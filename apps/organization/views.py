from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Sum, Q
from decimal import Decimal
from .models import Profile, CreditPackage, CreditsLedger, PackagePurchase
from .serializers import (
    ProfileSerializer, CreditPackageSerializer, 
    CreditsLedgerSerializer, PackagePurchaseSerializer
)
from rest_framework.exceptions import ValidationError, PermissionDenied


class IsStaff(BasePermission):
    """Permission class to check if user is staff."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()  # Add class-level queryset
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['organization_name', 'registration_number', 'area_of_focus']
    ordering_fields = ['created_at', 'organization_name']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Profile.objects.select_related('user')
        
        user = self.request.user
        
        if user.role == 'Organization':
            return queryset.filter(user=user)
        elif user.is_staff:
            return queryset
        
        return queryset.none()

    def perform_create(self, serializer):
        if self.request.user.role != 'Organization':
            raise ValidationError("Only organization users can create profiles.")
        
        if Profile.objects.filter(user=self.request.user).exists():
            raise ValidationError("Profile already exists for this organization.")
        
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Get the authenticated organization's profile."""
        if request.user.role != 'Organization':
            raise PermissionDenied("Only organizations have profiles.")
        
        try:
            profile = Profile.objects.select_related('user').get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except Profile.DoesNotExist:
            return Response(
                {'error': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def credits_summary(self, request, pk=None):
        """Get detailed credits summary for an organization."""
        organization = self.get_object()
        
        ledger_summary = organization.ledger_entries.aggregate(
            total_purchased=Sum(
                'amount',
                filter=Q(transaction_type__in=['Purchase', 'Bonus'])
            ),
            total_refunded=Sum(
                'amount',
                filter=Q(transaction_type='Refund')
            ),
            total_deducted=Sum(
                'amount',
                filter=Q(transaction_type='Deduction')
            ),
            total_adjustments=Sum(
                'amount',
                filter=Q(transaction_type='Adjustment')
            )
        )
        
        summary = {
            'current_balance': float(organization.current_credits_balance),
            'total_purchased': float(ledger_summary['total_purchased'] or Decimal('0.00')),
            'total_refunded': float(abs(ledger_summary['total_refunded'] or Decimal('0.00'))),
            'total_deducted': float(abs(ledger_summary['total_deducted'] or Decimal('0.00'))),
            'total_adjustments': float(ledger_summary['total_adjustments'] or Decimal('0.00')),
            'currency': organization.currency,
        }
        
        return Response(summary)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def adjust_credits(self, request, pk=None):
        """Manually adjust organization credits (admin only)."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff can adjust credits.")
        
        organization = self.get_object()
        amount = request.data.get('amount')
        description = request.data.get('description', 'Manual adjustment')
        
        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid amount.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount == 0:
            return Response(
                {'error': 'Amount cannot be zero.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        balance_before = organization.current_credits_balance
        new_balance = balance_before + amount
        
        if new_balance < 0:
            return Response(
                {'error': 'Adjustment would result in negative balance.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update balance
        organization.current_credits_balance = new_balance
        organization.version += 1
        organization.save(update_fields=['current_credits_balance', 'version', 'updated_at'])
        
        # Create ledger entry
        CreditsLedger.objects.create(
            organization=organization,
            transaction_type='Adjustment',
            amount=amount,
            balance_before=balance_before,
            balance_after=new_balance,
            description=description,
            created_by=request.user
        )
        
        return Response({
            'message': 'Credits adjusted successfully.',
            'balance_before': float(balance_before),
            'balance_after': float(new_balance),
            'adjustment': float(amount)
        })


class CreditPackageViewSet(viewsets.ModelViewSet):
    queryset = CreditPackage.objects.all()  # Add class-level queryset
    serializer_class = CreditPackageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'currency']
    search_fields = ['name', 'description']
    ordering_fields = ['display_order', 'price', 'credits_amount']
    ordering = ['display_order']

    def get_queryset(self):
        queryset = CreditPackage.objects.all()
        
        # Non-staff users only see active packages
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        return queryset

    def get_permissions(self):
        # Only staff can create/update/delete packages
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsStaff()]
        return super().get_permissions()


class CreditsLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CreditsLedger.objects.all()  # Add class-level queryset
    serializer_class = CreditsLedgerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['transaction_type', 'organization']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = CreditsLedger.objects.select_related(
            'organization__user',
            'created_by',
            'related_appointment',
            'related_purchase__credit_package',
            'related_transaction'
        )
        
        user = self.request.user
        
        if user.role == 'Organization':
            try:
                org = Profile.objects.get(user=user)
                return queryset.filter(organization=org)
            except Profile.DoesNotExist:
                return queryset.none()
        elif user.is_staff:
            return queryset
        
        return queryset.none()

    @action(detail=False, methods=['get'])
    def my_ledger(self, request):
        """Get ledger entries for the authenticated organization."""
        if request.user.role != 'Organization':
            raise PermissionDenied("Only organizations can access ledger.")
        
        try:
            org = Profile.objects.get(user=request.user)
            ledger = self.get_queryset().filter(organization=org)
            
            page = self.paginate_queryset(ledger)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(ledger, many=True)
            return Response(serializer.data)
        except Profile.DoesNotExist:
            return Response(
                {'error': 'Organization profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )


class PackagePurchaseViewSet(viewsets.ModelViewSet):
    queryset = PackagePurchase.objects.all()  # Add class-level queryset
    serializer_class = PackagePurchaseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'organization']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = PackagePurchase.objects.select_related(
            'organization__user',
            'credit_package',
            'purchased_by',
            'payment_transaction'
        )
        
        user = self.request.user
        
        if user.role == 'Organization':
            try:
                org = Profile.objects.get(user=user)
                return queryset.filter(organization=org)
            except Profile.DoesNotExist:
                return queryset.none()
        elif user.is_staff:
            return queryset
        
        return queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        if self.request.user.role != 'Organization':
            raise ValidationError("Only organizations can purchase packages.")
        
        try:
            org = Profile.objects.get(user=self.request.user)
        except Profile.DoesNotExist:
            raise ValidationError("Organization profile not found.")
        
        serializer.save(
            organization=org,
            purchased_by=self.request.user,
            status='Pending'
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete_purchase(self, request, pk=None):
        """Complete a pending purchase (typically after payment confirmation)."""
        purchase = self.get_object()
        
        if purchase.status != 'Pending':
            return Response(
                {'error': f'Cannot complete purchase with status: {purchase.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update purchase to completed
        serializer = self.get_serializer(
            purchase,
            data={'status': 'Completed'},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Purchase completed successfully.',
            'purchase': serializer.data
        })

    @action(detail=False, methods=['get'])
    def my_purchases(self, request):
        """Get purchases for the authenticated organization."""
        if request.user.role != 'Organization':
            raise PermissionDenied("Only organizations can access purchases.")
        
        try:
            org = Profile.objects.get(user=request.user)
            purchases = self.get_queryset().filter(organization=org)
            
            page = self.paginate_queryset(purchases)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(purchases, many=True)
            return Response(serializer.data)
        except Profile.DoesNotExist:
            return Response(
                {'error': 'Organization profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
