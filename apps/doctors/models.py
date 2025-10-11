from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


class Profile(models.Model):
    """Doctor profile with professional information."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('base.User', on_delete=models.CASCADE, related_name='doctor_profile')
    about = models.TextField(blank=True)
    specialization = models.CharField(max_length=255, blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    license_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('doctor profile')
        verbose_name_plural = _('doctor profiles')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['specialization']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Dr. {self.user.get_full_name()}"

    def clean(self):
        """Validate years of experience."""
        if self.years_of_experience < 0 or self.years_of_experience > 100:
            raise ValidationError(_('Years of experience must be between 0 and 100.'))


# class DoctorExperience(models.Model):
#     """Link table between doctors and their experiences."""
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     doctor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='doctor_experiences')
#     experience = models.ForeignKey('base.Experience', on_delete=models.CASCADE, related_name='doctor_experiences')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         verbose_name = _('doctor experience')
#         verbose_name_plural = _('doctor experiences')
#         unique_together = [['doctor', 'experience']]
#         indexes = [
#             models.Index(fields=['doctor']),
#         ]
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.doctor.user.get_full_name()} - {self.experience.title}"


# class DoctorEducation(models.Model):
#     """Link table between doctors and their education."""
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     doctor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='doctor_educations')
#     education = models.ForeignKey('base.Education', on_delete=models.CASCADE, related_name='doctor_educations')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         verbose_name = _('doctor education')
#         verbose_name_plural = _('doctor educations')
#         unique_together = [['doctor', 'education']]
#         indexes = [
#             models.Index(fields=['doctor']),
#         ]
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.doctor.user.get_full_name()} - {self.education.degree}"


# class DoctorCertification(models.Model):
#     """Link table between doctors and their certifications."""
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     doctor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='doctor_certifications')
#     certification = models.ForeignKey('base.Certification', on_delete=models.CASCADE, related_name='doctor_certifications')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         verbose_name = _('doctor certification')
#         verbose_name_plural = _('doctor certifications')
#         unique_together = [['doctor', 'certification']]
#         indexes = [
#             models.Index(fields=['doctor']),
#         ]
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.doctor.user.get_full_name()} - {self.certification.title}"


# class ConsultationFee(models.Model):
#     """Consultation fees for doctors based on service fees."""
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     doctor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='consultation_fees')
#     service_fee = models.ForeignKey('base.ServiceFee', on_delete=models.CASCADE, related_name='consultation_fees')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name = _('consultation fee')
#         verbose_name_plural = _('consultation fees')
#         unique_together = [['doctor', 'service_fee']]
#         indexes = [
#             models.Index(fields=['doctor']),
#         ]
#         ordering = ['service_fee__duration']

#     def __str__(self):
#         return f"{self.doctor.user.get_full_name()} - {self.service_fee.get_duration_display()}"


# class DoctorAvailability(models.Model):
#     """Doctor availability based on availability slots."""
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     doctor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='doctor_availabilities')
#     availability_slot = models.ForeignKey('base.AvailabilitySlot', on_delete=models.CASCADE, related_name='doctor_availabilities')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name = _('doctor availability')
#         verbose_name_plural = _('doctor availabilities')
#         unique_together = [['doctor', 'availability_slot']]
#         indexes = [
#             models.Index(fields=['doctor']),
#         ]
#         ordering = ['availability_slot__day_of_week', 'availability_slot__start_time']

#     def __str__(self):
#         return f"{self.doctor.user.get_full_name()} - {self.availability_slot}"


class Prescription(models.Model):
    """Medical prescription issued by doctor."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey('patients.Case', on_delete=models.CASCADE, related_name='prescriptions')
    appointment = models.ForeignKey('patients.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions')
    title = models.CharField(max_length=255)
    start_date = models.DateField(default=timezone.now)
    course_duration_days = models.PositiveIntegerField()
    instructions = models.TextField(blank=True)
    created_by = models.ForeignKey('base.User', on_delete=models.SET_NULL, null=True, related_name='prescriptions_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('prescription')
        verbose_name_plural = _('prescriptions')
        indexes = [
            models.Index(fields=['case']),
            models.Index(fields=['appointment']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.case.title}"

    def clean(self):
        """Validate prescription data."""
        if self.course_duration_days < 1 or self.course_duration_days > 365:
            raise ValidationError(_('Course duration must be between 1 and 365 days.'))
        
        if self.appointment and self.appointment.case != self.case:
            raise ValidationError(_('Appointment must belong to the specified case.'))


class PrescriptionItem(models.Model):
    """Individual medicine item in a prescription."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    medicine_name = models.CharField(max_length=255)
    frequency = models.CharField(max_length=100, help_text=_('e.g., Twice daily, Every 6 hours'))
    dosage_amount = models.CharField(max_length=100, help_text=_('e.g., 500mg, 2 tablets'))
    instructions = models.TextField(blank=True, help_text=_('e.g., Take with food'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('prescription item')
        verbose_name_plural = _('prescription items')
        indexes = [
            models.Index(fields=['prescription']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.medicine_name} - {self.dosage_amount}"


class DoctorReview(models.Model):
    """Patient reviews for doctors."""
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Published', 'Published'),
        ('Hidden', 'Hidden'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey('patients.Profile', on_delete=models.CASCADE, related_name='reviews_given')
    doctor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reviews')
    appointment = models.ForeignKey('patients.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    rating = models.PositiveSmallIntegerField(help_text=_('Rating from 1 to 5'))
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    updated_by = models.ForeignKey('base.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews_moderated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('doctor review')
        verbose_name_plural = _('doctor reviews')
        unique_together = [['patient', 'doctor', 'appointment']]
        indexes = [
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['patient']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient.user.get_full_name()} -> Dr. {self.doctor.user.get_full_name()} ({self.rating}/5)"

    def clean(self):
        """Validate review data."""
        if self.rating < 1 or self.rating > 5:
            raise ValidationError(_('Rating must be between 1 and 5.'))
        
        if self.appointment:
            if self.appointment.case.patient != self.patient:
                raise ValidationError(_('Appointment must belong to the reviewing patient.'))
            
            if self.appointment.time_slot.doctor != self.doctor:
                raise ValidationError(_('Appointment must be with the reviewed doctor.'))