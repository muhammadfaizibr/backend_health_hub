from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid

from apps.base.models import User
from apps.doctors.models import Profile as DoctorProfile
from apps.translators.models import Profile as TranslatorProfile
import secrets


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
        ('rescheduling_requested', 'Rescheduling Requested'),
        ('in_progress', 'In Progress'),
        ('conducted', 'Conducted'),
        ('cancelled', 'Cancelled'),
    ]

    TRANSLATOR_STATUS_CHOICES = [
        ('not_needed', 'Not Needed'),
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey('patients.Case', on_delete=models.CASCADE, related_name='appointments')
    time_slot = models.OneToOneField('patients.AppointmentTimeSlot', on_delete=models.CASCADE, related_name='appointment')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_confirmation')
    
    # Join tracking
    patient_joined = models.BooleanField(default=False)
    doctor_joined = models.BooleanField(default=False)
    translator_joined = models.BooleanField(default=False)
    patient_joined_at = models.DateTimeField(null=True, blank=True)
    doctor_joined_at = models.DateTimeField(null=True, blank=True)
    translator_joined_at = models.DateTimeField(null=True, blank=True)
    
    # Meeting link
    meeting_link = models.CharField(max_length=500, blank=True)
    
    cancelled_by = models.ForeignKey('base.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments_cancelled')
    cancellation_reason = models.TextField(blank=True)
    is_translator_required = models.BooleanField(default=False)
    translator_status = models.CharField(max_length=20, choices=TRANSLATOR_STATUS_CHOICES, default='not_needed')
    translator = models.ForeignKey('translators.Profile', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_appointments')
    is_follow_up = models.BooleanField(default=False)
    reason_for_visit = models.TextField()
    special_requests = models.TextField(blank=True)
    doctor_notes = models.TextField(blank=True)
    appointment_number = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey('base.User', on_delete=models.SET_NULL, null=True, related_name='appointments_created')
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
            models.Index(fields=['patient_joined', 'doctor_joined', 'translator_joined']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Appointment #{self.appointment_number} - {self.case.title}"

    def save(self, *args, **kwargs):
        if not self.meeting_link:
            self.meeting_link = self.generate_meeting_link()
        super().save(*args, **kwargs)

    def generate_meeting_link(self):
        """Generate a dummy meeting link."""
        token = secrets.token_urlsafe(32)
        return f"https://meet.telemedicine.com/session/{token}"

    def clean(self):
        """Validate appointment data."""
        if self.time_slot and self.time_slot.is_booked and not self.pk:
            raise ValidationError(_('This time slot is already booked.'))
        
        if self.is_translator_required and self.translator_status == 'not_needed':
            self.translator_status = 'pending'
        
        if not self.is_translator_required:
            self.translator_status = 'not_needed'
            self.translator = None

    def is_join_button_enabled(self):
        """Check if join button should be enabled (5 mins before to 10 mins after start)."""
        if not self.time_slot:
            return False
        
        from datetime import datetime, timedelta
        
        appointment_datetime = datetime.combine(
            self.time_slot.date, 
            self.time_slot.start_time
        )
        
        if timezone.is_naive(appointment_datetime):
            appointment_datetime = timezone.make_aware(appointment_datetime)
        
        now = timezone.now()
        
        enable_time = appointment_datetime - timedelta(minutes=5)
        disable_time = appointment_datetime + timedelta(minutes=10)
        
        return enable_time <= now <= disable_time

    def get_join_status_display(self):
        """Get human-readable join status."""
        if self.status == 'conducted':
            return 'Conducted'
        elif self.status == 'in_progress':
            return 'In Progress'
        elif self.patient_joined or self.doctor_joined or self.translator_joined:
            return 'Participants Joining'
        return self.get_status_display()

    # apps/patients/models.py

    def check_and_update_status(self):
        """Check join status and update appointment status accordingly."""
        from datetime import datetime, timedelta
        
        if self.status in ['conducted', 'cancelled']:
            return
        
        appointment_datetime = datetime.combine(
            self.time_slot.date, 
            self.time_slot.start_time
        )
        
        if timezone.is_naive(appointment_datetime):
            appointment_datetime = timezone.make_aware(appointment_datetime)
        
        appointment_end = appointment_datetime + timedelta(minutes=self.time_slot.duration)
        now = timezone.now()
        
        # Check if patient and doctor have joined
        if self.patient_joined and self.doctor_joined:
            # If translator is required, check if translator joined
            if self.is_translator_required:
                # If translator has joined, mark as in_progress
                # If translator hasn't joined but time hasn't ended, still in_progress
                # Both cases are handled the same way
                if now < appointment_end:
                    self.status = 'in_progress'
                else:
                    # Time ended, mark as conducted regardless of translator join status
                    self.status = 'conducted'
                    if not self.conducted_at:
                        self.conducted_at = now
            else:
                # No translator required, just patient and doctor
                if now < appointment_end:
                    self.status = 'in_progress'
                else:
                    self.status = 'conducted'
                    if not self.conducted_at:
                        self.conducted_at = now
        
        # If appointment time has ended and someone joined
        elif now > appointment_end and (self.patient_joined or self.doctor_joined):
            self.status = 'conducted'
            if not self.conducted_at:
                self.conducted_at = now
        
        self.save(update_fields=['status', 'conducted_at', 'updated_at'])

    def get_frontend_status_display(self):
        """Get status for frontend display."""
        if self.status == 'in_progress':
            return 'Going On / Happening Now'
        elif self.status == 'conducted':
            return 'Conducted'
        return self.get_status_display()


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