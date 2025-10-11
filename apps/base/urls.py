from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    UserViewSet, UserLanguageViewSet, EducationViewSet, ExperienceViewSet,
    CertificationViewSet, AvailabilitySlotViewSet, ServiceFeeViewSet, WalletViewSet,
    UserRegistrationView, UserLoginView, UserLogoutView, ChangePasswordView,
    ForgotPasswordView, ResetPasswordView
)

app_name = 'users'

# Router for ViewSets
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
    # Authentication endpoints
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'), 
    path('auth/logout/', UserLogoutView.as_view(), name='logout'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    # JWT token endpoints
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Include router URLs
    path('', include(router.urls)),
]