from rest_framework import serializers
from .models import File
from apps.base.models import User


class FileSerializer(serializers.ModelSerializer):
    """Full file serializer with all details"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    related_to_user_name = serializers.CharField(source='related_to_user.get_full_name', read_only=True)
    case_title = serializers.CharField(source='case.title', read_only=True)
    file_size_display = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            'id', 'uploaded_by', 'uploaded_by_name', 'related_to_user', 
            'related_to_user_name', 'case', 'case_title', 'file_type', 
            'original_filename', 'file_path', 'file_size', 'file_size_display',
            'mime_type', 'storage_provider', 'is_public', 'uploaded_at',
            'deleted_at', 'deleted_by', 'download_url'
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'file_path', 'file_size', 'mime_type',
            'uploaded_at', 'deleted_at', 'deleted_by'
        ]

    def get_file_size_display(self, obj):
        """Display file size in human-readable format"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    def get_download_url(self, obj):
        """Generate download URL"""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/files/{obj.id}/download/')
        return None

class FileUploadSerializer(serializers.Serializer):
    """Serializer for file upload"""
    file = serializers.FileField()
    file_type = serializers.ChoiceField(choices=File.FILE_TYPE_CHOICES)
    is_public = serializers.BooleanField(default=False)
    storage_provider = serializers.ChoiceField(
        choices=File.STORAGE_PROVIDER_CHOICES,
        default='local'
    )
    related_to_user_id = serializers.UUIDField(required=False, allow_null=True)
    case = serializers.UUIDField(required=False, allow_null=True)


class FileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing files"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    case_title = serializers.CharField(source='case.title', read_only=True)
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            'id', 'file_type', 'original_filename', 'uploaded_by_name',
            'case_title', 'file_size_display', 'is_public', 'uploaded_at'
        ]

    def get_file_size_display(self, obj):
        """Display file size in human-readable format"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"