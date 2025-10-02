from django.db import models
import uuid
from apps.base.models import User


class File(models.Model):
    FILE_TYPE_CHOICES = [
        ('Profile Picture', 'Profile Picture'),
        ('Report', 'Report'),
        ('Receipt', 'Receipt'),
        ('Bill', 'Bill'),
        ('Prescription', 'Prescription'),
        ('Certification', 'Certification'),
        ('ID Document', 'ID Document'),
        ('Chat Attachment', 'Chat Attachment'),
        ('Other', 'Other'),
    ]

    STORAGE_PROVIDER_CHOICES = [
        ('Local', 'Local'),
        ('S3', 'S3'),
        ('GCS', 'GCS'),
        ('Azure', 'Azure'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    related_to_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    file_type = models.CharField(max_length=30, choices=FILE_TYPE_CHOICES)
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    storage_provider = models.CharField(max_length=20, choices=STORAGE_PROVIDER_CHOICES, default='Local')
    is_public = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        indexes = [models.Index(fields=['related_to_user', 'file_type', 'is_public'])]