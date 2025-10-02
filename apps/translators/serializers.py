from rest_framework import serializers
from django.db import transaction
from .models import (
    Profile, TranslatorExperience, TranslatorEducation, TranslatorCertification,
    TranslationLanguage, TranslationFee, TranslatorAvailability, TranslatorReview
)
from apps.base.serializers import (
    UserSerializer, EducationSerializer, ExperienceSerializer, 
    CertificationSerializer, ServiceFeeSerializer, AvailabilitySlotSerializer
)
from apps.base.models import Experience, Education, Certification


class TranslationLanguageSerializer(serializers.ModelSerializer):
    """Serializer for translation languages."""
    
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)

    class Meta:
        model = TranslationLanguage
        fields = ['id', 'translator', 'translator_name', 'language_code', 'proficiency_level', 'created_at']
        read_only_fields = ['id', 'translator', 'translator_name', 'created_at']

    def validate_proficiency_level(self, value):
        valid_levels = dict(TranslationLanguage.PROFICIENCY_LEVEL_CHOICES).keys()
        if value not in valid_levels:
            raise serializers.ValidationError(f"Invalid proficiency level. Choose from: {', '.join(valid_levels)}")
        return value

    def validate_language_code(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Language code cannot be empty.")
        if not value.isalpha():
            raise serializers.ValidationError("Language code must contain only letters.")
        return value.lower()


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for translator profile with nested relationships."""
    
    user = UserSerializer(read_only=True)
    languages = TranslationLanguageSerializer(many=True, read_only=True)
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'about', 'area_of_focus', 'currency', 'is_verified',
            'languages', 'average_rating', 'total_reviews', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'created_at', 'updated_at']

    def validate_currency(self, value):
        if value and len(value) != 3:
            raise serializers.ValidationError("Currency code must be exactly 3 characters.")
        return value.upper() if value else 'USD'


class TranslatorExperienceSerializer(serializers.ModelSerializer):
    """Serializer for translator experience with nested creation."""
    
    experience = ExperienceSerializer()
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)

    class Meta:
        model = TranslatorExperience
        fields = ['id', 'translator', 'translator_name', 'experience', 'created_at']
        read_only_fields = ['id', 'translator', 'translator_name', 'created_at']

    @transaction.atomic
    def create(self, validated_data):
        experience_data = validated_data.pop('experience')
        
        # Use get_or_create to avoid duplicates
        experience, created = Experience.objects.get_or_create(
            title=experience_data.get('title'),
            company=experience_data.get('company'),
            defaults=experience_data
        )
        
        validated_data['experience'] = experience
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        if 'experience' in validated_data:
            experience_data = validated_data.pop('experience')
            
            # Update existing experience or create new one
            for attr, value in experience_data.items():
                setattr(instance.experience, attr, value)
            instance.experience.save()
        
        return super().update(instance, validated_data)


class TranslatorEducationSerializer(serializers.ModelSerializer):
    """Serializer for translator education with nested creation."""
    
    education = EducationSerializer()
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)

    class Meta:
        model = TranslatorEducation
        fields = ['id', 'translator', 'translator_name', 'education', 'created_at']
        read_only_fields = ['id', 'translator', 'translator_name', 'created_at']

    @transaction.atomic
    def create(self, validated_data):
        education_data = validated_data.pop('education')
        
        education, created = Education.objects.get_or_create(
            institution=education_data.get('institution'),
            degree=education_data.get('degree'),
            defaults=education_data
        )
        
        validated_data['education'] = education
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        if 'education' in validated_data:
            education_data = validated_data.pop('education')
            
            for attr, value in education_data.items():
                setattr(instance.education, attr, value)
            instance.education.save()
        
        return super().update(instance, validated_data)


class TranslatorCertificationSerializer(serializers.ModelSerializer):
    """Serializer for translator certifications with nested creation."""
    
    certification = CertificationSerializer()
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)

    class Meta:
        model = TranslatorCertification
        fields = ['id', 'translator', 'translator_name', 'certification', 'created_at']
        read_only_fields = ['id', 'translator', 'translator_name', 'created_at']

    @transaction.atomic
    def create(self, validated_data):
        certification_data = validated_data.pop('certification')
        
        certification, created = Certification.objects.get_or_create(
            name=certification_data.get('name'),
            issuing_organization=certification_data.get('issuing_organization'),
            defaults=certification_data
        )
        
        validated_data['certification'] = certification
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        if 'certification' in validated_data:
            certification_data = validated_data.pop('certification')
            
            for attr, value in certification_data.items():
                setattr(instance.certification, attr, value)
            instance.certification.save()
        
        return super().update(instance, validated_data)


class TranslationFeeSerializer(serializers.ModelSerializer):
    """Serializer for translation fees."""
    
    service_fee = ServiceFeeSerializer(read_only=True)
    service_fee_id = serializers.UUIDField(write_only=True)
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)

    class Meta:
        model = TranslationFee
        fields = ['id', 'translator', 'translator_name', 'service_fee', 'service_fee_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'translator', 'translator_name', 'created_at', 'updated_at']


class TranslatorAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for translator availability."""
    
    availability_slot = AvailabilitySlotSerializer(read_only=True)
    availability_slot_id = serializers.UUIDField(write_only=True)
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)

    class Meta:
        model = TranslatorAvailability
        fields = ['id', 'translator', 'translator_name', 'availability_slot', 'availability_slot_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'translator', 'translator_name', 'created_at', 'updated_at']


class TranslatorReviewSerializer(serializers.ModelSerializer):
    """Serializer for translator reviews with permissions."""
    
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    translator_name = serializers.CharField(source='translator.user.get_full_name', read_only=True)
    updated_by = UserSerializer(read_only=True)

    class Meta:
        model = TranslatorReview
        fields = [
            'id', 'patient', 'patient_name', 'translator', 'translator_name',
            'appointment', 'rating', 'comment', 'status', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'patient', 'translator', 'updated_by', 'created_at', 'updated_at']

    def validate_rating(self, value):
        if not isinstance(value, int) or not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be an integer between 1 and 5.")
        return value

    def validate_status(self, value):
        # Only staff can change status
        request = self.context.get('request')
        if request and not request.user.is_staff:
            if self.instance and self.instance.status != value:
                raise serializers.ValidationError("Only staff members can change review status.")
        return value

    def validate(self, attrs):
        # Ensure patient owns the appointment
        if 'appointment' in attrs:
            request = self.context.get('request')
            if request and hasattr(request.user, 'patient_profile'):
                if attrs['appointment'].patient != request.user.patient_profile:
                    raise serializers.ValidationError({
                        'appointment': "You can only review appointments you attended."
                    })
        return attrs