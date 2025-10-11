from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    Profile, MedicalHistory, Case, AppointmentTimeSlot, Appointment, Report
)
from apps.base.models import AvailabilitySlot
from apps.base.serializers import UserSerializer
from apps.files.serializers import FileSerializer
from apps.translators.models import Profile as TranslatorProfile
from apps.files.models import File



class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for patient profiles."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'user_id', 'emergency_contact_name',
            'emergency_contact_phone', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class MedicalHistorySerializer(serializers.ModelSerializer):
    """Serializer for medical history records."""
    
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)

    class Meta:
        model = MedicalHistory
        fields = [
            'id', 'patient', 'patient_name', 'type', 'title', 'description',
            'diagnosed_date', 'is_active', 'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at']

    def validate_diagnosed_date(self, value):
        """Ensure diagnosed date is not in the future."""
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Diagnosed date cannot be in the future.")
        return value


class DoctorBasicSerializer(serializers.Serializer):
    """Basic doctor information for nested serialization."""
    
    id = serializers.UUIDField()
    user = UserSerializer()

class CaseSerializer(serializers.ModelSerializer):
    """Serializer for medical cases."""
    
    patient = ProfileSerializer(read_only=True)
    patient_id = serializers.UUIDField(write_only=True, required=False)
    doctor = DoctorBasicSerializer(read_only=True)
    doctor_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    created_by = UserSerializer(read_only=True)
    closed_by = UserSerializer(read_only=True)
    appointments_count = serializers.IntegerField(source='appointments.count', read_only=True)

    class Meta:
        model = Case
        fields = [
            'id', 'title', 'patient', 'patient_id', 'doctor', 'doctor_id',
            'description', 'status', 'created_by', 'closed_by',
            'created_at', 'updated_at', 'closed_at', 'appointments_count'
        ]
        read_only_fields = ['id', 'patient', 'created_by', 'closed_by', 'created_at', 'updated_at', 'closed_at']

    def validate_status(self, value):
        """Validate status transitions."""
        if self.instance and self.instance.status == 'Closed' and value != 'Closed':
            raise serializers.ValidationError("Cannot reopen a closed case.")
        return value

    def create(self, validated_data):
        """Handle case creation with automatic patient assignment."""
        request = self.context.get('request')
        
        # If patient_id is not provided, get it from the authenticated user
        if 'patient_id' not in validated_data:
            try:
                patient_profile = Profile.objects.get(user=request.user)
                validated_data['patient_id'] = patient_profile.id
            except Profile.DoesNotExist:
                raise serializers.ValidationError({
                    'patient_id': 'Patient profile not found for the current user.'
                })
        
        # Set created_by to the current user
        validated_data['created_by'] = request.user
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Handle case closure logic."""
        if validated_data.get('status') == 'Closed' and instance.status != 'Closed':
            validated_data['closed_at'] = timezone.now()
            validated_data['closed_by'] = self.context['request'].user
        return super().update(instance, validated_data)

class AppointmentTimeSlotSerializer(serializers.ModelSerializer):
    """Serializer for appointment time slots."""
    
    case_title = serializers.CharField(source='case.title', read_only=True)
    patient_name = serializers.CharField(source='case.patient.user.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='case.doctor.user.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    end_time = serializers.TimeField(read_only=True)
    duration_display = serializers.CharField(source='get_duration_display', read_only=True)

    class Meta:
        model = AppointmentTimeSlot
        fields = [
            'id', 'case', 'case_title', 'patient_name', 'doctor_name',
            'created_by', 'created_by_name', 'date', 'start_time',
            'end_time', 'duration', 'duration_display', 'timezone',
            'is_booked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_booked', 'created_by', 'created_at', 'updated_at']

    def validate_date(self, value):
        """Ensure date is not in the past."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Cannot create time slot for past dates.")
        return value

    def validate(self, attrs):
        """Validate time slot doesn't overlap and falls within doctor's availability."""
        case = attrs.get('case')
        date = attrs.get('date')
        start_time = attrs.get('start_time')
        duration = attrs.get('duration', 0)

        if not all([case, date, start_time, duration]):
            return attrs

        # Get the doctor from the case
        if not case.doctor:
            raise serializers.ValidationError("Case must have an assigned doctor to create time slots.")

        doctor = case.doctor

        # Calculate end time
        start_datetime = datetime.combine(date, start_time)
        end_datetime = start_datetime + timedelta(minutes=duration)
        end_time = end_datetime.time()

        # Get the day of week (0=Sunday, 1=Monday, etc.)
        day_of_week = date.weekday()
        # Python's weekday() returns 0=Monday, 6=Sunday, so convert to match DAY_CHOICES
        day_of_week = (day_of_week + 1) % 7  # Convert to 0=Sunday format

        # Check if doctor is available on this day and time
        availability_slots = AvailabilitySlot.objects.filter(
            user=doctor.user,
            day_of_week=day_of_week,
            is_active=True
        )

        if not availability_slots.exists():
            day_name = dict(AvailabilitySlot.DAY_CHOICES)[day_of_week]
            raise serializers.ValidationError(
                f"Doctor is not available on {day_name}s."
            )

        # Check if the time slot falls within any availability slot
        is_within_availability = False
        for slot in availability_slots:
            # Check if appointment start_time and end_time are within this availability slot
            if slot.start_time <= start_time < slot.end_time and slot.start_time < end_time <= slot.end_time:
                is_within_availability = True
                break

        if not is_within_availability:
            raise serializers.ValidationError(
                f"The selected time ({start_time} - {end_time}) is not within doctor's available hours. "
                f"Please check the doctor's availability schedule."
            )

        # Check for overlapping slots for the same case
        overlapping = AppointmentTimeSlot.objects.filter(
            case=case,
            date=date,
        ).exclude(pk=self.instance.pk if self.instance else None)

        for slot in overlapping:
            slot_end = datetime.combine(date, slot.start_time) + timedelta(minutes=slot.duration)
            slot_end_time = slot_end.time()
            
            # Check if times overlap
            if not (end_time <= slot.start_time or start_time >= slot_end_time):
                raise serializers.ValidationError("Time slot overlaps with existing appointment.")

        return attrs

class TranslatorBasicSerializer(serializers.Serializer):
    """Basic translator information for nested serialization."""
    
    id = serializers.UUIDField()
    user = UserSerializer()


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for appointments."""
    
    case = CaseSerializer(read_only=True)
    case_id = serializers.UUIDField(write_only=True)
    time_slot = AppointmentTimeSlotSerializer(read_only=True)
    time_slot_id = serializers.UUIDField(write_only=True)
    translator = TranslatorBasicSerializer(read_only=True)
    translator_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    cancelled_by = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'case', 'case_id', 'time_slot', 'time_slot_id', 'status', 'status_display',
            'cancelled_by', 'cancellation_reason', 'is_translator_required',
            'translator_status', 'translator', 'translator_id', 'is_follow_up',
            'reason_for_visit', 'special_requests', 'doctor_notes',
            'appointment_number', 'created_by', 'created_at', 'updated_at',
            'conducted_at', 'cancelled_at'
        ]
        read_only_fields = [
            'id', 'appointment_number', 'cancelled_by', 'created_by',
            'created_at', 'updated_at', 'conducted_at', 'cancelled_at'
        ]

    def validate_time_slot_id(self, value):
        """Ensure time slot exists and is available."""
        try:
            slot = AppointmentTimeSlot.objects.get(pk=value)
            if slot.is_booked and not self.instance:
                raise serializers.ValidationError("This time slot is already booked.")
            if slot.date < timezone.now().date():
                raise serializers.ValidationError("Cannot book appointments for past dates.")
            return value
        except AppointmentTimeSlot.DoesNotExist:
            raise serializers.ValidationError("Time slot not found.")

    def validate(self, attrs):
        """Validate translator requirements."""
        is_translator_required = attrs.get('is_translator_required', False)
        translator_status = attrs.get('translator_status')
        
        if is_translator_required and translator_status == 'Not Needed':
            attrs['translator_status'] = 'Pending'
        elif not is_translator_required:
            attrs['translator_status'] = 'Not Needed'
            attrs['translator'] = None
        
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create appointment and mark slot as booked."""
        case_id = validated_data.pop('case_id')
        time_slot_id = validated_data.pop('time_slot_id')
        translator_id = validated_data.pop('translator_id', None)
        
        # Get the actual objects
        case = Case.objects.get(pk=case_id)
        time_slot = AppointmentTimeSlot.objects.get(pk=time_slot_id)
        translator = TranslatorProfile.objects.get(pk=translator_id) if translator_id else None
        
        # Auto-increment appointment number
        last_appointment = case.appointments.order_by('-appointment_number').first()
        appointment_number = (last_appointment.appointment_number + 1) if last_appointment else 1
        
        # Mark slot as booked
        time_slot.is_booked = True
        time_slot.save(update_fields=['is_booked'])
        
        # Create the appointment with the actual objects
        appointment = Appointment.objects.create(
            case=case,
            time_slot=time_slot,
            translator=translator,
            appointment_number=appointment_number,
            **validated_data
        )
        
        return appointment

class ReportSerializer(serializers.ModelSerializer):
    """Serializer for medical reports."""
    
    case = CaseSerializer(read_only=True)  # Add this line
    case_title = serializers.CharField(source='case.title', read_only=True)
    case_id = serializers.UUIDField(write_only=True)
    appointment = AppointmentSerializer(read_only=True)  # Add this line
    appointment_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    file = FileSerializer(read_only=True)
    file_id = serializers.UUIDField(write_only=True)
    uploaded_by = UserSerializer(read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'case', 'case_id', 'case_title', 'appointment', 'appointment_id',
            'title', 'description', 'file', 'file_id', 'report_type',
            'report_type_display', 'uploaded_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uploaded_by', 'created_at', 'updated_at']

    def validate_case_id(self, value):
        """Ensure case exists."""
        try:
            Case.objects.get(pk=value)
            return value
        except Case.DoesNotExist:
            raise serializers.ValidationError("Case not found.")

    def validate_file_id(self, value):
        """Ensure file exists."""
        try:
            File.objects.get(pk=value)
            return value
        except File.DoesNotExist:
            raise serializers.ValidationError("File not found.")

    def validate(self, attrs):
        """Ensure appointment belongs to case if provided."""
        appointment_id = attrs.get('appointment_id')  # Changed from 'appointment'
        case_id = attrs.get('case_id')  # Changed from 'case'
        
        if appointment_id and case_id:
            try:
                appointment = Appointment.objects.get(pk=appointment_id)
                if str(appointment.case_id) != str(case_id):  # Convert to string for comparison
                    raise serializers.ValidationError("Appointment does not belong to the specified case.")
            except Appointment.DoesNotExist:
                raise serializers.ValidationError("Appointment not found.")
        
        return attrs

    def create(self, validated_data):
        """Create report with proper object references."""
        case_id = validated_data.pop('case_id')
        file_id = validated_data.pop('file_id')
        appointment_id = validated_data.pop('appointment_id', None)
        
        # Get the actual objects
        case = Case.objects.get(pk=case_id)
        file = File.objects.get(pk=file_id)
        appointment = Appointment.objects.get(pk=appointment_id) if appointment_id else None
        
        # Create the report
        report = Report.objects.create(
            case=case,
            file=file,
            appointment=appointment,
            **validated_data
        )
        
        return report