from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from .models import (
    Profile, Prescription, PrescriptionItem, DoctorReview
)
from apps.base.serializers import (
    UserSerializer, 
)

class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for doctor profiles with enhanced data."""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'user_id', 'full_name', 'profile_image',
            'about', 'category', 'category_display', 'specialization', 
            'years_of_experience', 'license_number', 'is_verified', 
            'average_rating', 'total_reviews', 'location',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        """Get doctor's full name."""
        return obj.user.get_full_name()
    
    def get_profile_image(self, obj):
        """Get doctor's profile image URL."""
        if hasattr(obj.user, 'profile_image') and obj.user.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.user.profile_image.url)
        return None

    def get_average_rating(self, obj):
        """Calculate average rating from published reviews."""
        # Check if avg_rating is already annotated
        if hasattr(obj, 'avg_rating') and obj.avg_rating is not None:
            return round(obj.avg_rating, 2)
        
        from django.db.models import Avg
        result = obj.reviews.filter(status='Published').aggregate(avg_rating=Avg('rating'))
        return round(result['avg_rating'], 2) if result['avg_rating'] else None

    def get_total_reviews(self, obj):
        """Count total published reviews."""
        # Check if review_count is already annotated
        if hasattr(obj, 'review_count'):
            return obj.review_count
        
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