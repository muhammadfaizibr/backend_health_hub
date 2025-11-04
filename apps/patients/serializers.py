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
from apps.doctors.models import Profile as DoctorProfile
from apps.translators.models import Profile as TranslatorProfile
from apps.files.models import File
from apps.payments.models import AppointmentBilling, WalletLedger
from apps.base.models import Wallet
from decimal import Decimal



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
    join_status_display = serializers.CharField(source='get_join_status_display', read_only=True)
    is_join_enabled = serializers.SerializerMethodField()

    frontend_status = serializers.SerializerMethodField()
    billing_info = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'case', 'case_id', 'time_slot', 'time_slot_id', 'status', 
            'status_display', 'frontend_status', 'join_status_display', 
            'is_join_enabled', 'cancelled_by', 'cancellation_reason',
            'is_translator_required', 'translator_status', 'translator', 'translator_id',
            'is_follow_up', 'reason_for_visit', 'special_requests', 'doctor_notes',
            'appointment_number', 'created_by', 'created_at', 'updated_at',
            'conducted_at', 'cancelled_at', 'meeting_link',
            'patient_joined', 'doctor_joined', 'translator_joined',
            'patient_joined_at', 'doctor_joined_at', 'translator_joined_at',
            'billing_info'
        ]
        read_only_fields = [
            'id', 'appointment_number', 'cancelled_by', 'created_by',
            'created_at', 'updated_at', 'conducted_at', 'cancelled_at',
            'meeting_link', 'patient_joined_at', 'doctor_joined_at', 
            'translator_joined_at', 'billing_info'
        ]
    
    def get_frontend_status(self, obj):
        return obj.get_frontend_status_display()
    
    def get_is_join_enabled(self, obj):
        """Check if the join button should be enabled for this appointment."""
        return obj.is_join_button_enabled()
    
    def get_billing_info(self, obj):
        if hasattr(obj, 'billing'):
            return {
                'id': str(obj.billing.id),
                'total_amount': str(obj.billing.total_amount),
                'status': obj.billing.status,
                'organization': obj.billing.organization.user.email if obj.billing.organization else None
            }
        return None

# apps/patients/serializers.py

class JoinAppointmentSerializer(serializers.Serializer):
    """Serializer for joining an appointment."""
    
    participant_type = serializers.ChoiceField(
        choices=['patient', 'doctor', 'translator'],
        required=True
    )

    @transaction.atomic
    def update(self, instance, validated_data):
        participant_type = validated_data['participant_type']
        now = timezone.now()
        
        # Update join status
        if participant_type == 'patient':
            if not instance.patient_joined:
                instance.patient_joined = True
                instance.patient_joined_at = now
        elif participant_type == 'doctor':
            if not instance.doctor_joined:
                instance.doctor_joined = True
                instance.doctor_joined_at = now
        elif participant_type == 'translator':
            if not instance.translator_joined:
                instance.translator_joined = True
                instance.translator_joined_at = now
        
        instance.save()
        
        # Process payments ONLY if patient has joined
        if instance.patient_joined:
            self._process_payments(instance)
        
        # Update appointment status
        instance.check_and_update_status()
        
        return instance

    def _process_payments(self, appointment):
        """Process payments when patient has joined."""
        from apps.payments.models import AppointmentBilling, WalletLedger
        from apps.organization.models import Profile as OrganizationProfile
        from apps.base.models import Wallet
        from decimal import Decimal
        
        # Check if billing already exists and is not draft
        if hasattr(appointment, 'billing') and appointment.billing.status != 'draft':
            return
        
        # Get doctor fee
        doctor = appointment.case.doctor
        doctor_fee = Decimal('0.00')
        doctor_service_fees = doctor.user.service_fees.filter(is_active=True).first()
        if doctor_service_fees:
            doctor_fee = doctor_service_fees.fee
        
        # Get translator fee if required and assigned
        translator_fee = Decimal('0.00')
        if appointment.is_translator_required and appointment.translator:
            translator_service_fees = appointment.translator.user.service_fees.filter(
                is_active=True
            ).first()
            if translator_service_fees:
                translator_fee = translator_service_fees.fee
        
        # Calculate platform fee (5%)
        total_service_fee = doctor_fee + translator_fee
        platform_fee_percentage = Decimal('5.00')
        platform_fee = (total_service_fee * platform_fee_percentage / 100).quantize(Decimal('0.01'))
        total_amount = doctor_fee + translator_fee + platform_fee
        
        # Find organization with enough credits
        organization = OrganizationProfile.objects.select_for_update().filter(
            current_credits_balance__gte=total_amount,
        ).order_by('total_appointments_processed', '-current_credits_balance').first()
        
        if not organization:
            raise serializers.ValidationError({
                "detail": "No organization available with sufficient credits."
            })
        
        # Get or create billing record
        billing, created = AppointmentBilling.objects.get_or_create(
            appointment=appointment,
            defaults={
                'organization': organization,
                'doctor': doctor,
                'translator': appointment.translator if appointment.is_translator_required else None,
                'doctor_fee': doctor_fee,
                'translator_fee': translator_fee,
                'platform_fee': platform_fee,
                'platform_fee_percentage': platform_fee_percentage,
                'total_amount': total_amount,
                'currency': 'PKR',
                'status': 'draft'
            }
        )
        
        if not created:
            # Update existing billing if needed
            billing.translator = appointment.translator if appointment.is_translator_required else None
            billing.translator_fee = translator_fee
            billing.platform_fee = platform_fee
            billing.total_amount = total_amount
            billing.save()
        
        # Create wallet entries only if patient and doctor have joined
        if appointment.patient_joined and appointment.doctor_joined:
            self._create_doctor_payment(appointment, billing, doctor_fee)
            
            # Create translator payment only if translator is required AND has joined
            if appointment.is_translator_required and appointment.translator and appointment.translator_joined:
                self._create_translator_payment(appointment, billing, translator_fee)
    
    def _create_doctor_payment(self, appointment, billing, doctor_fee):
        """Create pending wallet entry for doctor."""
        from apps.payments.models import WalletLedger
        from apps.base.models import Wallet
        from datetime import timedelta
        
        doctor = appointment.case.doctor
        doctor_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=doctor.user)
        
        # Check if ledger entry already exists
        existing_ledger = WalletLedger.objects.filter(
            wallet=doctor_wallet,
            related_appointment=appointment,
            related_billing=billing,
            transaction_type='earning'
        ).exists()
        
        if not existing_ledger:
            # Create pending wallet entry (available after 3 days)
            available_at = timezone.now() + timedelta(days=3)
            
            WalletLedger.objects.create(
                wallet=doctor_wallet,
                transaction_type='earning',
                amount=doctor_fee,
                balance_before=doctor_wallet.pending_balance,
                balance_after=doctor_wallet.pending_balance + doctor_fee,
                balance_type='pending',
                status='pending',
                related_appointment=appointment,
                related_billing=billing,
                description=f'Earning from Appointment #{appointment.appointment_number}',
                available_at=available_at
            )
            
            # Update wallet balances
            doctor_wallet.pending_balance += doctor_fee
            doctor_wallet.total_lifetime_earnings += doctor_fee
            doctor_wallet.save()
            
            # Deduct from organization
            self._deduct_from_organization(billing, doctor_fee, appointment, 'doctor')
    
    def _create_translator_payment(self, appointment, billing, translator_fee):
        """Create pending wallet entry for translator."""
        from apps.payments.models import WalletLedger
        from apps.base.models import Wallet
        from datetime import timedelta
        
        if not appointment.translator:
            return
        
        translator_wallet, _ = Wallet.objects.select_for_update().get_or_create(
            user=appointment.translator.user
        )
        
        # Check if ledger entry already exists
        existing_ledger = WalletLedger.objects.filter(
            wallet=translator_wallet,
            related_appointment=appointment,
            related_billing=billing,
            transaction_type='earning'
        ).exists()
        
        if not existing_ledger:
            # Create pending wallet entry (available after 3 days)
            available_at = timezone.now() + timedelta(days=3)
            
            WalletLedger.objects.create(
                wallet=translator_wallet,
                transaction_type='earning',
                amount=translator_fee,
                balance_before=translator_wallet.pending_balance,
                balance_after=translator_wallet.pending_balance + translator_fee,
                balance_type='pending',
                status='pending',
                related_appointment=appointment,
                related_billing=billing,
                description=f'Translation fee for Appointment #{appointment.appointment_number}',
                available_at=available_at
            )
            
            # Update wallet balances
            translator_wallet.pending_balance += translator_fee
            translator_wallet.total_lifetime_earnings += translator_fee
            translator_wallet.save()
            
            # Deduct from organization
            self._deduct_from_organization(billing, translator_fee, appointment, 'translator')
    
    def _deduct_from_organization(self, billing, amount, appointment, service_type):
        """Deduct amount from organization credits."""
        from apps.payments.models import WalletLedger
        from apps.base.models import Wallet
        
        org_wallet, _ = Wallet.objects.select_for_update().get_or_create(
            user=billing.organization.user
        )
        
        # Check if deduction already exists
        existing_deduction = WalletLedger.objects.filter(
            wallet=org_wallet,
            related_appointment=appointment,
            related_billing=billing,
            description__contains=service_type
        ).exists()
        
        if not existing_deduction:
            WalletLedger.objects.create(
                wallet=org_wallet,
                transaction_type='adjustment',
                amount=-amount,
                balance_before=org_wallet.available_balance,
                balance_after=org_wallet.available_balance - amount,
                balance_type='available',
                status='available',
                related_appointment=appointment,
                related_billing=billing,
                description=f'Payment for Appointment #{appointment.appointment_number} ({service_type})'
            )
            
            # Update organization wallet
            org_wallet.available_balance -= amount
            org_wallet.save()
            
            # Update organization credits
            org_profile = billing.organization
            org_profile.current_credits_balance -= amount
            org_profile.save()

class CreateAppointmentSerializer(serializers.Serializer):
    """Serializer for creating appointment with automatic case and time slot creation."""
    
    # Case fields (optional - will auto-create if not provided)
    case_id = serializers.UUIDField(required=False, allow_null=True)
    case_title = serializers.CharField(max_length=255, required=False)
    case_description = serializers.CharField(required=False)
    
    # Doctor (required)
    doctor_id = serializers.UUIDField(required=True)
    
    # Time slot fields
    appointment_date = serializers.DateField(required=True)
    start_time = serializers.TimeField(required=True)
    duration = serializers.IntegerField(required=True)
    timezone = serializers.CharField(max_length=50, default='UTC')
    
    # Appointment fields
    reason_for_visit = serializers.CharField(required=True)
    special_requests = serializers.CharField(required=False, allow_blank=True)
    is_translator_required = serializers.BooleanField(default=False)
    language_preference = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    is_follow_up = serializers.BooleanField(default=False)
    
    def validate_appointment_date(self, value):
        """Ensure date is not in the past."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Cannot book appointments for past dates.")
        return value
    
    def validate_duration(self, value):
        """Validate duration is one of the allowed choices."""
        allowed_durations = [choice[0] for choice in AppointmentTimeSlot.DURATION_CHOICES]
        if value not in allowed_durations:
            raise serializers.ValidationError(
                f"Duration must be one of: {', '.join(map(str, allowed_durations))} minutes."
            )
        return value
    
    def validate_doctor_id(self, value):
        """Ensure doctor exists."""
        if not DoctorProfile.objects.filter(id=value).exists():
            raise serializers.ValidationError("Doctor not found.")
        return value
    
    def validate_case_id(self, value):
        """Ensure case exists and belongs to the patient if provided."""
        if value:
            request = self.context.get('request')
            try:
                case = Case.objects.select_related('patient__user', 'doctor__user').get(id=value)
                
                # Verify case belongs to the current patient
                if request.user.role == 'Patient':
                    if case.patient.user != request.user:
                        raise serializers.ValidationError("This case does not belong to you.")
                
                # Store the case object for later use in validate()
                self._validated_case = case
                
            except Case.DoesNotExist:
                raise serializers.ValidationError("Case not found. Please verify the case ID.")
        
        return value
    
    def validate(self, attrs):
        """Comprehensive validation for the booking."""
        request = self.context.get('request')
        doctor_id = attrs['doctor_id']
        appointment_date = attrs['appointment_date']
        start_time = attrs['start_time']
        duration = attrs['duration']
        case_id = attrs.get('case_id')
        
        # Get doctor
        try:
            doctor = DoctorProfile.objects.get(id=doctor_id)
        except DoctorProfile.DoesNotExist:
            raise serializers.ValidationError({"doctor_id": "Doctor not found."})
        
        # IMPORTANT: If case_id is provided, validate that all appointments for this case are with the same doctor
        if case_id:
            # Use the case we already fetched in validate_case_id
            case = getattr(self, '_validated_case', None)
            
            if not case:
                # Fallback: fetch the case if it wasn't stored
                try:
                    case = Case.objects.select_related('patient__user', 'doctor__user').get(id=case_id)
                except Case.DoesNotExist:
                    raise serializers.ValidationError({"case_id": "Case not found."})
            
            # Check if case already has a doctor assigned and it's different from the selected doctor
            if case.doctor and case.doctor.id != doctor_id:
                raise serializers.ValidationError({
                    "doctor_id": f"This case is already assigned to Dr. {case.doctor.user.full_name}. All appointments for a case must be with the same doctor. Please select Dr. {case.doctor.user.full_name} or create a new case."
                })
            
            # Check if case has any appointments with a different doctor
            existing_appointment = case.appointments.select_related('case__doctor__user').first()
            if existing_appointment:
                existing_doctor = existing_appointment.case.doctor
                if existing_doctor and existing_doctor.id != doctor_id:
                    raise serializers.ValidationError({
                        "doctor_id": f"This case has existing appointments with Dr. {existing_doctor.user.full_name}. All appointments for a case must be with the same doctor. Please select Dr. {existing_doctor.user.full_name} or create a new case."
                    })
        
        # Calculate end time
        start_datetime = datetime.combine(appointment_date, start_time)
        end_datetime = start_datetime + timedelta(minutes=duration)
        end_time = end_datetime.time()
        
        # Check if end time goes to next day
        if end_datetime.date() != appointment_date:
            raise serializers.ValidationError({
                "start_time": "Appointment cannot extend past midnight. Please choose an earlier time."
            })
        
        # Get day of week (0=Sunday format)
        day_of_week = (appointment_date.weekday() + 1) % 7
        
        # Check doctor availability
        availability_slots = AvailabilitySlot.objects.filter(
            user=doctor.user,
            day_of_week=day_of_week,
            is_active=True
        )
        
        if not availability_slots.exists():
            day_name = dict(AvailabilitySlot.DAY_CHOICES)[day_of_week]
            raise serializers.ValidationError({
                "appointment_date": f"Doctor is not available on {day_name}s."
            })
        
        # Check if time falls within availability
        is_within_availability = False
        for slot in availability_slots:
            if slot.start_time <= start_time < slot.end_time and slot.start_time < end_time <= slot.end_time:
                is_within_availability = True
                break
        
        if not is_within_availability:
            raise serializers.ValidationError({
                "start_time": f"The selected time ({start_time} - {end_time}) is not within doctor's available hours."
            })
        
        # Store calculated end_time for later use
        attrs['end_time'] = end_time
        attrs['doctor'] = doctor
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Create case, time slot, and appointment in a single transaction."""
        request = self.context.get('request')
        
        # Extract data
        case_id = validated_data.pop('case_id', None)
        case_title = validated_data.pop('case_title', None)
        case_description = validated_data.pop('case_description', None)
        doctor = validated_data.pop('doctor')
        doctor_id = validated_data.pop('doctor_id')
        
        appointment_date = validated_data.pop('appointment_date')
        start_time = validated_data.pop('start_time')
        end_time = validated_data.pop('end_time')
        duration = validated_data.pop('duration')
        timezone_str = validated_data.pop('timezone')
        
        language_preference = validated_data.pop('language_preference', None)
        
        # Get patient profile
        try:
            patient_profile = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist:
            raise serializers.ValidationError("Patient profile not found.")
        
        # Step 1: Get or create case
        if case_id:
            # Use the case we already validated
            case = getattr(self, '_validated_case', None)
            
            if not case:
                # Fallback: fetch the case if it wasn't stored
                try:
                    case = Case.objects.select_related('patient__user', 'doctor__user').get(id=case_id)
                    
                    # Double-check ownership
                    if case.patient != patient_profile:
                        raise serializers.ValidationError("This case does not belong to you.")
                        
                except Case.DoesNotExist:
                    raise serializers.ValidationError("Case not found.")
            
            # Ensure the case has the doctor assigned (if not already)
            if not case.doctor:
                case.doctor = doctor
                case.save(update_fields=['doctor'])
                    
        else:
            # Auto-create case
            if not case_title:
                case_title = f"Medical Consultation - {appointment_date.strftime('%B %d, %Y')}"
            if not case_description:
                case_description = validated_data.get('reason_for_visit', 'General consultation')
            
            case = Case.objects.create(
                title=case_title,
                patient=patient_profile,
                doctor=doctor,
                description=case_description,
                status='open',
                created_by=request.user
            )
        
        # Step 2: Check for overlapping time slots for this doctor
        overlapping_slots = AppointmentTimeSlot.objects.filter(
            case__doctor=doctor,
            date=appointment_date,
            is_booked=True
        )
        
        for slot in overlapping_slots:
            slot_end = datetime.combine(appointment_date, slot.start_time) + timedelta(minutes=slot.duration)
            slot_end_time = slot_end.time()
            
            # Check if times overlap
            if not (end_time <= slot.start_time or start_time >= slot_end_time):
                raise serializers.ValidationError({
                    "start_time": f"This time slot conflicts with an existing appointment at {slot.start_time}."
                })
        
        # Step 3: Create time slot
        time_slot = AppointmentTimeSlot.objects.create(
            case=case,
            date=appointment_date,
            start_time=start_time,
            duration=duration,
            timezone=timezone_str,
            is_booked=True,
            created_by=request.user
        )
        
        # Step 4: Handle translator requirements
        translator_status = 'not_needed'
        is_translator_required = validated_data.pop('is_translator_required', False)
        
        if is_translator_required or (language_preference and language_preference != 'not-required'):
            translator_status = 'pending'
            is_translator_required = True
        
        # Step 5: Create appointment
        last_appointment = case.appointments.order_by('-appointment_number').first()
        appointment_number = (last_appointment.appointment_number + 1) if last_appointment else 1
        
        appointment = Appointment.objects.create(
            case=case,
            time_slot=time_slot,
            status='confirmed',
            is_translator_required=is_translator_required,
            translator_status=translator_status,
            reason_for_visit=validated_data.get('reason_for_visit'),
            special_requests=validated_data.get('special_requests', ''),
            is_follow_up=validated_data.get('is_follow_up', False),
            appointment_number=appointment_number,
            created_by=request.user
        )
        
        from apps.payments.models import AppointmentBilling
        from apps.organization.models import Profile as OrganizationProfile
        from apps.base.models import Wallet
        from decimal import Decimal

        # Get doctor's service fee
        doctor_fee = Decimal('0.00')
        doctor_service_fees = doctor.user.service_fees.filter(  # Changed from doctor.service_fees
            is_active=True
        ).first()
        if doctor_service_fees:
            doctor_fee = doctor_service_fees.fee

        # Get translator fee if required
        translator_fee = Decimal('0.00')
        if appointment.is_translator_required and appointment.translator:
            translator_service_fees = appointment.translator.user.service_fees.filter(  # Changed from appointment.translator.service_fees
                is_active=True
            ).first()
            if translator_service_fees:
                translator_fee = translator_service_fees.fee

        # Calculate platform fee (5%)
        total_service_fee = doctor_fee + translator_fee
        platform_fee_percentage = Decimal('5.00')
        platform_fee = (total_service_fee * platform_fee_percentage / 100).quantize(Decimal('0.01'))
        total_amount = doctor_fee + translator_fee + platform_fee

        # Find organization with enough credits and lowest appointments
        organization = OrganizationProfile.objects.select_for_update().filter(
            current_credits_balance__gte=total_amount,
        ).order_by('total_appointments_processed', '-current_credits_balance').first()
        
        if not organization:
            raise serializers.ValidationError({
                "detail": "No organization available with sufficient credits to process this appointment."
            })
        
        # Create billing record
        billing = AppointmentBilling.objects.create(
            appointment=appointment,
            organization=organization,
            doctor=doctor,
            translator=appointment.translator if appointment.is_translator_required else None,
            doctor_fee=doctor_fee,
            translator_fee=translator_fee,
            platform_fee=platform_fee,
            platform_fee_percentage=platform_fee_percentage,
            total_amount=total_amount,
            currency='PKR',
            status='draft'
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