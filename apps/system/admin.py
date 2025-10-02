from django.contrib import admin
from .models import Settings, RateLimit


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'value_type', 'is_public', 'description')
    list_filter = ('value_type', 'is_public')


@admin.register(RateLimit)
class RateLimitAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'action_type', 'attempt_count', 'blocked_until')
    list_filter = ('action_type',)