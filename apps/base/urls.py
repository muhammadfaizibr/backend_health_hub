from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, UserLanguageViewSet, EducationViewSet, ExperienceViewSet,
    CertificationViewSet, AvailabilitySlotViewSet, ServiceFeeViewSet, WalletViewSet
)

app_name = 'users'

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'languages', UserLanguageViewSet, basename='user-language')
router.register(r'education', EducationViewSet, basename='education')
router.register(r'experience', ExperienceViewSet, basename='experience')
router.register(r'certifications', CertificationViewSet, basename='certification')
router.register(r'availability-slots', AvailabilitySlotViewSet, basename='availability-slot')
router.register(r'service-fees', ServiceFeeViewSet, basename='service-fee')
router.register(r'wallets', WalletViewSet, basename='wallet')

urlpatterns = [
    path('', include(router.urls)),
]