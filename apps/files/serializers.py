from rest_framework import serializers
from django.conf import settings
from .models import File
from apps.base.serializers import UserSerializer


class FileUploadSerializer(serializers.ModelSerializer):
    """Serializer for file upload"""
    file = serializers.FileField(write_only=True)
    related_to_user_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = File
        fields = ['file', 'file_type', 'is_public', 'related_to_user_id', 'storage_provider']

    def validate_file(self, value):
        """Validate file upload"""
        # Check file size (50MB limit)
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size cannot exceed {max_size / (1024 * 1024)}MB"
            )

        # Validate mime type (basic check)
        allowed_types = getattr(settings, 'ALLOWED_FILE_TYPES', None)
        if allowed_types and value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"File type '{value.content_type}' is not allowed"
            )

        return value

    def validate_file_type(self, value):
        """Ensure file_type is provided"""
        if not value:
            raise serializers.ValidationError("File type is required")
        return value


class FileSerializer(serializers.ModelSerializer):
    """Serializer for file details"""
    uploaded_by = UserSerializer(read_only=True)
    related_to_user = UserSerializer(read_only=True)
    deleted_by = UserSerializer(read_only=True)
    download_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            'id', 'uploaded_by', 'related_to_user', 'file_type',
            'original_filename', 'file_path', 'file_size', 'file_size_mb',
            'mime_type', 'storage_provider', 'is_public', 'uploaded_at',
            'deleted_at', 'deleted_by', 'download_url'
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'related_to_user', 'file_path', 
            'file_size', 'mime_type', 'uploaded_at', 'deleted_at', 'deleted_by'
        ]

    def get_download_url(self, obj):
        """Generate download URL"""
        request = self.context.get('request')
        if request and obj.can_access(request.user):
            return request.build_absolute_uri(f'/api/files/{obj.id}/download/')
        return None

    def get_file_size_mb(self, obj):
        """Return file size in MB"""
        return round(obj.file_size / (1024 * 1024), 2)


class FileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for file listings"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            'id', 'file_type', 'original_filename', 'file_size', 
            'file_size_mb', 'mime_type', 'is_public', 'uploaded_at',
            'uploaded_by_name'
        ]

    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)