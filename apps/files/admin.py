from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import File


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename', 
        'file_type', 
        'file_size_display',
        'uploaded_by', 
        'related_to_user', 
        'is_public',
        'storage_provider',
        'uploaded_at',
        'status_display'
    )
    list_filter = (
        'file_type', 
        'is_public', 
        'storage_provider',
        'uploaded_at',
        'deleted_at'
    )
    search_fields = (
        'original_filename', 
        'uploaded_by__email',
        'uploaded_by__first_name',
        'uploaded_by__last_name',
        'related_to_user__email'
    )
    readonly_fields = (
        'id',
        'uploaded_by',
        'file_path',
        'file_size',
        'mime_type',
        'uploaded_at',
        'deleted_at',
        'deleted_by',
        'file_size_display',
        'download_link'
    )
    fieldsets = (
        ('File Information', {
            'fields': (
                'id',
                'original_filename',
                'file_type',
                'mime_type',
                'file_size_display',
                'download_link'
            )
        }),
        ('Storage', {
            'fields': (
                'file_path',
                'storage_provider',
                'is_public'
            )
        }),
        ('Relationships', {
            'fields': (
                'uploaded_by',
                'related_to_user'
            )
        }),
        ('Timestamps', {
            'fields': (
                'uploaded_at',
                'deleted_at',
                'deleted_by'
            )
        }),
    )
    date_hierarchy = 'uploaded_at'
    ordering = ('-uploaded_at',)
    list_per_page = 50

    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    file_size_display.short_description = 'File Size'

    def status_display(self, obj):
        """Display file status with color"""
        if obj.deleted_at:
            return format_html(
                '<span style="color: red;">Deleted</span>'
            )
        return format_html(
            '<span style="color: green;">Active</span>'
        )
    status_display.short_description = 'Status'

    def download_link(self, obj):
        """Provide download link in admin"""
        if obj.id:
            url = reverse('admin-download-file', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank">Download File</a>',
                url
            )
        return '-'
    download_link.short_description = 'Download'

    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related('uploaded_by', 'related_to_user', 'deleted_by')

    def has_delete_permission(self, request, obj=None):
        """Only allow superusers to permanently delete"""
        return request.user.is_superuser

    actions = ['soft_delete_files', 'restore_files', 'mark_as_public', 'mark_as_private']

    def soft_delete_files(self, request, queryset):
        """Soft delete selected files"""
        count = queryset.filter(deleted_at__isnull=True).update(
            deleted_at=timezone.now(),
            deleted_by=request.user
        )
        self.message_user(request, f'{count} file(s) marked as deleted.')
    soft_delete_files.short_description = 'Soft delete selected files'

    def restore_files(self, request, queryset):
        """Restore soft-deleted files"""
        count = queryset.filter(deleted_at__isnull=False).update(
            deleted_at=None,
            deleted_by=None
        )
        self.message_user(request, f'{count} file(s) restored.')
    restore_files.short_description = 'Restore selected files'

    def mark_as_public(self, request, queryset):
        """Mark files as public"""
        count = queryset.update(is_public=True)
        self.message_user(request, f'{count} file(s) marked as public.')
    mark_as_public.short_description = 'Mark as public'

    def mark_as_private(self, request, queryset):
        """Mark files as private"""
        count = queryset.update(is_public=False)
        self.message_user(request, f'{count} file(s) marked as private.')
    mark_as_private.short_description = 'Mark as private'