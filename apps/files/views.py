from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .models import File
from .serializers import FileSerializer
from django.core.files.storage import default_storage
from django.conf import settings
import uuid
from django.http import FileResponse
from django.db.models import Q
from datetime import timezone

class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.select_related('uploaded_by', 'related_to_user', 'deleted_by').filter(deleted_at__isnull=True)
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['file_type', 'is_public', 'related_to_user']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(Q(uploaded_by=self.request.user) | Q(related_to_user=self.request.user) | Q(is_public=True))
        return qs

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user, related_to_user=self.request.user if self.request.data.get('related_to_user') else None)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        file_obj = self.get_object()
        if not file_obj.is_public and file_obj.related_to_user != request.user and file_obj.uploaded_by != request.user and not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        # For private, could generate signed URL, but for local, serve directly
        response = FileResponse(open(file_obj.file_path, 'rb'), content_type=file_obj.mime_type)
        response['Content-Disposition'] = f'attachment; filename="{file_obj.original_filename}"'
        return response

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save()