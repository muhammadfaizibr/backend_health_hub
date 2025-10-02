from rest_framework import serializers
from .models import Settings, RateLimit
from apps.base.serializers import UserSerializer


class SettingsSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)

    class Meta:
        model = Settings
        fields = '__all__'
        read_only_fields = ['id', 'key', 'created_at', 'updated_at']

    def validate_value(self, value):
        value_type = self.initial_data.get('value_type', 'String')
        if value_type == 'Integer' and not isinstance(value, int):
            raise serializers.ValidationError("Value must be integer.")
        # Similar validations
        return value


class RateLimitSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = RateLimit
        fields = '__all__'
        read_only_fields = ['id', 'attempt_count', 'created_at', 'updated_at']