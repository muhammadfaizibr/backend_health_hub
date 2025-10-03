from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
import uuid


class UserManager(BaseUserManager):
    """Custom manager for User model with role-based defaults and staff/superuser logic."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a standard user with email and password."""
        if not email:
            raise ValueError(_('The Email field must be set'))
        
        email = self.normalize_email(email)
        extra_fields.setdefault('role', 'Patient')
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with admin privileges."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'Admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

    def active_users(self):
        """Return queryset of active users (not soft-deleted)."""
        return self.get_queryset().filter(is_active=True, deleted_at__isnull=True)

    def users_by_role(self, role):
        """Return active users filtered by role."""
        return self.active_users().filter(role=role)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with role-based access and soft delete support."""
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    ROLE_CHOICES = [ 
        ('Patient', 'Patient'),
        ('Doctor', 'Doctor'),
        ('Translator', 'Translator'),
        ('Organization', 'Organization'),
        ('Admin', 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    password = models.CharField(_('password'), max_length=128)
    
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message=_('Enter a valid phone number.'))]
    )
    country_code = models.CharField(max_length=10, default='+1', blank=True)
    verification_id = models.CharField(max_length=255, unique=True, blank=True, null=True, db_index=True)
    bio = models.TextField(blank=True)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Patient', db_index=True)
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    
    timezone = models.CharField(max_length=50, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['deleted_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def soft_delete(self):
        """Soft delete the user by setting deleted_at and deactivating."""
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['deleted_at', 'is_active'])

    def get_full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name


class UserLanguage(models.Model):
    """Languages associated with a user."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='languages')
    language_code = models.CharField(max_length=10, help_text=_('ISO language code (e.g., en, ar, ur-PK)'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('user language')
        verbose_name_plural = _('user languages')
        unique_together = [['user', 'language_code']]
        indexes = [
            models.Index(fields=['user']),
        ]
        ordering = ['language_code']

    def __str__(self):
        return f"{self.user.email} - {self.language_code}"


class Education(models.Model):
    """Educational background information."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='education')
    school = models.CharField(max_length=255)
    degree = models.CharField(max_length=100)
    field = models.CharField(max_length=100)
    grade = models.CharField(max_length=10, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('education')
        verbose_name_plural = _('education records')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['school']),
        ]
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.degree} in {self.field} at {self.school}"

    def clean(self):
        """Validate that start_date is before end_date."""
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_('Start date cannot be after end date.'))


class Experience(models.Model):
    """Professional work experience."""
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('House Job', 'House Job'),
        ('Part Time', 'Part Time'),
        ('Full Time', 'Full Time'),
        ('Contract', 'Contract'),
        ('Internship', 'Internship'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiences')
    title = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    company_or_organization = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('experience')
        verbose_name_plural = _('experiences')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['title']),
        ]
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.title} at {self.company_or_organization}"

    def clean(self):
        """Validate that start_date is before end_date."""
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_('Start date cannot be after end date.'))


class Certification(models.Model):
    """Professional certifications and credentials."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certifications')
    title = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255)
    issue_date = models.DateField()
    expiration_date = models.DateField(blank=True, null=True)
    credential_id = models.CharField(max_length=100, blank=True)
    credential_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    file = models.ForeignKey('files.File', on_delete=models.SET_NULL, null=True, blank=True, related_name='certifications')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('certification')
        verbose_name_plural = _('certifications')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['title']),
        ]
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.title} from {self.issuing_organization}"

    def clean(self):
        """Validate that issue_date is before expiration_date."""
        from django.core.exceptions import ValidationError
        if self.issue_date and self.expiration_date and self.issue_date > self.expiration_date:
            raise ValidationError(_('Issue date cannot be after expiration date.'))


class AvailabilitySlot(models.Model):
    """Weekly availability slots for scheduling."""
    
    DAY_CHOICES = [
        (0, _('Sunday')),
        (1, _('Monday')),
        (2, _('Tuesday')),
        (3, _('Wednesday')),
        (4, _('Thursday')),
        (5, _('Friday')),
        (6, _('Saturday')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availability_slots')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('availability slot')
        verbose_name_plural = _('availability slots')
        unique_together = [['user', 'day_of_week', 'start_time', 'end_time']]
        indexes = [
            models.Index(fields=['user', 'day_of_week']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.get_day_of_week_display()}: {self.start_time} - {self.end_time}"

    def clean(self):
        """Validate that start_time is before end_time."""
        from django.core.exceptions import ValidationError
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(_('Start time must be before end time.'))


class ServiceFee(models.Model):
    """Fee structure for services by duration."""
    
    DURATION_CHOICES = [
        (15, '15 min'),
        (30, '30 min'),
        (45, '45 min'),
        (60, '60 min'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_fees')
    duration = models.IntegerField(choices=DURATION_CHOICES)
    fee = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('service fee')
        verbose_name_plural = _('service fees')
        unique_together = [['user', 'duration']]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['duration']),
        ]
        ordering = ['duration']

    def __str__(self):
        return f"{self.get_duration_display()} - {self.fee} {self.currency}"

    def clean(self):
        """Validate that fee is positive."""
        from django.core.exceptions import ValidationError
        if self.fee and self.fee <= 0:
            raise ValidationError(_('Fee must be greater than zero.'))


class Wallet(models.Model):
    """User wallet for managing earnings and balances."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_lifetime_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    version = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('wallet')
        verbose_name_plural = _('wallets')
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.available_balance} {self.currency}"

    def clean(self):
        """Validate that balances are non-negative."""
        from django.core.exceptions import ValidationError
        if self.available_balance < 0:
            raise ValidationError(_('Available balance cannot be negative.'))
        if self.pending_balance < 0:
            raise ValidationError(_('Pending balance cannot be negative.'))
        if self.total_lifetime_earnings < 0:
            raise ValidationError(_('Total lifetime earnings cannot be negative.'))