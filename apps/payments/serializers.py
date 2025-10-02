from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .models import (
    PaymentMethod, Transaction, Refund, AppointmentBilling, WalletLedger, PayoutRequest
)
from apps.base.serializers import UserSerializer, WalletSerializer
from apps.base.models import Wallet


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment methods."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'user', 'user_email', 'provider', 'type', 'brand', 
            'is_default', 'expires_at', 'metadata', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'user_email', 'created_at', 'updated_at', 'deleted_at']

    def validate_expires_at(self, value):
        if value and value < timezone.now():
            raise serializers.ValidationError("Expiration date cannot be in the past.")
        return value

    def validate(self, attrs):
        # Card types must have expiration date
        if attrs.get('type') == 'Card' and not attrs.get('expires_at'):
            raise serializers.ValidationError({
                'expires_at': "Card payment methods must have an expiration date."
            })
        
        # Check for existing default if setting as default
        request = self.context.get('request')
        if attrs.get('is_default') and request:
            existing_default = PaymentMethod.objects.filter(
                user=request.user,
                is_default=True,
                deleted_at__isnull=True
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_default.exists():
                # Automatically unset existing default
                pass  # This is handled in model save()
        
        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for transactions."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    payment_method_info = serializers.SerializerMethodField()
    refunded_amount = serializers.ReadOnlyField()
    is_refundable = serializers.ReadOnlyField()

    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_id_gateway', 'idempotency_key', 'user', 'user_email',
            'payment_method', 'payment_method_info', 'amount', 'currency', 'status',
            'purpose', 'purpose_id', 'purpose_type', 'receipt_file', 'gateway_response',
            'failure_reason', 'refunded_amount', 'is_refundable',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'user_email', 'idempotency_key', 'status', 
            'gateway_response', 'created_at', 'updated_at', 'completed_at'
        ]

    def get_payment_method_info(self, obj):
        if obj.payment_method:
            return {
                'id': str(obj.payment_method.id),
                'provider': obj.payment_method.provider,
                'type': obj.payment_method.type
            }
        return None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for refunds."""
    
    transaction_info = serializers.SerializerMethodField()
    initiated_by_user = UserSerializer(source='initiated_by', read_only=True)
    processed_by_user = UserSerializer(source='processed_by', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id', 'transaction', 'transaction_info', 'refund_id_gateway', 'amount',
            'reason', 'status', 'initiated_by', 'initiated_by_user', 'processed_at',
            'processed_by', 'processed_by_user', 'failure_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'initiated_by', 'initiated_by_user', 'processed_by', 
            'processed_by_user', 'created_at', 'updated_at'
        ]

    def get_transaction_info(self, obj):
        return {
            'id': str(obj.transaction.id),
            'amount': str(obj.transaction.amount),
            'currency': obj.transaction.currency,
            'status': obj.transaction.status
        }

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than zero.")
        return value

    def validate(self, attrs):
        transaction = attrs.get('transaction') or (self.instance.transaction if self.instance else None)
        
        if transaction:
            # Check if transaction is refundable
            if not transaction.is_refundable:
                raise serializers.ValidationError({
                    'transaction': "This transaction cannot be refunded."
                })
            
            # Check refund amount
            amount = attrs.get('amount', self.instance.amount if self.instance else 0)
            total_refunded = transaction.refunded_amount
            
            if self.instance:
                # Exclude current refund from total
                total_refunded -= self.instance.amount
            
            if total_refunded + amount > transaction.amount:
                raise serializers.ValidationError({
                    'amount': f"Refund would exceed transaction amount. Available: {transaction.amount - total_refunded}"
                })
        
        return attrs


class AppointmentBillingSerializer(serializers.ModelSerializer):
    """Serializer for appointment billing."""
    
    appointment_info = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source='organization.user.email', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    translator_name = serializers.SerializerMethodField()

    class Meta:
        model = AppointmentBilling
        fields = [
            'id', 'appointment', 'appointment_info', 'organization', 'organization_name',
            'doctor', 'doctor_name', 'translator', 'translator_name', 'doctor_fee',
            'translator_fee', 'platform_fee', 'platform_fee_percentage', 'total_amount',
            'currency', 'status', 'billed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_amount', 'billed_at', 'created_at', 'updated_at']

    def get_appointment_info(self, obj):
        return {
            'id': str(obj.appointment.id),
            'scheduled_at': obj.appointment.scheduled_at.isoformat() if hasattr(obj.appointment, 'scheduled_at') else None
        }

    def get_translator_name(self, obj):
        return obj.translator.user.get_full_name() if obj.translator else None

    def validate(self, attrs):
        doctor_fee = attrs.get('doctor_fee', 0)
        translator_fee = attrs.get('translator_fee', 0)
        platform_fee = attrs.get('platform_fee', 0)
        
        # Validate fees are non-negative
        if doctor_fee < 0 or translator_fee < 0 or platform_fee < 0:
            raise serializers.ValidationError("Fees cannot be negative.")
        
        # Auto-calculate total
        attrs['total_amount'] = doctor_fee + translator_fee + platform_fee
        
        # Validate translator fee requires translator
        if translator_fee > 0 and not attrs.get('translator'):
            raise serializers.ValidationError({
                'translator': "Translator is required when translator fee is set."
            })
        
        return attrs


class WalletLedgerSerializer(serializers.ModelSerializer):
    """Serializer for wallet ledger entries."""
    
    wallet_info = serializers.SerializerMethodField()
    created_by_user = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = WalletLedger
        fields = [
            'id', 'wallet', 'wallet_info', 'transaction_type', 'amount', 
            'balance_before', 'balance_after', 'balance_type', 'status',
            'related_appointment', 'related_billing', 'related_payout',
            'description', 'available_at', 'created_by', 'created_by_user', 'created_at'
        ]
        read_only_fields = [
            'id', 'wallet', 'balance_before', 'balance_after', 
            'created_by', 'created_by_user', 'created_at'
        ]

    def get_wallet_info(self, obj):
        return {
            'id': str(obj.wallet.id),
            'user_email': obj.wallet.user.email,
            'available_balance': str(obj.wallet.available_balance),
            'pending_balance': str(obj.wallet.pending_balance)
        }


class PayoutRequestSerializer(serializers.ModelSerializer):
    """Serializer for payout requests."""
    
    wallet_info = WalletSerializer(source='wallet', read_only=True)
    processed_by_user = UserSerializer(source='processed_by', read_only=True)
    transaction_info = serializers.SerializerMethodField()

    class Meta:
        model = PayoutRequest
        fields = [
            'id', 'wallet', 'wallet_info', 'amount', 'currency', 'payment_method',
            'bank_details', 'status', 'transaction', 'transaction_info',
            'processing_notes', 'failure_reason', 'requested_at', 'processed_at',
            'processed_by', 'processed_by_user', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'wallet', 'status', 'transaction', 'processed_by', 
            'processed_by_user', 'requested_at', 'processed_at', 'created_at', 'updated_at'
        ]

    def get_transaction_info(self, obj):
        if obj.transaction:
            return {
                'id': str(obj.transaction.id),
                'status': obj.transaction.status,
                'amount': str(obj.transaction.amount)
            }
        return None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payout amount must be greater than zero.")
        
        # Check minimum payout amount
        min_payout = Decimal('10.00')  # Example minimum
        if value < min_payout:
            raise serializers.ValidationError(f"Minimum payout amount is {min_payout}.")
        
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        
        # Validate sufficient balance
        if request and hasattr(request.user, 'wallet'):
            wallet = request.user.wallet
            amount = attrs.get('amount')
            
            if amount > wallet.available_balance:
                raise serializers.ValidationError({
                    'amount': f"Insufficient balance. Available: {wallet.available_balance}"
                })
        
        # Require either payment method or bank details
        if not attrs.get('payment_method') and not attrs.get('bank_details'):
            raise serializers.ValidationError(
                "Either payment_method or bank_details must be provided."
            )
        
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        wallet = validated_data['wallet']
        amount = validated_data['amount']
        
        # Check available balance again with lock
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        
        if wallet.available_balance < amount:
            raise serializers.ValidationError({"amount": "Insufficient available balance."})
        
        # Create payout request first
        payout_request = super().create(validated_data)
        
        # Create wallet ledger entry
        ledger_entry = WalletLedger.objects.create(
            wallet=wallet,
            transaction_type='Withdrawal',
            amount=-amount,
            balance_before=wallet.available_balance,
            balance_after=wallet.available_balance - amount,
            balance_type='Available',
            status='Pending',
            related_payout=payout_request,
            description=f'Payout request #{payout_request.id}',
            created_by=self.context['request'].user
        )
        
        # Update wallet balance
        wallet.available_balance -= amount
        wallet.save()
        
        return payout_request