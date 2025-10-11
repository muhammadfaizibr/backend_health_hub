from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProfileViewSet, 
    # DoctorExperienceViewSet, DoctorEducationViewSet, DoctorCertificationViewSet, ConsultationFeeViewSet, DoctorAvailabilityViewSet,
    PrescriptionViewSet, PrescriptionItemViewSet, DoctorReviewViewSet
)

app_name = 'doctors'

router = DefaultRouter()
router.register(r'profiles', ProfileViewSet, basename='profile')
# router.register(r'experiences', DoctorExperienceViewSet, basename='experience')
# router.register(r'educations', DoctorEducationViewSet, basename='education')
# router.register(r'certifications', DoctorCertificationViewSet, basename='certification')
# router.register(r'consultation-fees', ConsultationFeeViewSet, basename='consultation-fee')
# router.register(r'availabilities', DoctorAvailabilityViewSet, basename='availability')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'prescription-items', PrescriptionItemViewSet, basename='prescription-item')
router.register(r'reviews', DoctorReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]