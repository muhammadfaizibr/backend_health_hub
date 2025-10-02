from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg
import uuid

from apps.base.models import User, Education, Experience, Certification, AvailabilitySlot, ServiceFee


class Profile(models.Model):
    """Translator profile with professional information."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='translator_profile'
    )
    about = models.TextField(blank=True)
    area_of_focus = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'translator_profile'
        verbose_name = _('Translator Profile')
        verbose_name_plural = _('Translator Profiles')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - Translator Profile"

    def clean(self):
        """Validate that user has Translator role."""
        if self.user_id and hasattr(self.user, 'role') and self.user.role != 'Translator':
            raise ValidationError({
                'user': _('Only users with Translator role can have a translator profile.')
            })

    @property
    def average_rating(self):
        """Calculate average rating from reviews."""
        avg = self.reviews.filter(status='Published').aggregate(Avg('rating'))['rating__avg']
        return round(avg, 2) if avg else None

    @property
    def total_reviews(self):
        """Count total published reviews."""
        return self.reviews.filter(status='Published').count()


class TranslatorExperience(models.Model):
    """Links translators to their professional experiences."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='experiences'
    )
    experience = models.ForeignKey(
        Experience, 
        on_delete=models.CASCADE,
        related_name='translator_experiences'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'translator_experience'
        verbose_name = _('Translator Experience')
        verbose_name_plural = _('Translator Experiences')
        unique_together = ['translator', 'experience']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['translator', '-created_at']),
        ]

    def __str__(self):
        return f"{self.translator.user.get_full_name()} - {self.experience.title}"


class TranslatorEducation(models.Model):
    """Links translators to their educational background."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='educations'
    )
    education = models.ForeignKey(
        Education, 
        on_delete=models.CASCADE,
        related_name='translator_educations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'translator_education'
        verbose_name = _('Translator Education')
        verbose_name_plural = _('Translator Education')
        unique_together = ['translator', 'education']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['translator', '-created_at']),
        ]

    def __str__(self):
        return f"{self.translator.user.get_full_name()} - {self.education.degree}"


class TranslatorCertification(models.Model):
    """Links translators to their certifications."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='certifications'
    )
    certification = models.ForeignKey(
        Certification, 
        on_delete=models.CASCADE,
        related_name='translator_certifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'translator_certification'
        verbose_name = _('Translator Certification')
        verbose_name_plural = _('Translator Certifications')
        unique_together = ['translator', 'certification']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['translator', '-created_at']),
        ]

    def __str__(self):
        return f"{self.translator.user.get_full_name()} - {self.certification.name}"


class TranslationLanguage(models.Model):
    """Languages spoken by translator with proficiency levels."""
    
    PROFICIENCY_LEVEL_CHOICES = [
        ('Native', _('Native')),
        ('Fluent', _('Fluent')),
        ('Advanced', _('Advanced')),
        ('Intermediate', _('Intermediate')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='languages'
    )
    language_code = models.CharField(max_length=10)
    proficiency_level = models.CharField(
        max_length=20, 
        choices=PROFICIENCY_LEVEL_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'translator_language'
        verbose_name = _('Translation Language')
        verbose_name_plural = _('Translation Languages')
        unique_together = ['translator', 'language_code']
        ordering = ['proficiency_level', 'language_code']
        indexes = [
            models.Index(fields=['translator', 'language_code']),
            models.Index(fields=['language_code']),
        ]

    def __str__(self):
        return f"{self.translator.user.get_full_name()} - {self.language_code} ({self.proficiency_level})"

    def clean(self):
        """Validate language code format."""
        if self.language_code and not self.language_code.isalpha():
            raise ValidationError({
                'language_code': _('Language code must contain only alphabetic characters.')
            })


class TranslationFee(models.Model):
    """Service fees configured by translator."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='fees'
    )
    service_fee = models.ForeignKey(
        ServiceFee, 
        on_delete=models.CASCADE,
        related_name='translator_fees'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'translator_fee'
        verbose_name = _('Translation Fee')
        verbose_name_plural = _('Translation Fees')
        unique_together = ['translator', 'service_fee']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['translator', '-created_at']),
        ]

    def __str__(self):
        return f"{self.translator.user.get_full_name()} - Fee"


class TranslatorAvailability(models.Model):
    """Availability slots for translator scheduling."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='availabilities'
    )
    availability_slot = models.ForeignKey(
        AvailabilitySlot, 
        on_delete=models.CASCADE,
        related_name='translator_availabilities'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'translator_availability'
        verbose_name = _('Translator Availability')
        verbose_name_plural = _('Translator Availabilities')
        unique_together = ['translator', 'availability_slot']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['translator', '-created_at']),
        ]

    def __str__(self):
        return f"{self.translator.user.get_full_name()} - Availability"


class TranslatorReview(models.Model):
    """Patient reviews for translators."""
    
    STATUS_CHOICES = [
        ('Published', _('Published')),
        ('Hidden', _('Hidden')),
        ('Flagged', _('Flagged')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'patients.Profile', 
        on_delete=models.CASCADE, 
        related_name='translator_reviews'
    )
    translator = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    appointment = models.ForeignKey(
        'patients.Appointment', 
        on_delete=models.CASCADE,
        related_name='translator_reviews'
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Published'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='updated_translator_reviews'
    )

    class Meta:
        db_table = 'translator_review'
        verbose_name = _('Translator Review')
        verbose_name_plural = _('Translator Reviews')
        unique_together = ['patient', 'translator', 'appointment']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['translator', 'status']),
            models.Index(fields=['translator', '-created_at']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f"Review by {self.patient.user.get_full_name()} for {self.translator.user.get_full_name()} - {self.rating}★"

    def clean(self):
        """Validate review constraints."""
        if self.rating and not (1 <= self.rating <= 5):
            raise ValidationError({
                'rating': _('Rating must be between 1 and 5.')
            })
        
        # Ensure patient can only review after appointment
        if self.appointment_id and self.patient_id:
            if self.appointment.patient_id != self.patient_id:
                raise ValidationError({
                    'appointment': _('Review appointment must belong to the patient.')
                })