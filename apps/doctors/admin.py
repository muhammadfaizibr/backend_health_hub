from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg, Count, Q
from .models import Profile, Prescription, PrescriptionItem, DoctorReview


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin interface for doctor profiles."""
    
    list_display = (
        'user_email', 'user_full_name', 'category', 'specialization', 'years_of_experience',
        'license_number', 'is_verified_badge', 'location', 'average_rating', 'total_reviews', 'created_at'
    )
    list_filter = ['is_verified', 'category', 'years_of_experience', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'specialization', 'license_number', 'location']
    readonly_fields = ['id', 'created_at', 'updated_at', 'average_rating_display', 'total_reviews_display']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('User'), {'fields': ('id', 'user',)}),
        (_('Professional Information'), {
            'fields': ('about', 'category', 'specialization', 'years_of_experience', 'license_number', 'location')
        }),
        (_('Verification'), {
            'fields': ('is_verified',)
        }),
        (_('Statistics'), {
            'fields': ('average_rating_display', 'total_reviews_display'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_doctors', 'unverify_doctors']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def user_full_name(self, obj):
        return obj.user.get_full_name() or '-'
    user_full_name.short_description = 'Full Name'
    user_full_name.admin_order_field = 'user__first_name'
    
    def is_verified_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span style="color: white; background-color: #28a745; padding: 3px 10px; border-radius: 3px;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #dc3545; padding: 3px 10px; border-radius: 3px;">✗ Not Verified</span>'
        )
    is_verified_badge.short_description = 'Verification Status'
    
    def average_rating(self, obj):
        return obj.avg_rating if hasattr(obj, 'avg_rating') and obj.avg_rating else 'N/A'
    average_rating.short_description = 'Avg Rating'
    
    def total_reviews(self, obj):
        return obj.review_count if hasattr(obj, 'review_count') else 0
    total_reviews.short_description = 'Reviews'
    
    def average_rating_display(self, obj):
        result = obj.reviews.filter(status='published').aggregate(avg=Avg('rating'))
        return round(result['avg'], 2) if result['avg'] else 'N/A'
    average_rating_display.short_description = 'Average Rating'
    
    def total_reviews_display(self, obj):
        return obj.reviews.filter(status='published').count()
    total_reviews_display.short_description = 'Total Reviews'
    
    def verify_doctors(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} doctor(s) successfully verified.")
    verify_doctors.short_description = "Verify selected doctors"
    
    def unverify_doctors(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} doctor(s) successfully unverified.")
    unverify_doctors.short_description = "Unverify selected doctors"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__status='published')),
            review_count=Count('reviews', filter=Q(reviews__status='published'))
        )


class PrescriptionItemInline(admin.TabularInline):
    """Inline admin for prescription items."""
    
    model = PrescriptionItem
    extra = 1
    fields = ('medicine_name', 'dosage_amount', 'frequency', 'instructions')
    readonly_fields = []


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    """Admin interface for prescriptions."""
    
    list_display = ['id', 'title', 'case_title', 'appointment_id', 'start_date', 'course_duration_days', 'created_by_email', 'created_at']
    list_filter = ['start_date', 'created_at']
    search_fields = ['title', 'case__title', 'case__patient__user__email', 'instructions', 'created_by__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['case', 'appointment', 'created_by']
    inlines = [PrescriptionItemInline]
    
    fieldsets = (
        (_('Prescription Information'), {
            'fields': ('id', 'title', 'start_date', 'course_duration_days', 'instructions')
        }),
        (_('Related Records'), {
            'fields': ('case', 'appointment')
        }),
        (_('Tracking'), {
            'fields': ('created_by',),
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
    
    def appointment_id(self, obj):
        return str(obj.appointment.id) if obj.appointment else '-'
    appointment_id.short_description = 'Appointment'
    
    def created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else '-'
    created_by_email.short_description = 'Created By'
    created_by_email.admin_order_field = 'created_by__email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'case__patient__user',
            'appointment',
            'created_by'
        )


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    """Admin interface for prescription items."""
    
    list_display = ['id', 'prescription_title', 'medicine_name', 'dosage_amount', 'frequency', 'created_at']
    list_filter = ['created_at']
    search_fields = ['medicine_name', 'prescription__title', 'instructions']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['prescription']
    
    fieldsets = (
        (_('Medicine Information'), {
            'fields': ('id', 'prescription', 'medicine_name', 'dosage_amount', 'frequency')
        }),
        (_('Instructions'), {
            'fields': ('instructions',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def prescription_title(self, obj):
        return obj.prescription.title
    prescription_title.short_description = 'Prescription'
    prescription_title.admin_order_field = 'prescription__title'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('prescription__case__patient__user')

@admin.register(DoctorReview)
class DoctorReviewAdmin(admin.ModelAdmin):
    """Admin interface for doctor reviews."""
    
    list_display = ('doctor', 'patient', 'rating', 'status', 'appointment', 'created_at')
    list_filter = ('status', 'rating', 'created_at')
    search_fields = (
        'doctor__user__email', 'doctor__user__first_name',
        'patient__user__email', 'patient__user__first_name',
        'comment'
    )
    readonly_fields = ('created_at', 'updated_at', 'updated_by')
    date_hierarchy = 'created_at'
    # Remove autocomplete_fields that don't have search_fields defined
    autocomplete_fields = ['updated_by']
    actions = ['publish_reviews', 'hide_reviews']
    
    fieldsets = (
        (_('Review Details'), {
            'fields': ('patient', 'doctor', 'appointment', 'rating')
        }),
        (_('Content'), {
            'fields': ('comment',)
        }),
        (_('Moderation'), {
            'fields': ('status', 'updated_by')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def publish_reviews(self, request, queryset):
        """Bulk action to publish reviews."""
        updated = queryset.update(status='Published', updated_by=request.user)
        self.message_user(request, f'{updated} reviews published successfully.')
    publish_reviews.short_description = 'Publish selected reviews'
    
    def hide_reviews(self, request, queryset):
        """Bulk action to hide reviews."""
        updated = queryset.update(status='Hidden', updated_by=request.user)
        self.message_user(request, f'{updated} reviews hidden successfully.')
    hide_reviews.short_description = 'Hide selected reviews'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'patient__user',
            'doctor__user',
            'appointment',
            'updated_by'
        )