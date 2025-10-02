from django.db import models
from django.core.exceptions import ValidationError
import uuid
from apps.base.models import User


def validate_file_size(value):
    """Validate file size doesn't exceed 50MB"""
    limit = 50 * 1024 * 1024  # 50MB
    if value > limit:
        raise ValidationError(f'File size cannot exceed {limit / (1024 * 1024)}MB')


class File(models.Model):
    """
    Model to store file metadata and manage file uploads.
    Supports soft deletion and multiple storage providers.
    """
    FILE_TYPE_CHOICES = [
        ('profile_picture', 'Profile Picture'),
        ('report', 'Report'),
        ('receipt', 'Receipt'),
        ('bill', 'Bill'),
        ('prescription', 'Prescription'),
        ('certification', 'Certification'),
        ('id_document', 'ID Document'),
        ('chat_attachment', 'Chat Attachment'),
        ('other', 'Other'),
    ]

    STORAGE_PROVIDER_CHOICES = [
        ('local', 'Local'),
        ('s3', 'S3'),
        ('gcs', 'GCS'),
        ('azure', 'Azure'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='uploaded_files'
    )
    related_to_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='related_files'
    )
    file_type = models.CharField(max_length=30, choices=FILE_TYPE_CHOICES)
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(validators=[validate_file_size])
    mime_type = models.CharField(max_length=100)
    storage_provider = models.CharField(
        max_length=20, 
        choices=STORAGE_PROVIDER_CHOICES, 
        default='local'
    )
    is_public = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='deleted_files'
    )

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['related_to_user', 'file_type', 'is_public']),
            models.Index(fields=['uploaded_by', 'deleted_at']),
            models.Index(fields=['file_type', 'deleted_at']),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.file_type})"

    def is_deleted(self):
        """Check if file is soft deleted"""
        return self.deleted_at is not None

    def can_access(self, user):
        """Check if user can access this file"""
        if self.is_public:
            return True
        if user.is_staff:
            return True
        if self.uploaded_by == user or self.related_to_user == user:
            return True
        return False