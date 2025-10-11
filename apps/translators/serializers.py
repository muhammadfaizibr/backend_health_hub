from rest_framework import serializers
from .models import (
    Profile, TranslationLanguage, TranslatorReview
)
from apps.base.serializers import (
    UserSerializer, 
)


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