from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from .models import (
    Profile, 
    # DoctorExperience, DoctorEducation, DoctorCertification, ConsultationFee, DoctorAvailability, 
    Prescription, PrescriptionItem, DoctorReview
)
from apps.base.serializers import (
    UserSerializer, 
    # EducationSerializer, ExperienceSerializer, CertificationSerializer, ServiceFeeSerializer, AvailabilitySlotSerializer
)
# from apps.base.models import Education, Experience, Certification, ServiceFee, AvailabilitySlot


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for doctor profiles."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'user_id', 'about', 'specialization', 'years_of_experience',
            'license_number', 'is_verified', 'average_rating', 'total_reviews',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'created_at', 'updated_at']

    def get_average_rating(self, obj):
        """Calculate average rating from published reviews."""
        from django.db.models import Avg
        result = obj.reviews.filter(status='Published').aggregate(avg_rating=Avg('rating'))
        return round(result['avg_rating'], 2) if result['avg_rating'] else None

    def get_total_reviews(self, obj):
        """Count total published reviews."""
        return obj.reviews.filter(status='Published').count()

    def validate_license_number(self, value):
        """Ensure license number is unique."""
        if not value:
            return value
        
        queryset = Profile.objects.filter(license_number=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError("License number already exists.")
        return value

    def validate_years_of_experience(self, value):
        """Validate years of experience range."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Years of experience must be between 0 and 100.")
        return value

# class DoctorExperienceSerializer(serializers.ModelSerializer):
#     """Serializer for doctor experience records."""
    
#     experience = ExperienceSerializer(read_only=True)
#     experience_id = serializers.UUIDField(write_only=True)
#     doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)

#     class Meta:
#         model = DoctorExperience
#         fields = ['id', 'doctor', 'doctor_name', 'experience', 'experience_id', 'created_at']
#         read_only_fields = ['id', 'created_at']

#     def validate_experience_id(self, value):
#         """Ensure experience exists."""
#         try:
#             Experience.objects.get(pk=value)
#             return value
#         except Experience.DoesNotExist:
#             raise serializers.ValidationError("Experience not found.")

#     def validate(self, attrs):
#         """Ensure no duplicate experience for the same doctor."""
#         doctor = attrs.get('doctor')
#         experience_id = attrs.get('experience_id')
        
#         if doctor and experience_id:
#             queryset = DoctorExperience.objects.filter(doctor=doctor, experience_id=experience_id)
#             if self.instance:
#                 queryset = queryset.exclude(pk=self.instance.pk)
            
#             if queryset.exists():
#                 raise serializers.ValidationError("This experience already exists for the doctor.")
        
#         return attrs

#     @transaction.atomic
#     def create(self, validated_data):
#         """Create doctor experience."""
#         experience_id = validated_data.pop('experience_id')
#         doctor_experience = DoctorExperience.objects.create(
#             doctor=validated_data['doctor'],
#             experience_id=experience_id
#         )
#         return doctor_experience

#     @transaction.atomic
#     def update(self, instance, validated_data):
#         """Update doctor experience."""
#         if 'experience_id' in validated_data:
#             instance.experience_id = validated_data.pop('experience_id')
#         return super().update(instance, validated_data)


# class DoctorEducationSerializer(serializers.ModelSerializer):
#     """Serializer for doctor education records."""
    
#     education = EducationSerializer(read_only=True)
#     education_id = serializers.UUIDField(write_only=True)
#     doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)

#     class Meta:
#         model = DoctorEducation
#         fields = ['id', 'doctor', 'doctor_name', 'education', 'education_id', 'created_at']
#         read_only_fields = ['id', 'created_at']

#     def validate_education_id(self, value):
#         """Ensure education exists."""
#         try:
#             Education.objects.get(pk=value)
#             return value
#         except Education.DoesNotExist:
#             raise serializers.ValidationError("Education not found.")

#     def validate(self, attrs):
#         """Ensure no duplicate education for the same doctor."""
#         doctor = attrs.get('doctor')
#         education_id = attrs.get('education_id')
        
#         if doctor and education_id:
#             queryset = DoctorEducation.objects.filter(doctor=doctor, education_id=education_id)
#             if self.instance:
#                 queryset = queryset.exclude(pk=self.instance.pk)
            
#             if queryset.exists():
#                 raise serializers.ValidationError("This education already exists for the doctor.")
        
#         return attrs

#     @transaction.atomic
#     def create(self, validated_data):
#         """Create doctor education."""
#         education_id = validated_data.pop('education_id')
#         doctor_education = DoctorEducation.objects.create(
#             doctor=validated_data['doctor'],
#             education_id=education_id
#         )
#         return doctor_education

#     @transaction.atomic
#     def update(self, instance, validated_data):
#         """Update doctor education."""
#         if 'education_id' in validated_data:
#             instance.education_id = validated_data.pop('education_id')
#         return super().update(instance, validated_data)


# class DoctorCertificationSerializer(serializers.ModelSerializer):
#     """Serializer for doctor certifications."""
    
#     certification = CertificationSerializer(read_only=True)
#     certification_id = serializers.UUIDField(write_only=True)
#     doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)

#     class Meta:
#         model = DoctorCertification
#         fields = ['id', 'doctor', 'doctor_name', 'certification', 'certification_id', 'created_at']
#         read_only_fields = ['id', 'created_at']

#     def validate_certification_id(self, value):
#         """Ensure certification exists."""
#         try:
#             Certification.objects.get(pk=value)
#             return value
#         except Certification.DoesNotExist:
#             raise serializers.ValidationError("Certification not found.")

#     def validate(self, attrs):
#         """Ensure no duplicate certification for the same doctor."""
#         doctor = attrs.get('doctor')
#         certification_id = attrs.get('certification_id')
        
#         if doctor and certification_id:
#             queryset = DoctorCertification.objects.filter(doctor=doctor, certification_id=certification_id)
#             if self.instance:
#                 queryset = queryset.exclude(pk=self.instance.pk)
            
#             if queryset.exists():
#                 raise serializers.ValidationError("This certification already exists for the doctor.")
        
#         return attrs

#     @transaction.atomic
#     def create(self, validated_data):
#         """Create doctor certification."""
#         certification_id = validated_data.pop('certification_id')
#         doctor_certification = DoctorCertification.objects.create(
#             doctor=validated_data['doctor'],
#             certification_id=certification_id
#         )
#         return doctor_certification

#     @transaction.atomic
#     def update(self, instance, validated_data):
#         """Update doctor certification."""
#         if 'certification_id' in validated_data:
#             instance.certification_id = validated_data.pop('certification_id')
#         return super().update(instance, validated_data)


# class ConsultationFeeSerializer(serializers.ModelSerializer):
#     """Serializer for consultation fees."""
    
#     service_fee = ServiceFeeSerializer(read_only=True)
#     service_fee_id = serializers.UUIDField(write_only=True)
#     doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
#     duration_display = serializers.CharField(source='service_fee.get_duration_display', read_only=True)

#     class Meta:
#         model = ConsultationFee
#         fields = [
#             'id', 'doctor', 'doctor_name', 'service_fee', 'service_fee_id',
#             'duration_display', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['id', 'created_at', 'updated_at']

#     def validate_service_fee_id(self, value):
#         """Ensure service fee exists."""
#         try:
#             ServiceFee.objects.get(pk=value)
#             return value
#         except ServiceFee.DoesNotExist:
#             raise serializers.ValidationError("Service fee not found.")

#     def validate(self, attrs):
#         """Ensure no duplicate consultation fees for the same doctor and service fee."""
#         doctor = attrs.get('doctor')
#         service_fee_id = attrs.get('service_fee_id')
        
#         if doctor and service_fee_id:
#             queryset = ConsultationFee.objects.filter(doctor=doctor, service_fee_id=service_fee_id)
#             if self.instance:
#                 queryset = queryset.exclude(pk=self.instance.pk)
            
#             if queryset.exists():
#                 raise serializers.ValidationError("This consultation fee already exists for the doctor.")
        
#         return attrs


# class DoctorAvailabilitySerializer(serializers.ModelSerializer):
#     """Serializer for doctor availability."""
    
#     availability_slot = AvailabilitySlotSerializer(read_only=True)
#     availability_slot_id = serializers.UUIDField(write_only=True)
#     doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
#     day_name = serializers.CharField(source='availability_slot.get_day_of_week_display', read_only=True)

#     class Meta:
#         model = DoctorAvailability
#         fields = [
#             'id', 'doctor', 'doctor_name', 'availability_slot', 'availability_slot_id',
#             'day_name', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['id', 'created_at', 'updated_at']

#     def validate_availability_slot_id(self, value):
#         """Ensure availability slot exists."""
#         try:
#             AvailabilitySlot.objects.get(pk=value)
#             return value
#         except AvailabilitySlot.DoesNotExist:
#             raise serializers.ValidationError("Availability slot not found.")

#     def validate(self, attrs):
#         """Ensure no duplicate availability for the same doctor and slot."""
#         doctor = attrs.get('doctor')
#         availability_slot_id = attrs.get('availability_slot_id')
        
#         if doctor and availability_slot_id:
#             queryset = DoctorAvailability.objects.filter(doctor=doctor, availability_slot_id=availability_slot_id)
#             if self.instance:
#                 queryset = queryset.exclude(pk=self.instance.pk)
            
#             if queryset.exists():
#                 raise serializers.ValidationError("This availability already exists for the doctor.")
        
#         return attrs

class PrescriptionItemSerializer(serializers.ModelSerializer):
    """Serializer for prescription items."""
    
    class Meta:
        model = PrescriptionItem
        fields = [
            'id', 'medicine_name', 'frequency',
            'dosage_amount', 'instructions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PrescriptionSerializer(serializers.ModelSerializer):
    """Serializer for prescriptions."""
    
    created_by = UserSerializer(read_only=True)
    items = PrescriptionItemSerializer(many=True, read_only=True)
    case_id = serializers.UUIDField(write_only=True)
    appointment_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    case_title = serializers.CharField(source='case.title', read_only=True)

    class Meta:
        model = Prescription
        fields = [
            'id', 'case', 'case_id', 'case_title', 'appointment', 'appointment_id',
            'title', 'start_date', 'course_duration_days', 'instructions',
            'created_by', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'case', 'appointment', 'created_by', 'created_at', 'updated_at']

    def validate_course_duration_days(self, value):
        """Validate course duration range."""
        if value < 1 or value > 365:
            raise serializers.ValidationError("Course duration must be between 1 and 365 days.")
        return value

    def validate(self, attrs):
        """Validate case and appointment relationship."""
        appointment_id = attrs.get('appointment_id')
        case_id = attrs.get('case_id')
        
        if appointment_id and case_id:
            from apps.patients.models import Appointment
            try:
                appointment = Appointment.objects.get(pk=appointment_id)
                if str(appointment.case_id) != str(case_id):
                    raise serializers.ValidationError("Appointment must belong to the specified case.")
            except Appointment.DoesNotExist:
                raise serializers.ValidationError("Appointment not found.")
        
        return attrs


class DoctorReviewSerializer(serializers.ModelSerializer):
    """Serializer for doctor reviews."""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    updated_by = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DoctorReview
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'appointment', 'rating', 'comment', 'status', 'status_display',
            'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'patient', 'doctor', 'updated_by', 'created_at', 'updated_at']

    def validate_rating(self, value):
        """Ensure rating is between 1 and 5."""
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        """Validate appointment belongs to patient and doctor."""
        appointment = attrs.get('appointment')
        
        if appointment:
            # Get patient and doctor from context or instance
            if self.instance:
                patient = self.instance.patient
                doctor = self.instance.doctor
            else:
                patient = attrs.get('patient')
                doctor = attrs.get('doctor')
            
            if patient and appointment.case.patient != patient:
                raise serializers.ValidationError({
                    'appointment': 'Appointment must belong to the reviewing patient.'
                })
            
            if doctor and appointment.time_slot.doctor != doctor:
                raise serializers.ValidationError({
                    'appointment': 'Appointment must be with the reviewed doctor.'
                })
        
        return attrs