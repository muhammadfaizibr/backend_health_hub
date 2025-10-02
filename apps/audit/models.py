from django.db import models
import uuid
from apps.base.models import User


class Log(models.Model):
    ACTION_TYPE_CHOICES = [
        ('CREATE', 'CREATE'),
        ('UPDATE', 'UPDATE'),
        ('DELETE', 'DELETE'),
        ('LOGIN', 'LOGIN'),
        ('LOGOUT', 'LOGOUT'),
        ('PAYMENT', 'PAYMENT'),
        ('REFUND', 'REFUND'),
        ('STATUS_CHANGE', 'STATUS_CHANGE'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')  # Null for system
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.UUIDField()
    changes = models.JSONField(blank=True, null=True, default=dict)  # {'before': {}, 'after': {}}
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'action_type', 'created_at']), models.Index(fields=['model_name', 'object_id'])]
        ordering = ['-created_at']