from django.db import models
import uuid
from apps.base.models import User
from apps.files.models import File


class Ticket(models.Model):
    CATEGORY_CHOICES = [
        ('Technical Issue', 'Technical Issue'),
        ('Payment Billing', 'Payment Billing'),
        ('Appointment', 'Appointment'),
        ('Account Profile', 'Account Profile'),
        ('Other', 'Other'),
    ]

    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Waiting for User', 'Waiting for User'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.PositiveIntegerField(unique=True)  # Auto-increment
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Open')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')  # Staff
    related_object_type = models.CharField(max_length=50, blank=True, null=True)
    related_object_id = models.UUIDField(blank=True, null=True)
    resolution_summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        indexes = [models.Index(fields=['created_by', 'status', 'priority', 'created_at'])]


class TicketMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    message_body = models.TextField()
    is_internal_note = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)


class TicketAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_message = models.ForeignKey(TicketMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)    