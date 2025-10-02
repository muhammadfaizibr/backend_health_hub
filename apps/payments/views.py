from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from decimal import Decimal

from .models import (
    PaymentMethod, Transaction, Refund, AppointmentBilling, WalletLedger, PayoutRequest
)
from .serializers import (
    PaymentMethodSerializer, TransactionSerializer, RefundSerializer,
    AppointmentBillingSerializer, WalletLedgerSerializer, PayoutRequestSerializer
)
from .permissions import IsOwnerOrAdmin, IsOrganizationOrAdmin
from apps.base.models import Wallet
from apps.organization.models import Profile as OrganizationProfile, CreditsLedger
from django.db import models
from rest_framework.serializers import ValidationError


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment methods.
    Users can only access their own payment methods.
    """
    
    queryset = PaymentMethod.objects.select_related('user').filter(deleted_at__isnull=True)
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['provider', 'type', 'is_default']
    ordering = ['-is_default', '-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        """Soft delete payment method."""
        if instance.is_default:
            raise ValidationError("Cannot delete default payment method. Set another as default first.")
        
        instance.deleted_at = timezone.now()
        instance.save()

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set payment method as default."""
        payment_method = self.get_object()
        
        with transaction.atomic():
            # Unset all other defaults
            PaymentMethod.objects.filter(
                user=request.user,
                is_default=True,
                deleted_at__isnull=True
            ).update(is_default=False)
            
            # Set this as default
            payment_method.is_default = True
            payment_method.save()
        
        return Response({'message': 'Payment method set as default.'})


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing transactions.
    Read-only for regular users, admin can access all.
    """
    
    queryset = Transaction.objects.select_related('user', 'payment_method')
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'purpose', 'currency', 'purpose_type']
    search_fields = ['transaction_id_gateway', 'idempotency_key']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """Get transaction receipt."""
        transaction_obj = self.get_object()
        
        if transaction_obj.receipt_file:
            return Response({
                'receipt_url': transaction_obj.receipt_file.file.url if hasattr(transaction_obj.receipt_file, 'file') else None
            })
        
        return Response(
            {'error': 'No receipt available for this transaction.'},
            status=status.HTTP_404_NOT_FOUND
        )


class RefundViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing refunds.
    Users can view their refunds, staff can process them.
    """
    
    queryset = Refund.objects.select_related('transaction__user', 'initiated_by', 'processed_by')
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(transaction__user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(initiated_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def process(self, request, pk=None):
        """Process a refund (admin only)."""
        refund = self.get_object()
        
        if refund.status != 'Initiated':
            return Response(
                {'error': 'Only initiated refunds can be processed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            refund.status = 'Processing'
            refund.save()
            
            # TODO: Integrate with payment gateway to process refund
            # gateway_result = process_gateway_refund(refund)
            
            # Simulate success for now
            refund.status = 'Processed'
            refund.processed_at = timezone.now()
            refund.processed_by = request.user
            refund.save()
            
            # Update transaction status
            trans = refund.transaction
            total_refunded = trans.refunded_amount
            
            if total_refunded >= trans.amount:
                trans.status = 'Refunded'
            else:
                trans.status = 'Partially Refunded'
            trans.save()
        
        return Response(self.get_serializer(refund).data)


class AppointmentBillingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing appointment billing.
    Organizations can manage their billings, staff can access all.
    """
    
    queryset = AppointmentBilling.objects.select_related(
        'appointment', 'organization__user', 'doctor__user', 'translator__user'
    )
    serializer_class = AppointmentBillingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'organization']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        
        if hasattr(user, 'role') and user.role == 'Organization':
            org = OrganizationProfile.objects.filter(user=user).first()
            if org:
                return self.queryset.filter(organization=org)
        
        return self.queryset.none()

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def bill(self, request, pk=None):
        """Process billing for an appointment."""
        billing = self.get_object()
        
        if billing.status != 'Draft':
            return Response(
                {'error': 'Only draft billings can be processed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        org = billing.organization
        
        # Lock organization for update
        org = OrganizationProfile.objects.select_for_update().get(pk=org.pk)
        
        # Check sufficient credits
        if org.current_credits_balance < billing.total_amount:
            return Response(
                {'error': f'Insufficient credits. Available: {org.current_credits_balance}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Deduct credits from organization
        balance_before = org.current_credits_balance
        org.current_credits_balance -= billing.total_amount
        org.version = (org.version or 0) + 1
        org.save()
        
        # Create organization credits ledger entry
        CreditsLedger.objects.create(
            organization=org,
            transaction_type='Deduction',
            amount=-billing.total_amount,
            balance_before=balance_before,
            balance_after=org.current_credits_balance,
            description=f'Billed for appointment {billing.appointment.id}',
            related_appointment=billing.appointment,
            created_by=request.user
        )
        
        # Add earnings to doctor wallet
        doctor_wallet = Wallet.objects.select_for_update().get(user=billing.doctor.user)
        
        WalletLedger.objects.create(
            wallet=doctor_wallet,
            transaction_type='Earning',
            amount=billing.doctor_fee,
            balance_before=doctor_wallet.pending_balance,
            balance_after=doctor_wallet.pending_balance + billing.doctor_fee,
            balance_type='Pending',
            status='Pending',
            related_billing=billing,
            related_appointment=billing.appointment,
            description=f'Doctor fee for appointment {billing.appointment.id}',
            created_by=request.user
        )
        
        doctor_wallet.pending_balance += billing.doctor_fee
        doctor_wallet.save()
        
        # Add earnings to translator wallet if applicable
        if billing.translator and billing.translator_fee > 0:
            translator_wallet = Wallet.objects.select_for_update().get(user=billing.translator.user)
            
            WalletLedger.objects.create(
                wallet=translator_wallet,
                transaction_type='Earning',
                amount=billing.translator_fee,
                balance_before=translator_wallet.pending_balance,
                balance_after=translator_wallet.pending_balance + billing.translator_fee,
                balance_type='Pending',
                status='Pending',
                related_billing=billing,
                related_appointment=billing.appointment,
                description=f'Translator fee for appointment {billing.appointment.id}',
                created_by=request.user
            )
            
            translator_wallet.pending_balance += billing.translator_fee
            translator_wallet.save()
        
        # Update billing status
        billing.status = 'Billed'
        billing.billed_at = timezone.now()
        billing.save()
        
        return Response(self.get_serializer(billing).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """Cancel a billing."""
        billing = self.get_object()
        
        if billing.status == 'Cancelled':
            return Response(
                {'error': 'Billing is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if billing.status == 'Billed':
            return Response(
                {'error': 'Cannot cancel billed appointments. Request a refund instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        billing.status = 'Cancelled'
        billing.save()
        
        return Response({'message': 'Billing cancelled successfully.'})


class WalletLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing wallet ledger entries.
    Read-only, users can only see their own ledger.
    """
    
    queryset = WalletLedger.objects.select_related(
        'wallet__user', 'created_by', 'related_appointment', 'related_billing', 'related_payout'
    )
    serializer_class = WalletLedgerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['transaction_type', 'status', 'balance_type']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        
        wallet = Wallet.objects.filter(user=self.request.user).first()
        if wallet:
            return self.queryset.filter(wallet=wallet)
        
        return self.queryset.none()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get wallet summary statistics."""
        wallet = get_object_or_404(Wallet, user=request.user)
        
        ledger_entries = WalletLedger.objects.filter(wallet=wallet)
        
        total_earnings = ledger_entries.filter(
            transaction_type='Earning',
            status__in=['Pending', 'Available']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        total_withdrawn = ledger_entries.filter(
            transaction_type='Withdrawal',
            status='Withdrawn'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        return Response({
            'available_balance': wallet.available_balance,
            'pending_balance': wallet.pending_balance,
            'total_earnings': abs(total_earnings),
            'total_withdrawn': abs(total_withdrawn)
        })


class PayoutRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payout requests.
    Users can create and view their requests, staff can process them.
    """
    
    queryset = PayoutRequest.objects.select_related(
        'wallet__user', 'payment_method', 'processed_by', 'transaction'
    )
    serializer_class = PayoutRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering = ['-requested_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        
        wallet = Wallet.objects.filter(user=self.request.user).first()
        if wallet:
            return self.queryset.filter(wallet=wallet)
        
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        wallet = get_object_or_404(Wallet, user=self.request.user)
        serializer.save(wallet=wallet)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    @transaction.atomic
    def process(self, request, pk=None):
        """Process a payout request (admin only)."""
        payout = self.get_object()
        
        if payout.status != 'Pending':
            return Response(
                {'error': 'Only pending payouts can be processed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status to processing
        payout.status = 'Processing'
        payout.save()
        
        try:
            # TODO: Integrate with payment gateway
            # gateway_result = process_gateway_payout(payout)
            
            # Create transaction record
            trans = Transaction.objects.create(
                transaction_id_gateway=f'payout_{payout.id}',  # Replace with actual gateway ID
                idempotency_key=f'payout_{payout.id}_{timezone.now().timestamp()}',
                user=payout.wallet.user,
                payment_method=payout.payment_method,
                amount=payout.amount,
                currency=payout.currency,
                status='Success',
                purpose='Payout',
                purpose_id=payout.id,
                purpose_type='Payout',
                completed_at=timezone.now()
            )
            
            # Update payout
            payout.transaction = trans
            payout.status = 'Completed'
            payout.processed_at = timezone.now()
            payout.processed_by = request.user
            payout.save()
            
            # Update ledger entries
            WalletLedger.objects.filter(
                related_payout=payout,
                status='Pending'
            ).update(status='Withdrawn')
            
            return Response(self.get_serializer(payout).data)
            
        except Exception as e:
            # Handle failure
            payout.status = 'Failed'
            payout.failure_reason = str(e)
            payout.save()
            
            # Reverse wallet deduction
            wallet = Wallet.objects.select_for_update().get(pk=payout.wallet.pk)
            wallet.available_balance += payout.amount
            wallet.save()
            
            # Update ledger
            WalletLedger.objects.filter(
                related_payout=payout,
                status='Pending'
            ).update(status='Available')
            
            return Response(
                {'error': f'Payout processing failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """Cancel a payout request."""
        payout = self.get_object()
        
        if payout.status not in ['Pending', 'Processing']:
            return Response(
                {'error': 'Only pending or processing payouts can be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Restore wallet balance
        wallet = Wallet.objects.select_for_update().get(pk=payout.wallet.pk)
        wallet.available_balance += payout.amount
        wallet.save()
        
        # Update ledger
        WalletLedger.objects.filter(
            related_payout=payout,
            status='Pending'
        ).update(status='Available')
        
        # Update payout
        payout.status = 'Cancelled'
        payout.save()
        
        return Response({'message': 'Payout request cancelled successfully.'})
