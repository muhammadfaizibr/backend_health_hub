from django.db import models
import uuid
from apps.base.models import User


class Settings(models.Model):
    VALUE_TYPE_CHOICES = [
        ('String', 'String'),
        ('Integer', 'Integer'),
        ('Boolean', 'Boolean'),
        ('JSON', 'JSON'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField()  # Flexible
    value_type = models.CharField(max_length=20, choices=VALUE_TYPE_CHOICES, default='String')
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        indexes = [models.Index(fields=['key', 'is_public'])]


class RateLimit(models.Model):
    ACTION_TYPE_CHOICES = [
        ('Login', 'Login'),
        ('Password Reset', 'Password Reset'),
        ('API Call', 'API Call'),
        ('Message Send', 'Message Send'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    attempt_count = models.PositiveIntegerField(default=1)
    window_start = models.DateTimeField()
    blocked_until = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'action_type', 'window_start'), ('ip_address', 'action_type', 'window_start')]
        indexes = [models.Index(fields=['user', 'action_type', 'window_start']), models.Index(fields=['ip_address', 'action_type', 'window_start'])]