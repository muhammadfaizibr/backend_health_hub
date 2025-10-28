from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg, Count, Q
from .models import (
    Profile, 
    # DoctorExperience, DoctorEducation, DoctorCertification, ConsultationFee, DoctorAvailability, 
    Prescription, PrescriptionItem, DoctorReview
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin interface for doctor profiles."""
    
    list_display = (
        'user', 'user_email', 'specialization', 'category','years_of_experience',
        'is_verified', 'average_rating', 'total_reviews', 'created_at'
    )
    list_filter = ('is_verified', 'specialization', 'years_of_experience', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'specialization', 'license_number')
    readonly_fields = ('created_at', 'updated_at', 'average_rating_display', 'total_reviews_display')
    autocomplete_fields = ['user']
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Professional Information'), {
            'fields': ('about', 'specialization', 'category','years_of_experience', 'license_number')
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
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def average_rating(self, obj):
        return obj.avg_rating if hasattr(obj, 'avg_rating') else None
    average_rating.short_description = 'Avg Rating'
    
    def total_reviews(self, obj):
        return obj.review_count if hasattr(obj, 'review_count') else 0
    total_reviews.short_description = 'Reviews'
    
    def average_rating_display(self, obj):
        result = obj.reviews.filter(status='Published').aggregate(avg=Avg('rating'))
        return round(result['avg'], 2) if result['avg'] else 'N/A'
    average_rating_display.short_description = 'Average Rating'
    
    def total_reviews_display(self, obj):
        return obj.reviews.filter(status='Published').count()
    total_reviews_display.short_description = 'Total Reviews'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__status='Published')),
            review_count=Count('reviews', filter=Q(reviews__status='Published'))
        )

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    """Admin interface for prescriptions."""
    
    list_display = ('title', 'case', 'appointment', 'start_date', 'course_duration_days', 'created_by', 'created_at')
    list_filter = ('start_date', 'created_at')
    search_fields = ('title', 'case__title', 'case__patient__user__email', 'instructions')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    date_hierarchy = 'created_at'
    # Remove autocomplete_fields for appointment since it doesn't have search_fields defined
    autocomplete_fields = ['case', 'created_by']
    
    fieldsets = (
        (_('Prescription Information'), {
            'fields': ('title', 'start_date', 'course_duration_days', 'instructions')
        }),
        (_('Related Records'), {
            'fields': ('case', 'appointment')
        }),
        (_('Tracking'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'case__patient__user',
            'appointment',
            'created_by'
        )


class PrescriptionItemInline(admin.TabularInline):
    """Inline admin for prescription items."""
    
    model = PrescriptionItem
    extra = 1
    fields = ('medicine_name', 'dosage_amount', 'frequency', 'instructions')


# Add inline to Prescription admin
PrescriptionAdmin.inlines = [PrescriptionItemInline]


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    """Admin interface for prescription items."""
    
    list_display = ('prescription', 'medicine_name', 'dosage_amount', 'frequency', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('medicine_name', 'prescription__title', 'instructions')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['prescription']
    
    fieldsets = (
        (_('Medicine Information'), {
            'fields': ('prescription', 'medicine_name', 'dosage_amount', 'frequency')
        }),
        (_('Instructions'), {
            'fields': ('instructions',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
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