from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import Room, Thread, Message


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'case_title', 'case_patient', 'thread_count', 'message_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['case__title', 'case__patient__user__email', 'case__patient__user__first_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'thread_count_display', 'message_count_display']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['case']
    
    fieldsets = (
        (_('Room Information'), {
            'fields': ('id', 'case')
        }),
        (_('Statistics'), {
            'fields': ('thread_count_display', 'message_count_display'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def case_title(self, obj):
        return obj.case.title
    case_title.short_description = 'Case'
    case_title.admin_order_field = 'case__title'
    
    def case_patient(self, obj):
        return obj.case.patient.user.get_full_name()
    case_patient.short_description = 'Patient'
    case_patient.admin_order_field = 'case__patient__user__first_name'
    
    def thread_count(self, obj):
        return obj.thread_count if hasattr(obj, 'thread_count') else 0
    thread_count.short_description = 'Threads'
    
    def message_count(self, obj):
        return obj.message_count if hasattr(obj, 'message_count') else 0
    message_count.short_description = 'Messages'
    
    def thread_count_display(self, obj):
        return obj.threads.count()
    thread_count_display.short_description = 'Total Threads'
    
    def message_count_display(self, obj):
        return Message.objects.filter(thread__room=obj, deleted_at__isnull=True).count()
    message_count_display.short_description = 'Total Messages'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'case__patient__user', 'case__doctor__user'
        ).annotate(
            thread_count=Count('threads'),
            message_count=Count('threads__messages', filter=Q(threads__messages__deleted_at__isnull=True))
        )


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['sender', 'body', 'sent_at', 'edited_at', 'deleted_at']
    can_delete = False
    max_num = 0  # Don't allow adding via inline
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'room', 'created_by', 'message_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'body', 'room__case__title', 'created_by__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'message_count_display']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['room', 'created_by']
    inlines = [MessageInline]
    
    fieldsets = (
        (_('Thread Information'), {
            'fields': ('id', 'room', 'created_by', 'title', 'body')
        }),
        (_('Statistics'), {
            'fields': ('message_count_display',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def message_count(self, obj):
        return obj.message_count if hasattr(obj, 'message_count') else 0
    message_count.short_description = 'Messages'
    
    def message_count_display(self, obj):
        return obj.messages.filter(deleted_at__isnull=True).count()
    message_count_display.short_description = 'Total Messages'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'room__case', 'created_by'
        ).annotate(
            message_count=Count('messages', filter=Q(messages__deleted_at__isnull=True))
        )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'thread_title', 'sender', 'body_preview', 'status_badge', 'sent_at']
    list_filter = ['sent_at', 'edited_at', 'deleted_at']
    search_fields = ['body', 'sender__email', 'sender__first_name', 'thread__title']
    readonly_fields = ['id', 'sent_at', 'edited_at', 'deleted_at']
    date_hierarchy = 'sent_at'
    autocomplete_fields = ['thread', 'sender']
    actions = ['soft_delete_messages', 'restore_messages']
    
    fieldsets = (
        (_('Message Information'), {
            'fields': ('id', 'thread', 'sender', 'body')
        }),
        (_('Timestamps'), {
            'fields': ('sent_at', 'edited_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def thread_title(self, obj):
        return obj.thread.title
    thread_title.short_description = 'Thread'
    thread_title.admin_order_field = 'thread__title'
    
    def body_preview(self, obj):
        max_length = 50
        if len(obj.body) > max_length:
            return f"{obj.body[:max_length]}..."
        return obj.body
    body_preview.short_description = 'Message'
    
    def status_badge(self, obj):
        if obj.deleted_at:
            return format_html(
                '<span style="color: white; background-color: #dc3545; padding: 3px 10px; border-radius: 3px;">Deleted</span>'
            )
        elif obj.edited_at:
            return format_html(
                '<span style="color: white; background-color: #ffc107; padding: 3px 10px; border-radius: 3px;">Edited</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #28a745; padding: 3px 10px; border-radius: 3px;">Active</span>'
        )
    status_badge.short_description = 'Status'
    
    def soft_delete_messages(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())
        self.message_user(request, f"{count} message(s) successfully deleted.")
    soft_delete_messages.short_description = "Soft delete selected messages"
    
    def restore_messages(self, request, queryset):
        count = queryset.filter(deleted_at__isnull=False).update(deleted_at=None)
        self.message_user(request, f"{count} message(s) successfully restored.")
    restore_messages.short_description = "Restore selected messages"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'thread__room__case', 'sender'
        )