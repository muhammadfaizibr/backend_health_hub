from rest_framework import serializers
from .models import Log
from apps.base.serializers import UserSerializer


class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Log
        fields = '__all__'
        read_only_fields = ['id', 'created_at']