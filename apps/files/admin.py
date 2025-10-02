from django.contrib import admin
from .models import File


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'file_type', 'uploaded_by', 'related_to_user', 'is_public', 'uploaded_at')
    list_filter = ('file_type', 'is_public', 'storage_provider')
    search_fields = ('original_filename',)