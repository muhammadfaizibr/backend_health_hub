from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProfileViewSet, TranslatorExperienceViewSet, TranslatorEducationViewSet,
    TranslatorCertificationViewSet, TranslationLanguageViewSet, TranslationFeeViewSet,
    TranslatorAvailabilityViewSet, TranslatorReviewViewSet
)

app_name = 'translators'

router = DefaultRouter()
router.register(r'profiles', ProfileViewSet, basename='profile')
router.register(r'experiences', TranslatorExperienceViewSet, basename='experience')
router.register(r'educations', TranslatorEducationViewSet, basename='education')
router.register(r'certifications', TranslatorCertificationViewSet, basename='certification')
router.register(r'languages', TranslationLanguageViewSet, basename='language')
router.register(r'fees', TranslationFeeViewSet, basename='fee')
router.register(r'availabilities', TranslatorAvailabilityViewSet, basename='availability')
router.register(r'reviews', TranslatorReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]