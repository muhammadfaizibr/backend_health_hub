from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProfileViewSet, TranslationLanguageViewSet, TranslatorReviewViewSet,
)

app_name = 'translators'

router = DefaultRouter()
router.register(r'profiles', ProfileViewSet, basename='profile')
router.register(r'languages', TranslationLanguageViewSet, basename='language')
router.register(r'reviews', TranslatorReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]