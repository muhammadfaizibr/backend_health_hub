from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count
from django.utils.translation import gettext_lazy as _

from .models import (
    Profile, TranslationLanguage, TranslatorReview
    # TranslatorExperience, TranslatorEducation, TranslatorCertification, TranslationFee, TranslatorAvailability, 
)
from django.db import models  # Import models for annotation


class TranslationLanguageInline(admin.TabularInline):
    model = TranslationLanguage
    extra = 1
    fields = ['language_code', 'proficiency_level']


# class TranslatorExperienceInline(admin.TabularInline):
#     model = TranslatorExperience
#     extra = 0
#     autocomplete_fields = ['experience']
#     readonly_fields = ['created_at']


# class TranslatorEducationInline(admin.TabularInline):
#     model = TranslatorEducation
#     extra = 0
#     autocomplete_fields = ['education']
#     readonly_fields = ['created_at']


# class TranslatorCertificationInline(admin.TabularInline):
#     model = TranslatorCertification
#     extra = 0
#     autocomplete_fields = ['certification']
#     readonly_fields = ['created_at']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_full_name', 'user_email', 'area_of_focus', 
        'currency', 'verification_badge', 'avg_rating', 'review_count', 'created_at'
    ]
    list_filter = ['is_verified', 'currency', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'area_of_focus']
    readonly_fields = ['id', 'created_at', 'updated_at', 'avg_rating_display', 'total_reviews_display']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    inlines = [
        TranslationLanguageInline, 
        # TranslatorExperienceInline, 
        # TranslatorEducationInline, 
        # TranslatorCertificationInline
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('id', 'user', 'about', 'area_of_focus', 'currency')
        }),
        (_('Verification'), {
            'fields': ('is_verified',)
        }),
        (_('Statistics'), {
            'fields': ('avg_rating_display', 'total_reviews_display'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_profiles', 'unverify_profiles']
    
    def user_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.email
    user_full_name.short_description = 'Translator Name'
    user_full_name.admin_order_field = 'user__first_name'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span style="color: white; background-color: #28a745; padding: 3px 10px; border-radius: 3px;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #dc3545; padding: 3px 10px; border-radius: 3px;">✗ Not Verified</span>'
        )
    verification_badge.short_description = 'Status'
    
    def avg_rating(self, obj):
        avg = obj.average_rating
        return f"{avg:.1f} ★" if avg else "No ratings"
    avg_rating.short_description = 'Avg Rating'
    
    def review_count(self, obj):
        return obj.total_reviews
    review_count.short_description = 'Reviews'
    
    def avg_rating_display(self, obj):
        return obj.average_rating or "No ratings yet"
    avg_rating_display.short_description = 'Average Rating'
    
    def total_reviews_display(self, obj):
        return obj.total_reviews
    total_reviews_display.short_description = 'Total Reviews'
    
    def verify_profiles(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} profile(s) successfully verified.")
    verify_profiles.short_description = "Verify selected profiles"
    
    def unverify_profiles(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} profile(s) successfully unverified.")
    unverify_profiles.short_description = "Unverify selected profiles"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            avg_rating_value=Avg('reviews__rating', filter=models.Q(reviews__status='Published')),
            review_count_value=Count('reviews', filter=models.Q(reviews__status='Published'))
        )


# @admin.register(TranslatorExperience)
# class TranslatorExperienceAdmin(admin.ModelAdmin):
#     list_display = ['id', 'translator_name', 'experience_title', 'experience_company', 'created_at']
#     list_filter = ['created_at']
#     search_fields = ['translator__user__email', 'translator__user__first_name', 'experience__title', 'experience__company']
#     readonly_fields = ['id', 'created_at']
#     autocomplete_fields = ['translator', 'experience']
#     date_hierarchy = 'created_at'
    
#     def translator_name(self, obj):
#         return obj.translator.user.get_full_name()
#     translator_name.short_description = 'Translator'
#     translator_name.admin_order_field = 'translator__user__first_name'
    
#     def experience_title(self, obj):
#         return obj.experience.title
#     experience_title.short_description = 'Position'
#     experience_title.admin_order_field = 'experience__title'
    
#     def experience_company(self, obj):
#         return obj.experience.company
#     experience_company.short_description = 'Company'
#     experience_company.admin_order_field = 'experience__company'
    
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('translator__user', 'experience')


# @admin.register(TranslatorEducation)
# class TranslatorEducationAdmin(admin.ModelAdmin):
#     list_display = ['id', 'translator_name', 'education_degree', 'education_institution', 'created_at']
#     list_filter = ['created_at']
#     search_fields = ['translator__user__email', 'translator__user__first_name', 'education__degree', 'education__institution']
#     readonly_fields = ['id', 'created_at']
#     autocomplete_fields = ['translator', 'education']
#     date_hierarchy = 'created_at'
    
#     def translator_name(self, obj):
#         return obj.translator.user.get_full_name()
#     translator_name.short_description = 'Translator'
#     translator_name.admin_order_field = 'translator__user__first_name'
    
#     def education_degree(self, obj):
#         return obj.education.degree
#     education_degree.short_description = 'Degree'
#     education_degree.admin_order_field = 'education__degree'
    
#     def education_institution(self, obj):
#         return obj.education.institution
#     education_institution.short_description = 'Institution'
#     education_institution.admin_order_field = 'education__institution'
    
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('translator__user', 'education')


# @admin.register(TranslatorCertification)
# class TranslatorCertificationAdmin(admin.ModelAdmin):
#     list_display = ['id', 'translator_name', 'certification_name', 'certification_organization', 'created_at']
#     list_filter = ['created_at']
#     search_fields = ['translator__user__email', 'translator__user__first_name', 'certification__name', 'certification__issuing_organization']
#     readonly_fields = ['id', 'created_at']
#     autocomplete_fields = ['translator', 'certification']
#     date_hierarchy = 'created_at'
    
#     def translator_name(self, obj):
#         return obj.translator.user.get_full_name()
#     translator_name.short_description = 'Translator'
#     translator_name.admin_order_field = 'translator__user__first_name'
    
#     def certification_name(self, obj):
#         return obj.certification.name
#     certification_name.short_description = 'Certification'
#     certification_name.admin_order_field = 'certification__name'
    
#     def certification_organization(self, obj):
#         return obj.certification.issuing_organization
#     certification_organization.short_description = 'Organization'
#     certification_organization.admin_order_field = 'certification__issuing_organization'
    
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('translator__user', 'certification')


@admin.register(TranslationLanguage)
class TranslationLanguageAdmin(admin.ModelAdmin):
    list_display = ['id', 'translator_name', 'language_code', 'proficiency_badge', 'created_at']
    list_filter = ['proficiency_level', 'language_code', 'created_at']
    search_fields = ['translator__user__email', 'translator__user__first_name', 'language_code']
    readonly_fields = ['id', 'created_at']
    autocomplete_fields = ['translator']
    date_hierarchy = 'created_at'
    
    def translator_name(self, obj):
        return obj.translator.user.get_full_name()
    translator_name.short_description = 'Translator'
    translator_name.admin_order_field = 'translator__user__first_name'
    
    def proficiency_badge(self, obj):
        colors = {
            'Native': '#28a745',
            'Fluent': '#17a2b8',
            'Advanced': '#ffc107',
            'Intermediate': '#6c757d',
        }
        color = colors.get(obj.proficiency_level, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.proficiency_level
        )
    proficiency_badge.short_description = 'Proficiency'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('translator__user')


# @admin.register(TranslationFee)
# class TranslationFeeAdmin(admin.ModelAdmin):
#     list_display = ['id', 'translator_name', 'service_fee_info', 'created_at', 'updated_at']
#     list_filter = ['created_at', 'updated_at']
#     search_fields = ['translator__user__email', 'translator__user__first_name']
#     readonly_fields = ['id', 'created_at', 'updated_at']
#     autocomplete_fields = ['translator', 'service_fee']
#     date_hierarchy = 'created_at'
    
#     def translator_name(self, obj):
#         return obj.translator.user.get_full_name()
#     translator_name.short_description = 'Translator'
#     translator_name.admin_order_field = 'translator__user__first_name'
    
#     def service_fee_info(self, obj):
#         return str(obj.service_fee)
#     service_fee_info.short_description = 'Service Fee'
    
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('translator__user', 'service_fee')


# @admin.register(TranslatorAvailability)
# class TranslatorAvailabilityAdmin(admin.ModelAdmin):
#     list_display = ['id', 'translator_name', 'availability_info', 'created_at', 'updated_at']
#     list_filter = ['created_at', 'updated_at']
#     search_fields = ['translator__user__email', 'translator__user__first_name']
#     readonly_fields = ['id', 'created_at', 'updated_at']
#     autocomplete_fields = ['translator', 'availability_slot']
#     date_hierarchy = 'created_at'
    
#     def translator_name(self, obj):
#         return obj.translator.user.get_full_name()
#     translator_name.short_description = 'Translator'
#     translator_name.admin_order_field = 'translator__user__first_name'
    
#     def availability_info(self, obj):
#         return str(obj.availability_slot)
#     availability_info.short_description = 'Availability'
    
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('translator__user', 'availability_slot')

@admin.register(TranslatorReview)
class TranslatorReviewAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'patient_name', 'translator_name', 'rating_stars', 
        'status_badge', 'updated_by', 'created_at'
    ]
    list_filter = ['status', 'rating', 'created_at', 'updated_at']
    search_fields = [
        'patient__user__email', 'patient__user__first_name',
        'translator__user__email', 'translator__user__first_name',
        'comment'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    # Remove 'patient' and 'appointment' from autocomplete_fields
    autocomplete_fields = ['translator', 'updated_by']
    date_hierarchy = 'created_at'
    actions = ['publish_reviews', 'hide_reviews', 'flag_reviews']
    
    fieldsets = (
        (_('Review Information'), {
            'fields': ('id', 'patient', 'translator', 'appointment', 'rating', 'comment')
        }),
        (_('Moderation'), {
            'fields': ('status', 'updated_by')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def patient_name(self, obj):
        return obj.patient.user.get_full_name()
    patient_name.short_description = 'Patient'
    patient_name.admin_order_field = 'patient__user__first_name'
    
    def translator_name(self, obj):
        return obj.translator.user.get_full_name()
    translator_name.short_description = 'Translator'
    translator_name.admin_order_field = 'translator__user__first_name'
    
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html(
            '<span style="color: #ffc107; font-size: 16px;">{}</span>',
            stars
        )
    rating_stars.short_description = 'Rating'
    
    def status_badge(self, obj):
        colors = {
            'Published': '#28a745',
            'Hidden': '#6c757d',
            'Flagged': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def publish_reviews(self, request, queryset):
        updated = queryset.update(status='Published', updated_by=request.user)
        self.message_user(request, f"{updated} review(s) successfully published.")
    publish_reviews.short_description = "Publish selected reviews"
    
    def hide_reviews(self, request, queryset):
        updated = queryset.update(status='Hidden', updated_by=request.user)
        self.message_user(request, f"{updated} review(s) successfully hidden.")
    hide_reviews.short_description = "Hide selected reviews"
    
    def flag_reviews(self, request, queryset):
        updated = queryset.update(status='Flagged', updated_by=request.user)
        self.message_user(request, f"{updated} review(s) successfully flagged.")
    flag_reviews.short_description = "Flag selected reviews"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'patient__user', 'translator__user', 'appointment', 'updated_by'
        )
