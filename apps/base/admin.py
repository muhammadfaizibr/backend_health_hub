from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    User, UserLanguage, Education, Experience,
    Certification, AvailabilitySlot, ServiceFee, Wallet
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""
    
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser', 'gender', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number', 'verification_id')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {
            'fields': ('first_name', 'last_name', 'gender', 'phone_number', 'country_code', 'bio')
        }),
        (_('Role & Verification'), {
            'fields': ('role', 'verification_id')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        (_('Settings'), {
            'fields': ('timezone',)
        }),
        (_('Important Dates'), {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2', 'first_name', 'last_name',
                'role', 'is_staff', 'is_active'
            ),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    filter_horizontal = ('groups', 'user_permissions')
    
    def get_queryset(self, request):
        """Optimize queryset with prefetch_related."""
        return super().get_queryset(request).prefetch_related('languages')


@admin.register(UserLanguage)
class UserLanguageAdmin(admin.ModelAdmin):
    """Admin interface for UserLanguage model."""
    
    list_display = ('user', 'language_code', 'created_at')
    list_filter = ('language_code', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'language_code')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['user']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    """Admin interface for Education model."""
    
    list_display = ('user', 'school', 'degree', 'field', 'start_date', 'end_date')
    list_filter = ('field', 'degree', 'start_date', 'end_date')
    search_fields = ('user__email', 'school', 'degree', 'field')
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['user']
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Education Details'), {
            'fields': ('school', 'degree', 'field', 'grade')
        }),
        (_('Duration'), {
            'fields': ('start_date', 'end_date')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    """Admin interface for Experience model."""
    
    list_display = ('user', 'title', 'company_or_organization', 'employment_type', 'start_date', 'end_date')
    list_filter = ('employment_type', 'start_date', 'end_date')
    search_fields = ('user__email', 'title', 'company_or_organization', 'location')
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['user']
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Position Details'), {
            'fields': ('title', 'employment_type', 'company_or_organization', 'location')
        }),
        (_('Duration'), {
            'fields': ('start_date', 'end_date')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    """Admin interface for Certification model."""
    
    list_display = ('user', 'title', 'issuing_organization', 'issue_date', 'expiration_date', 'credential_id')
    list_filter = ('issue_date', 'expiration_date', 'issuing_organization')
    search_fields = ('user__email', 'title', 'issuing_organization', 'credential_id')
    date_hierarchy = 'issue_date'
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['user']
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Certification Details'), {
            'fields': ('title', 'issuing_organization', 'credential_id', 'credential_url', 'file')
        }),
        (_('Dates'), {
            'fields': ('issue_date', 'expiration_date')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user', 'file')


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    """Admin interface for AvailabilitySlot model."""
    
    list_display = ('user', 'day_of_week', 'start_time', 'end_time', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['user']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


@admin.register(ServiceFee)
class ServiceFeeAdmin(admin.ModelAdmin):
    """Admin interface for ServiceFee model."""
    
    list_display = ('user', 'duration', 'fee', 'currency', 'is_active')
    list_filter = ('duration', 'is_active', 'currency')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['user']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """Admin interface for Wallet model."""
    
    list_display = ('user', 'available_balance', 'pending_balance', 'total_lifetime_earnings', 'currency', 'version')
    list_filter = ('currency',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'version')
    autocomplete_fields = ['user']