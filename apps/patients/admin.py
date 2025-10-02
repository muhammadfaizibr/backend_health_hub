from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Profile, MedicalHistory, Case, AppointmentTimeSlot, Appointment, Report


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_email', 'emergency_contact_name', 'emergency_contact_phone', 'created_at']
    list_filter = ['created_at']
    # CRITICAL: search_fields required for autocomplete in TranslatorReviewAdmin
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'emergency_contact_name']
    autocomplete_fields = ['user']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('User Information'), {
            'fields': ('id', 'user')
        }),
        (_('Emergency Contact'), {
            'fields': ('emergency_contact_name', 'emergency_contact_phone')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'


@admin.register(MedicalHistory)
class MedicalHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient_email', 'type', 'title', 'is_active', 'diagnosed_date', 'created_at']
    list_filter = ['type', 'is_active', 'diagnosed_date', 'created_at']
    search_fields = ['title', 'description', 'patient__user__email']
    autocomplete_fields = ['patient']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Medical History Information'), {
            'fields': ('id', 'patient', 'type', 'title', 'description')
        }),
        (_('Details'), {
            'fields': ('diagnosed_date', 'is_active')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def patient_email(self, obj):
        return obj.patient.user.email
    patient_email.short_description = 'Patient'
    patient_email.admin_order_field = 'patient__user__email'


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'patient_email', 'doctor_email', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description', 'patient__user__email', 'doctor__user__email']
    autocomplete_fields = ['patient', 'doctor']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Case Information'), {
            'fields': ('id', 'title', 'description', 'patient', 'doctor')
        }),
        (_('Status'), {
            'fields': ('status',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def patient_email(self, obj):
        return obj.patient.user.email
    patient_email.short_description = 'Patient'
    patient_email.admin_order_field = 'patient__user__email'
    
    def doctor_email(self, obj):
        return obj.doctor.user.email if obj.doctor else '-'
    doctor_email.short_description = 'Doctor'
    doctor_email.admin_order_field = 'doctor__user__email'


@admin.register(AppointmentTimeSlot)
class AppointmentTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['id', 'doctor_email', 'date', 'start_time', 'duration', 'is_booked_badge']
    list_filter = ['date', 'is_booked', 'timezone', 'created_at']
    search_fields = ['doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name']
    autocomplete_fields = ['doctor']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'date'
    
    fieldsets = (
        (_('Time Slot Information'), {
            'fields': ('id', 'doctor', 'date', 'start_time', 'duration', 'timezone')
        }),
        (_('Status'), {
            'fields': ('is_booked',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def doctor_email(self, obj):
        return obj.doctor.user.email
    doctor_email.short_description = 'Doctor'
    doctor_email.admin_order_field = 'doctor__user__email'
    
    def is_booked_badge(self, obj):
        if obj.is_booked:
            return format_html(
                '<span style="color: white; background-color: #dc3545; padding: 3px 10px; border-radius: 3px;">Booked</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #28a745; padding: 3px 10px; border-radius: 3px;">Available</span>'
        )
    is_booked_badge.short_description = 'Status'


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    # Fixed: removed 'scheduled_at' which doesn't exist, using 'time_slot_info' instead
    list_display = ['id', 'case_title', 'patient_email', 'doctor_email', 'time_slot_info', 'status_badge', 'is_follow_up']
    # Fixed: removed 'scheduled_at' from list_filter
    list_filter = ['status', 'translator_status', 'is_follow_up', 'created_at']
    # CRITICAL: search_fields required for autocomplete in TranslatorReviewAdmin
    search_fields = [
        'case__title',
        'case__patient__user__email', 
        'case__patient__user__first_name',
        'case__patient__user__last_name',
        'case__doctor__user__email',
        'case__doctor__user__first_name',
        'case__doctor__user__last_name'
    ]
    autocomplete_fields = ['case', 'time_slot', 'translator']
    # Fixed: removed 'scheduled_at' from readonly_fields
    readonly_fields = ['id', 'created_at', 'updated_at']
    # Fixed: use 'created_at' instead of 'scheduled_at'
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Appointment Information'), {
            'fields': ('id', 'case', 'time_slot', 'reason_for_visit', 'special_requests')
        }),
        (_('Status'), {
            'fields': ('status', 'is_translator_required', 'translator_status', 'is_follow_up')
        }),
        (_('Translation'), {
            'fields': ('translator',),
            'classes': ('collapse',)
        }),
        (_('Notes'), {
            'fields': ('doctor_notes',),
            'classes': ('collapse',)
        }),
        (_('Cancellation'), {
            'fields': ('cancelled_by', 'cancellation_reason', 'cancelled_at'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at', 'conducted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def case_title(self, obj):
        return obj.case.title
    case_title.short_description = 'Case'
    case_title.admin_order_field = 'case__title'
    
    def patient_email(self, obj):
        return obj.case.patient.user.email
    patient_email.short_description = 'Patient'
    patient_email.admin_order_field = 'case__patient__user__email'
    
    def doctor_email(self, obj):
        return obj.case.doctor.user.email if obj.case.doctor else '-'
    doctor_email.short_description = 'Doctor'
    doctor_email.admin_order_field = 'case__doctor__user__email'
    
    def time_slot_info(self, obj):
        if obj.time_slot:
            return f"{obj.time_slot.date} {obj.time_slot.start_time}"
        return '-'
    time_slot_info.short_description = 'Scheduled Time'
    time_slot_info.admin_order_field = 'time_slot__date'
    
    def status_badge(self, obj):
        colors = {
            'Pending Confirmation': '#17a2b8',
            'Confirmed': '#28a745',
            'Rescheduling Requested': '#ffc107',
            'Conducted': '#6c757d',
            'Cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'case__patient__user', 'case__doctor__user', 'time_slot__doctor__user', 'translator__user'
        )


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'case_title', 'report_type', 'uploaded_by_email', 'created_at']
    list_filter = ['report_type', 'created_at']
    search_fields = ['title', 'description', 'case__title', 'uploaded_by__email']
    autocomplete_fields = ['case', 'appointment', 'uploaded_by']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Report Information'), {
            'fields': ('id', 'title', 'description', 'case', 'appointment', 'report_type')
        }),
        (_('File'), {
            'fields': ('file', 'uploaded_by')
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
    
    def uploaded_by_email(self, obj):
        return obj.uploaded_by.email if obj.uploaded_by else '-'
    uploaded_by_email.short_description = 'Uploaded By'
    uploaded_by_admin_order_field = 'uploaded_by__email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('case', 'appointment', 'uploaded_by')