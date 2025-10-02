from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import uuid
from apps.base.models import User
from apps.patients.models import Case


class Room(models.Model):
    """Chat room associated with a patient case."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.OneToOneField(
        Case, 
        on_delete=models.CASCADE,
        related_name='chat_room'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messaging_room'
        verbose_name = _('Chat Room')
        verbose_name_plural = _('Chat Rooms')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Room for Case: {self.case.title}"


class Thread(models.Model):
    """Discussion thread within a chat room."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        Room, 
        on_delete=models.CASCADE, 
        related_name='threads'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_threads'
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messaging_thread'
        verbose_name = _('Thread')
        verbose_name_plural = _('Threads')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', '-created_at']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return f"{self.title} - {self.room.case.title}"

    def clean(self):
        if not self.title.strip():
            raise ValidationError({'title': _('Title cannot be empty.')})
        if not self.body.strip():
            raise ValidationError({'body': _('Body cannot be empty.')})


class Message(models.Model):
    """Individual message in a thread."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        Thread, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'messaging_message'
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['thread', 'sent_at']),
            models.Index(fields=['sender']),
            models.Index(fields=['deleted_at']),
        ]

    def __str__(self):
        return f"Message by {self.sender.email} at {self.sent_at}"

    def clean(self):
        if not self.body.strip():
            raise ValidationError({'body': _('Message body cannot be empty.')})
        if len(self.body) > 10000:
            raise ValidationError({'body': _('Message exceeds maximum length of 10,000 characters.')})

    @property
    def is_deleted(self):
        """Check if message is soft-deleted."""
        return self.deleted_at is not None

    @property
    def is_edited(self):
        """Check if message has been edited."""
        return self.edited_at is not None