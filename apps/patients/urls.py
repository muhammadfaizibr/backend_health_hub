# apps/patients/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProfileViewSet, MedicalHistoryViewSet, CaseViewSet,
    AppointmentTimeSlotViewSet, AppointmentViewSet, ReportViewSet
)

router = DefaultRouter()
router.register(r'profiles', ProfileViewSet)
router.register(r'medical-history', MedicalHistoryViewSet)
router.register(r'cases', CaseViewSet)
router.register(r'time-slots', AppointmentTimeSlotViewSet)
router.register(r'appointments', AppointmentViewSet)
router.register(r'reports', ReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('cases/<uuid:pk>/assign_doctor/', CaseViewSet.as_view({'patch': 'assign_doctor'}), name='assign_doctor'),
    path('appointments/book/', AppointmentViewSet.as_view({'post': 'book_appointment'}), name='book_appointment'),
    path('appointments/<uuid:pk>/join/', AppointmentViewSet.as_view({'post': 'join'}), name='join_appointment'),
    path('appointments/<uuid:pk>/confirm/', AppointmentViewSet.as_view({'post': 'confirm'}), name='confirm_appointment'),
    path('appointments/<uuid:pk>/cancel/', AppointmentViewSet.as_view({'post': 'cancel'}), name='cancel_appointment'),
]