from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from .models import (
    User, UserLanguage, Education, Experience,
    Certification, AvailabilitySlot, ServiceFee, Wallet
)


class UserLanguageSerializer(serializers.ModelSerializer):
    """Serializer for user languages."""
    
    class Meta:
        model = UserLanguage
        fields = ['id', 'language_code', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_language_code(self, value):
        """Validate language code format."""
        if len(value) < 2 or len(value) > 10:
            raise serializers.ValidationError("Language code must be between 2 and 10 characters.")
        return value.lower()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profiles."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    languages = UserLanguageSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'email', 'gender',
            'phone_number', 'country_code', 'verification_id', 'bio', 'role',
            'is_active', 'timezone', 'created_at', 'updated_at', 'languages'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_email(self, value):
        """Ensure email is unique, excluding current instance."""
        user_id = self.instance.pk if self.instance else None
        if User.objects.filter(email=value).exclude(pk=user_id).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_phone_number(self, value):
        """Ensure phone number is unique, excluding current instance."""
        if not value:
            return value
        user_id = self.instance.pk if self.instance else None
        if User.objects.filter(phone_number=value).exclude(pk=user_id).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    languages = serializers.ListField(
        child=serializers.CharField(max_length=10),
        write_only=True,
        required=False,
        allow_empty=True
    )

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'password', 'confirm_password',
            'gender', 'phone_number', 'country_code', 'bio', 'role', 'timezone', 'languages'
        ]

    def validate_email(self, value):
        """Ensure email is unique."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_phone_number(self, value):
        """Ensure phone number is unique if provided."""
        if value and User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value

    def validate(self, attrs):
        """Validate password match."""
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Password fields didn't match."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create user with password hashing and optional languages."""
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        languages = validated_data.pop('languages', [])
        
        user = User.objects.create_user(password=password, **validated_data)
        
        # Create user languages
        if languages:
            language_objs = [UserLanguage(user=user, language_code=lang.lower()) for lang in languages]
            UserLanguage.objects.bulk_create(language_objs, ignore_conflicts=True)
        
        return user


class EducationSerializer(serializers.ModelSerializer):
    """Serializer for education records."""
    
    class Meta:
        model = Education
        fields = [
            'id', 'user', 'school', 'degree', 'field', 'grade',
            'start_date', 'end_date', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate date ranges."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date.")
        
        return attrs


class ExperienceSerializer(serializers.ModelSerializer):
    """Serializer for work experience."""
    
    class Meta:
        model = Experience
        fields = [
            'id', 'user', 'title', 'employment_type', 'company_or_organization',
            'start_date', 'end_date', 'location', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate date ranges."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date.")
        
        return attrs


class CertificationSerializer(serializers.ModelSerializer):
    """Serializer for certifications."""
    
    class Meta:
        model = Certification
        fields = [
            'id', 'user', 'title', 'issuing_organization', 'issue_date',
            'expiration_date', 'credential_id', 'credential_url',
            'description', 'file', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate date ranges."""
        issue_date = attrs.get('issue_date')
        expiration_date = attrs.get('expiration_date')
        
        if issue_date and expiration_date and issue_date > expiration_date:
            raise serializers.ValidationError("Issue date cannot be after expiration date.")
        
        return attrs


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    """Serializer for availability slots."""
    
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = AvailabilitySlot
        fields = [
            'id', 'user', 'day_of_week', 'day_name', 'start_time',
            'end_time', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate time ranges."""
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("Start time must be before end time.")
        
        return attrs


class ServiceFeeSerializer(serializers.ModelSerializer):
    """Serializer for service fees."""
    
    duration_display = serializers.CharField(source='get_duration_display', read_only=True)
    
    class Meta:
        model = ServiceFee
        fields = [
            'id', 'user', 'duration', 'duration_display', 'fee',
            'currency', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_fee(self, value):
        """Ensure fee is positive."""
        if value <= 0:
            raise serializers.ValidationError("Fee must be greater than zero.")
        return value


class WalletSerializer(serializers.ModelSerializer):
    """Serializer for wallet management."""
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'user', 'available_balance', 'pending_balance',
            'total_lifetime_earnings', 'currency', 'version',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_available_balance(self, value):
        """Ensure available balance is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Available balance cannot be negative.")
        return value

    def validate_pending_balance(self, value):
        """Ensure pending balance is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Pending balance cannot be negative.")
        return value

    def validate_total_lifetime_earnings(self, value):
        """Ensure total lifetime earnings is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Total lifetime earnings cannot be negative.")
        return value