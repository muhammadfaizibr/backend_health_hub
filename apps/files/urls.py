from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FileViewSet

router = DefaultRouter()
router.register(r'files', FileViewSet, basename='file')

urlpatterns = [
    path('', include(router.urls)),
]

# Router automatically generates these URLs:
# GET    /api/files/                  - List files
# POST   /api/files/                  - Upload file
# GET    /api/files/{id}/             - Retrieve file details
# PATCH  /api/files/{id}/             - Partial update file
# DELETE /api/files/{id}/             - Soft delete file
# GET    /api/files/{id}/download/    - Download file
# POST   /api/files/{id}/restore/     - Restore deleted file (staff only)
# DELETE /api/files/{id}/permanent_delete/ - Permanently delete file (staff only)