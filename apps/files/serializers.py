from rest_framework import serializers
from .models import File
from apps.base.serializers import UserSerializer
from django.conf import settings
from django.core.files.storage import default_storage
import uuid

class FileSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    related_to_user = UserSerializer(read_only=True)
    deleted_by = UserSerializer(read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = '__all__'
        read_only_fields = ['id', 'file_path', 'file_size', 'mime_type', 'uploaded_at', 'deleted_at']

    def get_download_url(self, obj):
        if obj.is_public:
            return f"{settings.MEDIA_URL}{obj.file_path}"
        return None  # Private, handle via signed URL in view

    def create(self, validated_data):
        file_obj = self.context['request'].FILES['file']
        validated_data['original_filename'] = file_obj.name
        validated_data['file_size'] = file_obj.size
        validated_data['mime_type'] = file_obj.content_type
        validated_data['file_path'] = f"{validated_data['file_type'].lower().replace(' ', '_')}/{uuid.uuid4()}_{file_obj.name}"
        # Save file to MEDIA_ROOT/subdir
        path = default_storage.save(validated_data['file_path'], file_obj)
        validated_data['file_path'] = path
        return super().create(validated_data)