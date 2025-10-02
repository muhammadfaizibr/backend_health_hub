from django.contrib import admin
from .models import Log


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('action_type', 'model_name', 'object_id', 'user', 'ip_address', 'created_at')
    list_filter = ('action_type', 'model_name')
    search_fields = ('object_id', 'ip_address')
    readonly_fields = ('changes',)