from django.contrib import admin
from .models import Ticket, TicketMessage, TicketAttachment


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'subject', 'created_by', 'status', 'priority', 'created_at')
    list_filter = ('status', 'category', 'priority')
    search_fields = ('subject', 'description')


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'sender', 'is_internal_note', 'sent_at')


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ('ticket_message', 'file', 'created_at')