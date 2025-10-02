from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SettingsViewSet, RateLimitViewSet

router = DefaultRouter()
router.register(r'settings', SettingsViewSet)
router.register(r'rate-limits', RateLimitViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('rate-limits/increment/', RateLimitViewSet.as_view({'post': 'increment'}), name='increment_rate_limit'),
]