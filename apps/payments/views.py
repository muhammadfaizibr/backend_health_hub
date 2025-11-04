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
    PaymentMethod, Transaction, Refund, AppointmentBilling, WalletLedger, PayoutRequest, 
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
from .services.stripe_service import StripeService
from apps.organization.models import CreditPackage, PackagePurchase
from rest_framework.views import APIView


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
            raise ValidationError({"non_field_errors":"Cannot delete default payment method. Set another as default first."})
        
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

            
    @action(detail=False, methods=['get'])
    def organization_appointments(self, request):
        """Get appointments for organization's billings."""
        if not hasattr(request.user, 'role') or request.user.role != 'Organization':
            return Response(
                {'error': 'Only organizations can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        org = OrganizationProfile.objects.filter(user=request.user).first()
        if not org:
            return Response(
                {'error': 'Organization profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        billings = self.queryset.filter(organization=org).select_related(
            'appointment__case__patient__user',
            'appointment__case__doctor__user',
            'appointment__time_slot'
        )
        
        appointments_data = []
        for billing in billings:
            appointment = billing.appointment
            appointments_data.append({
                'id': appointment.id,
                'billing_id': billing.id,
                'patient_name': appointment.case.patient.user.get_full_name(),
                'doctor_name': appointment.case.doctor.user.get_full_name(),
                'date': appointment.time_slot.date,
                'time': appointment.time_slot.start_time,
                'status': appointment.status,
                'billing_status': billing.status,
                'total_amount': billing.total_amount,
                'currency': billing.currency,
            })
        
        return Response(appointments_data)


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



class PackagePurchaseView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Purchase a credit package using Stripe."""
        if request.user.role != 'Organization':
            return Response(
                {'error': 'Only organizations can purchase packages.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        package_id = request.data.get('package_id')
        
        try:
            # Get organization profile
            org = OrganizationProfile.objects.select_for_update().get(user=request.user)
            
            # Get credit package
            package = CreditPackage.objects.get(id=package_id, is_active=True)
            
            # Create idempotency key
            idempotency_key = f"purchase_{org.id}_{package.id}_{int(timezone.now().timestamp() * 1000)}"
            
            # Check if transaction already exists
            existing_transaction = Transaction.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            
            if existing_transaction:
                return Response(
                    {'error': 'Transaction already processed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create Stripe payment intent
            stripe_service = StripeService()
            payment_intent = stripe_service.create_payment_intent(
                amount=package.price,
                currency='pkr',
                metadata={
                    'organization_id': str(org.id),
                    'package_id': str(package.id),
                    'credits_amount': str(package.credits_amount),
                }
            )
            
            # Create transaction record
            transaction_obj = Transaction.objects.create(
                transaction_id_gateway=payment_intent.id,
                idempotency_key=idempotency_key,
                user=request.user,
                amount=package.price,
                currency='PKR',
                status='pending',
                purpose='credit_purchase',
                purpose_id=package.id,
                purpose_type='package_purchase',
                gateway_response={'payment_intent_id': payment_intent.id}
            )
            
            # Create package purchase record with correct field names
            purchase = PackagePurchase.objects.create(
                organization=org,
                credit_package=package,  # Correct field name
                credits_amount=package.credits_amount,  # Correct field name
                price_paid=package.price,  # Correct field name
                currency='PKR',
                payment_transaction=transaction_obj,  # Correct field name
                status='pending',
                purchased_by=request.user
            )
            
            return Response({
                'client_secret': payment_intent.client_secret,
                'purchase_id': str(purchase.id),
                'transaction_id': str(transaction_obj.id),
            })
            
        except OrganizationProfile.DoesNotExist:
            return Response(
                {'error': 'Organization profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreditPackage.DoesNotExist:
            return Response(
                {'error': 'Credit package not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    def patch(self, request, purchase_id):
        """Confirm package purchase after Stripe payment."""
        try:
            purchase = PackagePurchase.objects.select_for_update().get(
                id=purchase_id,
                organization__user=request.user
            )
            
            if purchase.status != 'pending':
                return Response(
                    {'error': 'Purchase already processed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify payment with Stripe
            stripe_service = StripeService()
            payment_intent = stripe_service.confirm_payment(
                purchase.payment_transaction.transaction_id_gateway
            )
            
            if payment_intent.status != 'succeeded':
                return Response(
                    {'error': f'Payment not successful. Status: {payment_intent.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update transaction
            purchase.payment_transaction.status = 'success'
            purchase.payment_transaction.completed_at = timezone.now()
            purchase.payment_transaction.save()
            
            # Update purchase
            purchase.status = 'completed'
            purchase.purchased_at = timezone.now()
            purchase.save()
            
            # Update organization credits
            org = purchase.organization
            balance_before = org.current_credits_balance
            org.current_credits_balance += purchase.credits_amount
            org.version = (org.version or 0) + 1
            org.save()
            
            # Create credits ledger entry with correct field name
            CreditsLedger.objects.create(
                organization=org,
                transaction_type='purchase',
                amount=purchase.credits_amount,
                balance_before=balance_before,
                balance_after=org.current_credits_balance,
                description=f'Purchased {purchase.credits_amount} credits - {purchase.credit_package.name}',
                related_purchase=purchase,  # Correct field name
                related_transaction=purchase.payment_transaction,
                created_by=request.user
            )
            
            return Response({
                'message': 'Package purchased successfully.',
                'credits_balance': float(org.current_credits_balance),
                'credits_added': float(purchase.credits_amount),
            })
            
        except PackagePurchase.DoesNotExist:
            return Response(
                {'error': 'Purchase not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Log the full error for debugging
            import traceback
            print(f"Purchase confirmation error: {str(e)}")
            print(traceback.format_exc())
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )