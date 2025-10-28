from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

from apps.base.models import User, Wallet
from apps.patients.models import Appointment
from apps.organization.models import Profile as OrganizationProfile


class PaymentMethod(models.Model):
    """Payment methods for users (cards, wallets, bank accounts)."""
    
    PROVIDER_CHOICES = [
        ('stripe', _('Stripe')),
        ('jazz_cash', _('JazzCash')),
        ('easy_paisa', _('EasyPaisa')),
        ('bank', _('Bank')),
        ('cash', _('Cash')),
    ]

    TYPE_CHOICES = [
        ('card', _('Card')),
        ('wallet', _('Wallet')),
        ('bank', _('Bank')),
        ('cash', _('Cash')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='payment_methods'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    brand = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'billing_payment_method'
        verbose_name = _('Payment Method')
        verbose_name_plural = _('Payment Methods')
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', 'deleted_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.provider} ({self.type})"

    def clean(self):
        """Validate payment method constraints."""
        if self.expires_at and self.expires_at < timezone.now():
            raise ValidationError({
                'expires_at': _('Payment method has already expired.')
            })
        
        # Validate that card types have expiration dates
        if self.type == 'Card' and not self.expires_at:
            raise ValidationError({
                'expires_at': _('Card payment methods must have an expiration date.')
            })

    def save(self, *args, **kwargs):
        # Ensure only one default payment method per user
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user, 
                is_default=True,
                deleted_at__isnull=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if payment method is active (not deleted and not expired)."""
        if self.deleted_at:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class Transaction(models.Model):
    """Financial transactions for credit purchases and payouts."""
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('success', _('Success')),
        ('failed', _('Failed')),
        ('refunded', _('Refunded')),
        ('partially_refunded', _('Partially Refunded')),
    ]

    PURPOSE_CHOICES = [
        ('credit_purchase', _('Credit Purchase')),
        ('payout', _('Payout')),
    ]

    PURPOSE_TYPE_CHOICES = [
        ('package_purchase', _('Package Purchase')),
        ('payout', _('Payout')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id_gateway = models.CharField(
        max_length=255, 
        unique=True, 
        null=True, 
        blank=True,
        help_text=_('Transaction ID from payment gateway')
    )
    idempotency_key = models.CharField(
        max_length=255, 
        unique=True,
        help_text=_('Unique key to prevent duplicate transactions')
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    payment_method = models.ForeignKey(
        PaymentMethod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='Pending'
    )
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    purpose_id = models.UUIDField()
    purpose_type = models.CharField(max_length=30, choices=PURPOSE_TYPE_CHOICES)
    receipt_file = models.ForeignKey(
        'files.File', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transaction_receipts'
    )
    gateway_response = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'billing_transaction'
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', '-created_at']),
            models.Index(fields=['purpose', 'purpose_id']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.amount} {self.currency} ({self.status})"

    def clean(self):
        """Validate transaction constraints."""
        if self.amount <= 0:
            raise ValidationError({
                'amount': _('Transaction amount must be greater than zero.')
            })
        
        if self.status in ['Success', 'Refunded'] and not self.completed_at:
            raise ValidationError({
                'completed_at': _('Completed transactions must have a completion timestamp.')
            })

    @property
    def is_refundable(self):
        """Check if transaction can be refunded."""
        return self.status == 'Success' and self.purpose == 'Credit Purchase'

    @property
    def refunded_amount(self):
        """Calculate total refunded amount."""
        return self.refunds.filter(
            status='Processed'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0


class Refund(models.Model):
    """Refund records for transactions."""
    
    STATUS_CHOICES = [
        ('initiated', _('Initiated')),
        ('processing', _('Processing')),
        ('processed', _('Processed')),
        ('failed', _('Failed')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction, 
        on_delete=models.CASCADE, 
        related_name='refunds'
    )
    refund_id_gateway = models.CharField(
        max_length=255, 
        unique=True, 
        null=True, 
        blank=True
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Initiated'
    )
    initiated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='initiated_refunds'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_refunds'
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_refund'
        verbose_name = _('Refund')
        verbose_name_plural = _('Refunds')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Refund {self.amount} for Transaction {self.transaction.id}"

    def clean(self):
        """Validate refund constraints."""
        if self.amount <= 0:
            raise ValidationError({
                'amount': _('Refund amount must be greater than zero.')
            })
        
        if self.transaction_id:
            # Check if refund amount doesn't exceed transaction amount
            total_refunded = self.transaction.refunded_amount
            if self.pk:
                # Exclude current refund from calculation if updating
                total_refunded -= Refund.objects.filter(pk=self.pk).first().amount or 0
            
            if total_refunded + self.amount > self.transaction.amount:
                raise ValidationError({
                    'amount': _('Total refund amount cannot exceed transaction amount.')
                })


class AppointmentBilling(models.Model):
    """Billing records for appointments."""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('billed', _('Billed')),
        ('cancelled', _('Cancelled')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(
        Appointment, 
        on_delete=models.CASCADE,
        related_name='billing'
    )
    organization = models.ForeignKey(
        OrganizationProfile, 
        on_delete=models.CASCADE,
        related_name='billings'
    )
    doctor = models.ForeignKey(
        'doctors.Profile', 
        on_delete=models.CASCADE,
        related_name='billings'
    )
    translator = models.ForeignKey(
        'translators.Profile', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='billings'
    )
    doctor_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    translator_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    platform_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    platform_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MinValueValidator(100)]
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Draft'
    )
    billed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_appointment'
        verbose_name = _('Appointment Billing')
        verbose_name_plural = _('Appointment Billings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['appointment']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['doctor', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Billing for Appointment {self.appointment.id} - {self.total_amount} {self.currency}"

    def clean(self):
        """Validate billing constraints."""
        if self.doctor_fee < 0 or self.translator_fee < 0 or self.platform_fee < 0:
            raise ValidationError(_('Fees cannot be negative.'))
        
        calculated_total = self.doctor_fee + self.translator_fee + self.platform_fee
        if abs(calculated_total - self.total_amount) > 0.01:  # Allow small floating point differences
            raise ValidationError({
                'total_amount': _('Total amount must equal sum of all fees.')
            })
        
        if self.status == 'Billed' and not self.billed_at:
            raise ValidationError({
                'billed_at': _('Billed appointments must have a billing timestamp.')
            })

    def save(self, *args, **kwargs):
        # Auto-calculate total if not provided
        if not self.total_amount:
            self.total_amount = self.doctor_fee + self.translator_fee + self.platform_fee
        super().save(*args, **kwargs)


class WalletLedger(models.Model):
    """Ledger entries for wallet transactions."""
    
    TRANSACTION_TYPE_CHOICES = [
        ('earning', _('Earning')),
        ('withdrawal', _('Withdrawal')),
        ('refund', _('Refund')),
        ('adjustment', _('Adjustment')),
    ]

    BALANCE_TYPE_CHOICES = [
        ('pending', _('Pending')),
        ('available', _('Available')),
    ]

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('available', _('Available')),
        ('withdrawn', _('Withdrawn')),
        ('refunded', _('Refunded')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, 
        on_delete=models.CASCADE, 
        related_name='ledger_entries'
    )
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPE_CHOICES
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    balance_after = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    balance_type = models.CharField(max_length=20, choices=BALANCE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    related_appointment = models.ForeignKey(
        Appointment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='wallet_ledger_entries'
    )
    related_billing = models.ForeignKey(
        AppointmentBilling, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='wallet_ledger_entries'
    )
    related_payout = models.ForeignKey(
        'PayoutRequest', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='wallet_ledger_entries'
    )
    description = models.TextField()
    available_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_wallet_ledger_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_wallet_ledger'
        verbose_name = _('Wallet Ledger Entry')
        verbose_name_plural = _('Wallet Ledger Entries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'transaction_type', 'status', '-created_at']),
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.wallet.user.email} - {self.transaction_type} {self.amount}"

    def clean(self):
        """Validate ledger entry constraints."""
        if self.balance_before < 0 or self.balance_after < 0:
            raise ValidationError(_('Wallet balance cannot be negative.'))
        
        # Validate balance calculation
        expected_balance = self.balance_before + self.amount
        if abs(expected_balance - self.balance_after) > 0.01:
            raise ValidationError({
                'balance_after': _('Balance calculation is incorrect.')
            })


class PayoutRequest(models.Model):
    """Payout requests for withdrawing funds from wallet."""
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, 
        on_delete=models.CASCADE, 
        related_name='payout_requests'
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(max_length=3, default='USD')
    payment_method = models.ForeignKey(
        PaymentMethod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='payout_requests'
    )
    bank_details = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Pending'
    )
    transaction = models.ForeignKey(
        Transaction, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='payout_requests'
    )
    processing_notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_payouts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_payout_request'
        verbose_name = _('Payout Request')
        verbose_name_plural = _('Payout Requests')
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['wallet', 'status', '-requested_at']),
            models.Index(fields=['status', '-requested_at']),
        ]

    def __str__(self):
        return f"Payout {self.amount} {self.currency} for {self.wallet.user.email} ({self.status})"

    def clean(self):
        """Validate payout request constraints."""
        if self.amount <= 0:
            raise ValidationError({
                'amount': _('Payout amount must be greater than zero.')
            })
        
        if self.wallet_id:
            if self.amount > self.wallet.available_balance:
                raise ValidationError({
                    'amount': _('Payout amount exceeds available balance.')
                })
        
        if self.status in ['Completed', 'Failed'] and not self.processed_at:
            raise ValidationError({
                'processed_at': _('Processed payouts must have a processing timestamp.')
            })