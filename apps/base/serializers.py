from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
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
        read_only_fields = ['id', 'created_at', 'updated_at', 'role']

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


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration with complete validation."""
    
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )
    languages = serializers.ListField(
        child=serializers.CharField(max_length=10),
        write_only=True,
        required=False,
        allow_empty=True
    )
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'password', 'confirm_password',
            'gender', 'phone_number', 'country_code', 'bio', 'role', 'timezone', 
            'languages', 'access_token', 'refresh_token'
        ]
        read_only_fields = ['id']

    def validate_email(self, value):
        """Ensure email is unique and properly formatted."""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_phone_number(self, value):
        """Ensure phone number is unique if provided."""
        if value and User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value

    def validate_role(self, value):
        """Validate role - prevent users from registering as Admin."""
        if value == 'Admin':
            raise serializers.ValidationError("Cannot register as Admin role.")
        return value

    def validate(self, attrs):
        """Validate password match and required fields."""
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({
                "confirm_password": "Password fields didn't match."
            })
        
        # Ensure first_name and last_name are provided
        if not attrs.get('first_name'):
            raise serializers.ValidationError({"first_name": "First name is required."})
        if not attrs.get('last_name'):
            raise serializers.ValidationError({"last_name": "Last name is required."})
            
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create user with password hashing, wallet, and return tokens."""
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        languages = validated_data.pop('languages', [])
        
        # Create user
        user = User.objects.create_user(password=password, **validated_data)
        
        # Create user languages
        if languages:
            language_objs = [
                UserLanguage(user=user, language_code=lang.lower()) 
                for lang in languages
            ]
            UserLanguage.objects.bulk_create(language_objs, ignore_conflicts=True)
        
        # Create wallet for the user
        Wallet.objects.create(user=user)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        user.access_token = str(refresh.access_token)
        user.refresh_token = str(refresh)
        
        return user

    def to_representation(self, instance):
        """Custom representation with tokens."""
        data = super().to_representation(instance)
        data['access_token'] = getattr(instance, 'access_token', None)
        data['refresh_token'] = getattr(instance, 'refresh_token', None)
        return data


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login with email and password."""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, 
        write_only=True,
        style={'input_type': 'password'}
    )
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    def validate_email(self, value):
        """Normalize email."""
        return value.lower()

    def validate(self, attrs):
        """Authenticate user and generate tokens."""
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # Authenticate user
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    "Unable to log in with provided credentials.",
                    code='authorization'
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "User account is disabled.",
                    code='authorization'
                )

            # Check if user is soft deleted
            if user.deleted_at is not None:
                raise serializers.ValidationError(
                    "User account has been deleted.",
                    code='authorization'
                )

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            attrs['user'] = user
            attrs['access_token'] = str(refresh.access_token)
            attrs['refresh_token'] = str(refresh)
            
        else:
            raise serializers.ValidationError(
                "Must include 'email' and 'password'.",
                code='authorization'
            )

        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password for authenticated users."""
    
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_old_password(self, value):
        """Validate that old password is correct."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        """Validate that new passwords match."""
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({
                "confirm_new_password": "New password fields didn't match."
            })
        
        # Ensure new password is different from old password
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                "new_password": "New password must be different from old password."
            })
        
        return attrs

    def save(self, **kwargs):
        """Update user password."""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for requesting password reset."""
    
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validate email exists and normalize it."""
        email = value.lower()
        try:
            user = User.objects.get(email=email, is_active=True, deleted_at__isnull=True)
            self.context['user'] = user
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            pass
        return email


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for resetting password with token."""
    
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """Validate token and passwords match."""
        # Validate passwords match
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({
                "confirm_new_password": "Password fields didn't match."
            })

        # Decode uid and get user
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=uid, is_active=True, deleted_at__isnull=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uid": "Invalid reset link."})

        # Validate token
        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "Invalid or expired reset link."})

        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        """Reset user password."""
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class EducationSerializer(serializers.ModelSerializer):
    """Serializer for education records."""
    
    class Meta:
        model = Education
        fields = [
            'id', 'user', 'school', 'degree', 'field', 'grade',
            'start_date', 'end_date', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

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
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

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
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

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
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate time ranges and check for overlaps."""
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        day_of_week = attrs.get('day_of_week')
        
        # Validate start time is before end time
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("Start time must be before end time.")
        
        # Get user from context (set during creation) or from instance (during update)
        user = self.context['request'].user
        
        # Check for overlapping slots
        if start_time and end_time and day_of_week is not None:
            overlapping_slots = AvailabilitySlot.objects.filter(
                user=user,
                day_of_week=day_of_week,
                is_active=True
            ).filter(
                # Check if the new slot overlaps with existing slots
                # Overlap occurs when: new_start < existing_end AND new_end > existing_start
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            
            # Exclude current instance if updating
            if self.instance:
                overlapping_slots = overlapping_slots.exclude(id=self.instance.id)
            
            if overlapping_slots.exists():
                overlapping = overlapping_slots.first()
                raise serializers.ValidationError(
                    f"This time slot overlaps with an existing availability slot: "
                    f"{overlapping.get_day_of_week_display()} {overlapping.start_time} - {overlapping.end_time}"
                )
        
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
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_fee(self, value):
        """Ensure fee is positive."""
        if value <= 0:
            raise serializers.ValidationError("Fee must be greater than zero.")
        return value

    def validate(self, attrs):
        """Check for duplicate duration for the same user."""
        duration = attrs.get('duration')
        user = self.context['request'].user
        
        if duration:
            # Check if a fee with this duration already exists for this user
            existing_fees = ServiceFee.objects.filter(
                user=user,
                duration=duration
            )
            
            # Exclude current instance if updating
            if self.instance:
                existing_fees = existing_fees.exclude(id=self.instance.id)
            
            if existing_fees.exists():
                duration_display = dict(ServiceFee.DURATION_CHOICES).get(duration, f"{duration} min")
                raise serializers.ValidationError(
                    f"A service fee for {duration_display} already exists. Please update the existing fee instead."
                )
        
        return attrs

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