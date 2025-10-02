from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FileViewSet

router = DefaultRouter()
router.register(r'files', FileViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('files/<uuid:pk>/download/', FileViewSet.as_view({'get': 'download'}), name='download_file'),
]   