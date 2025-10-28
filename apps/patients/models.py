from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid

from apps.base.models import User
from apps.doctors.models import Profile as DoctorProfile
from apps.translators.models import Profile as TranslatorProfile


class Profile(models.Model):
    """Patient profile with emergency contact information."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('patient profile')
        verbose_name_plural = _('patient profiles')
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Patient: {self.user.get_full_name()}"


class MedicalHistory(models.Model):
    """Medical history records for patients."""
    
    TYPE_CHOICES = [
        ('chronic_condition', 'Chronic Condition'),
        ('allergy', 'Allergy'),
        ('surgery', 'Surgery'),
        ('hospitalization', 'Hospitalization'),
        ('medication', 'Medication'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='medical_history')
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    diagnosed_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='medical_histories_created', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='medical_histories_updated', null=True, blank=True)

    class Meta:
        verbose_name = _('medical history')
        verbose_name_plural = _('medical histories')
        indexes = [
            models.Index(fields=['patient', 'type']),
            models.Index(fields=['patient', 'is_active']),
        ]
        ordering = ['-diagnosed_date', '-created_at']

    def __str__(self):
        return f"{self.patient.user.get_full_name()} - {self.type}: {self.title}"


class Case(models.Model):
    """Medical case for tracking patient treatment."""
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    patient = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='cases')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cases')
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='cases_created', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='cases_closed', null=True, blank=True)

    class Meta:
        verbose_name = _('case')
        verbose_name_plural = _('cases')
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.patient.user.get_full_name()}"

    def clean(self):
        """Validate case status transitions."""
        if self.status == 'Closed' and not self.closed_at:
            self.closed_at = timezone.now()

class AppointmentTimeSlot(models.Model):
    """Available time slots for appointments."""
    
    DURATION_CHOICES = [
        (15, '15 minutes'),
        (30, '30 minutes'),
        (45, '45 minutes'),
        (60, '60 minutes'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='time_slots')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_time_slots')
    date = models.DateField()
    start_time = models.TimeField()
    duration = models.IntegerField(choices=DURATION_CHOICES)
    timezone = models.CharField(max_length=50, default='UTC')
    is_booked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('appointment time slot')
        verbose_name_plural = _('appointment time slots')
        unique_together = [['case', 'date', 'start_time']]
        indexes = [
            models.Index(fields=['case', 'date']),
            models.Index(fields=['case', 'date', 'is_booked']),
            models.Index(fields=['date', 'is_booked']),
            models.Index(fields=['created_by']),
        ]
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.case.title} - {self.date} {self.start_time}"

    def clean(self):
        """Validate time slot."""
        if self.date and self.date < timezone.now().date():
            raise ValidationError(_('Cannot create time slot in the past.'))

    @property
    def end_time(self):
        """Calculate end time based on start time and duration."""
        from datetime import datetime, timedelta
        start_datetime = datetime.combine(self.date, self.start_time)
        end_datetime = start_datetime + timedelta(minutes=self.duration)
        return end_datetime.time()
    
class Appointment(models.Model):
    """Patient appointment with doctor."""
    
    STATUS_CHOICES = [
        ('pending_confirmation', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('rescheduling Requested', 'Rescheduling Requested'),
        ('conducted', 'Conducted'),
        ('cancelled', 'Cancelled'),
    ]

    TRANSLATOR_STATUS_CHOICES = [
        ('not_needed', 'Not Needed'),
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='appointments')
    time_slot = models.OneToOneField(AppointmentTimeSlot, on_delete=models.CASCADE, related_name='appointment')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending Confirmation')
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments_cancelled')
    cancellation_reason = models.TextField(blank=True)
    is_translator_required = models.BooleanField(default=False)
    translator_status = models.CharField(max_length=20, choices=TRANSLATOR_STATUS_CHOICES, default='Not Needed')
    translator = models.ForeignKey(TranslatorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_appointments')
    is_follow_up = models.BooleanField(default=False)
    reason_for_visit = models.TextField()
    special_requests = models.TextField(blank=True)
    doctor_notes = models.TextField(blank=True)
    appointment_number = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='appointments_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    conducted_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _('appointment')
        verbose_name_plural = _('appointments')
        indexes = [
            models.Index(fields=['case', 'status']),
            models.Index(fields=['time_slot']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Appointment #{self.appointment_number} - {self.case.title}"

    def clean(self):
        """Validate appointment data."""
        if self.time_slot and self.time_slot.is_booked and not self.pk:
            raise ValidationError(_('This time slot is already booked.'))
        
        if self.is_translator_required and self.translator_status == 'Not Needed':
            self.translator_status = 'Pending'
        
        if not self.is_translator_required:
            self.translator_status = 'Not Needed'
            self.translator = None


class Report(models.Model):
    """Medical reports and documents for cases."""
    
    REPORT_TYPE_CHOICES = [
        ('lab_result', 'lab_result'),
        ('imaging', 'Imaging'),
        ('consultation_note', 'Consultation Note'),
        ('discharge_summary', 'Discharge Summary'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='reports')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.ForeignKey('files.File', on_delete=models.CASCADE, related_name='medical_reports')
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reports_uploaded')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('report')
        verbose_name_plural = _('reports')
        indexes = [
            models.Index(fields=['case', 'report_type']),
            models.Index(fields=['case', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.case.title}"