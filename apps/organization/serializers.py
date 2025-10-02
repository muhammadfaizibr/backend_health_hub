from rest_framework import serializers
from django.db import transaction, models  # Add models here
from django.utils import timezone
from decimal import Decimal
from .models import Profile, CreditPackage, CreditsLedger, PackagePurchase
from apps.base.serializers import UserSerializer
from django.db import models 

class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_credits_purchased = serializers.SerializerMethodField()
    total_credits_used = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'organization_name', 'size', 'about',
            'area_of_focus', 'registration_number', 'current_credits_balance',
            'currency', 'version', 'total_credits_purchased', 'total_credits_used',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'current_credits_balance', 'version', 
            'created_at', 'updated_at'
        ]

    def get_total_credits_purchased(self, obj):
        return obj.ledger_entries.filter(
            transaction_type__in=['Purchase', 'Bonus', 'Refund']
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

    def get_total_credits_used(self, obj):
        deductions = obj.ledger_entries.filter(
            transaction_type='Deduction'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        return abs(deductions)

    def validate_registration_number(self, value):
        if value:
            qs = Profile.objects.filter(registration_number=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Registration number already exists."
                )
        return value


class CreditPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPackage
        fields = [
            'id', 'name', 'credits_amount', 'patient_limit', 'price',
            'currency', 'description', 'is_active', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        if data.get('credits_amount', 0) <= 0:
            raise serializers.ValidationError({
                'credits_amount': 'Credits amount must be positive.'
            })
        if data.get('price', 0) <= 0:
            raise serializers.ValidationError({
                'price': 'Price must be positive.'
            })
        return data


class CreditsLedgerSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source='organization.organization_name', 
        read_only=True
    )
    organization_email = serializers.EmailField(
        source='organization.user.email', 
        read_only=True
    )
    created_by = UserSerializer(read_only=True)
    related_appointment_id = serializers.UUIDField(
        source='related_appointment.id', 
        read_only=True
    )
    related_purchase_id = serializers.UUIDField(
        source='related_purchase.id', 
        read_only=True
    )

    class Meta:
        model = CreditsLedger
        fields = [
            'id', 'organization', 'organization_name', 'organization_email',
            'transaction_type', 'amount', 'balance_before', 'balance_after',
            'description', 'related_appointment', 'related_appointment_id',
            'related_purchase', 'related_purchase_id', 'related_transaction',
            'created_by', 'created_at'
        ]
        read_only_fields = [
            'id', 'organization', 'balance_before', 'balance_after', 
            'created_by', 'created_at'
        ]


class PackagePurchaseSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source='organization.organization_name', 
        read_only=True
    )
    organization_email = serializers.EmailField(
        source='organization.user.email', 
        read_only=True
    )
    credit_package = CreditPackageSerializer(read_only=True)
    credit_package_id = serializers.UUIDField(write_only=True)
    purchased_by = UserSerializer(read_only=True)
    payment_transaction_id = serializers.UUIDField(
        source='payment_transaction.id', 
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = PackagePurchase
        fields = [
            'id', 'organization', 'organization_name', 'organization_email',
            'credit_package', 'credit_package_id', 'credits_amount',
            'price_paid', 'currency', 'payment_transaction',
            'payment_transaction_id', 'status', 'purchased_by',
            'purchased_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organization', 'credits_amount', 'price_paid', 'currency',
            'purchased_by', 'purchased_at', 'created_at', 'updated_at'
        ]

    def validate_credit_package_id(self, value):
        try:
            package = CreditPackage.objects.get(id=value, is_active=True)
        except CreditPackage.DoesNotExist:
            raise serializers.ValidationError(
                "Credit package not found or is inactive."
            )
        return value

    @transaction.atomic
    def create(self, validated_data):
        credit_package_id = validated_data.pop('credit_package_id')
        
        try:
            package = CreditPackage.objects.get(id=credit_package_id, is_active=True)
        except CreditPackage.DoesNotExist:
            raise serializers.ValidationError("Credit package not found or is inactive.")
        
        organization = validated_data['organization']
        
        # Create purchase record
        purchase = PackagePurchase.objects.create(
            organization=organization,
            credit_package=package,
            credits_amount=package.credits_amount,
            price_paid=package.price,
            currency=package.currency,
            **validated_data
        )
        
        return purchase

    @transaction.atomic
    def update(self, instance, validated_data):
        # Only allow status updates
        if 'status' in validated_data:
            old_status = instance.status
            new_status = validated_data['status']
            
            # Handle status transitions
            if old_status == 'Pending' and new_status == 'Completed':
                instance.purchased_at = timezone.now()
                
                # Update organization balance
                org = instance.organization
                balance_before = org.current_credits_balance
                org.current_credits_balance += instance.credits_amount
                org.version += 1
                org.save(update_fields=['current_credits_balance', 'version', 'updated_at'])
                
                # Create ledger entry
                CreditsLedger.objects.create(
                    organization=org,
                    transaction_type='Purchase',
                    amount=instance.credits_amount,
                    balance_before=balance_before,
                    balance_after=org.current_credits_balance,
                    description=f'Purchase of {instance.credit_package.name} package',
                    related_purchase=instance,
                    related_transaction=instance.payment_transaction,
                    created_by=instance.purchased_by
                )
            
            elif old_status == 'Completed' and new_status == 'Refunded':
                # Handle refund
                org = instance.organization
                balance_before = org.current_credits_balance
                org.current_credits_balance -= instance.credits_amount
                
                if org.current_credits_balance < 0:
                    raise serializers.ValidationError(
                        "Insufficient balance for refund."
                    )
                
                org.version += 1
                org.save(update_fields=['current_credits_balance', 'version', 'updated_at'])
                
                # Create ledger entry
                CreditsLedger.objects.create(
                    organization=org,
                    transaction_type='Refund',
                    amount=-instance.credits_amount,
                    balance_before=balance_before,
                    balance_after=org.current_credits_balance,
                    description=f'Refund of {instance.credit_package.name} package',
                    related_purchase=instance,
                    created_by=validated_data.get('purchased_by')
                )
        
        return super().update(instance, validated_data)