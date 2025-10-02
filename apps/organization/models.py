from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
from apps.base.models import User


class Profile(models.Model):
    """Organization profile with credit management capabilities."""
    
    SIZE_CHOICES = [
        ('Small', 'Small (1-50 employees)'),
        ('Medium', 'Medium (51-200 employees)'),
        ('Large', 'Large (201+ employees)'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('PKR', 'Pakistani Rupee'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='organization_profile'
    )
    organization_name = models.CharField(max_length=255)
    size = models.CharField(max_length=50, choices=SIZE_CHOICES, blank=True)
    about = models.TextField(blank=True)
    area_of_focus = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True,
        db_index=True
    )
    current_credits_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_profile'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['registration_number']),
        ]
        verbose_name = 'Organization Profile'
        verbose_name_plural = 'Organization Profiles'

    def __str__(self):
        return f"{self.organization_name} ({self.user.email})"

    def clean(self):
        if self.user and self.user.role != 'Organization':
            raise ValidationError({'user': 'User must have Organization role.'})
        
        if self.current_credits_balance < 0:
            raise ValidationError({'current_credits_balance': 'Balance cannot be negative.'})


class CreditPackage(models.Model):
    """Credit packages available for purchase by organizations."""
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('PKR', 'Pakistani Rupee'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    credits_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    patient_limit = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_credit_package'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
        ]
        verbose_name = 'Credit Package'
        verbose_name_plural = 'Credit Packages'

    def __str__(self):
        return f"{self.name} - {self.credits_amount} credits ({self.price} {self.currency})"

    def clean(self):
        if self.credits_amount <= 0:
            raise ValidationError({'credits_amount': 'Credits amount must be positive.'})
        if self.price <= 0:
            raise ValidationError({'price': 'Price must be positive.'})


class CreditsLedger(models.Model):
    """Tracks all credit transactions for organizations."""
    
    TRANSACTION_TYPE_CHOICES = [
        ('Purchase', 'Purchase'),
        ('Deduction', 'Deduction'),
        ('Refund', 'Refund'),
        ('Adjustment', 'Adjustment'),
        ('Bonus', 'Bonus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='ledger_entries'
    )
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPE_CHOICES,
        db_index=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    balance_after = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    description = models.TextField()
    related_appointment = models.ForeignKey(
        'patients.Appointment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='credit_ledger_entries'
    )
    related_purchase = models.ForeignKey(
        'PackagePurchase', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ledger_entries'
    )
    related_transaction = models.ForeignKey(
        'payments.Transaction', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='credit_ledger_entries'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_ledger_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organization_credits_ledger'
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['organization', 'transaction_type', '-created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Credits Ledger Entry'
        verbose_name_plural = 'Credits Ledger Entries'

    def __str__(self):
        return f"{self.organization.organization_name} - {self.transaction_type} - {self.amount}"

    def clean(self):
        if self.transaction_type in ['Purchase', 'Refund', 'Bonus'] and self.amount <= 0:
            raise ValidationError({
                'amount': f'{self.transaction_type} amount must be positive.'
            })
        
        if self.transaction_type == 'Deduction' and self.amount >= 0:
            raise ValidationError({
                'amount': 'Deduction amount must be negative.'
            })
        
        if self.balance_after != self.balance_before + self.amount:
            raise ValidationError({
                'balance_after': 'Balance calculation is incorrect.'
            })


class PackagePurchase(models.Model):
    """Records credit package purchases by organizations."""
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='purchases'
    )
    credit_package = models.ForeignKey(
        CreditPackage, 
        on_delete=models.PROTECT,
        related_name='purchases'
    )
    credits_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    price_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3)
    payment_transaction = models.OneToOneField(
        'payments.Transaction', 
        on_delete=models.PROTECT,
        related_name='package_purchase',
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Pending',
        db_index=True
    )
    purchased_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='package_purchases'
    )
    purchased_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_package_purchase'
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['organization', 'status', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Package Purchase'
        verbose_name_plural = 'Package Purchases'

    def __str__(self):
        return f"{self.organization.organization_name} - {self.credit_package.name} ({self.status})"

    def clean(self):
        if self.status == 'Completed' and not self.purchased_at:
            raise ValidationError({
                'purchased_at': 'Purchase date required for completed purchases.'
            })