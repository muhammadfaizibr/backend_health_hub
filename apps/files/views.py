from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.http import FileResponse, Http404
from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
import uuid
import os
import mimetypes

from .models import File
from .serializers import FileSerializer, FileUploadSerializer, FileListSerializer
from apps.base.models import User


class FileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing file uploads and downloads.
    Supports filtering, soft deletion, and access control.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['file_type', 'is_public', 'related_to_user']
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Filter files based on user permissions"""
        qs = File.objects.select_related(
            'uploaded_by', 'related_to_user', 'deleted_by'
        ).filter(deleted_at__isnull=True)

        if not self.request.user.is_staff:
            qs = qs.filter(
                Q(uploaded_by=self.request.user) | 
                Q(related_to_user=self.request.user) | 
                Q(is_public=True)
            )
        
        return qs

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return FileUploadSerializer
        elif self.action == 'list':
            return FileListSerializer
        return FileSerializer

    def create(self, request, *args, **kwargs):
        """Handle file upload"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {'error': 'No file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get validated data
        file_type = serializer.validated_data['file_type']
        is_public = serializer.validated_data.get('is_public', False)
        storage_provider = serializer.validated_data.get('storage_provider', 'local')
        related_to_user_id = serializer.validated_data.get('related_to_user_id')

        # Resolve related_to_user
        related_to_user = None
        if related_to_user_id:
            try:
                related_to_user = User.objects.get(id=related_to_user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Related user not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Generate safe file path
        safe_filename = self._generate_safe_filename(file_obj.name)
        file_path = f"{file_type}/{uuid.uuid4()}_{safe_filename}"

        try:
            # Save file to storage
            saved_path = default_storage.save(file_path, file_obj)

            # Create File record
            file_instance = File.objects.create(
                uploaded_by=request.user,
                related_to_user=related_to_user,
                file_type=file_type,
                original_filename=file_obj.name,
                file_path=saved_path,
                file_size=file_obj.size,
                mime_type=file_obj.content_type or 'application/octet-stream',
                storage_provider=storage_provider,
                is_public=is_public
            )

            response_serializer = FileSerializer(
                file_instance, 
                context={'request': request}
            )
            return Response(
                response_serializer.data, 
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            # Clean up file if database operation fails
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
            return Response(
                {'error': f'File upload failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Prevent full updates, only allow partial updates"""
        return Response(
            {'error': 'Full update not allowed. Use PATCH for partial updates.'}, 
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def partial_update(self, request, *args, **kwargs):
        """Allow updating only specific fields"""
        instance = self.get_object()
        
        # Only allow updating these fields
        allowed_fields = ['file_type', 'is_public']
        update_data = {
            key: value for key, value in request.data.items() 
            if key in allowed_fields
        }
        
        serializer = self.get_serializer(
            instance, 
            data=update_data, 
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download file with proper access control"""
        file_instance = self.get_object()

        # Check permissions
        if not file_instance.can_access(request.user):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if file exists in storage
        if not default_storage.exists(file_instance.file_path):
            return Response(
                {'error': 'File not found in storage'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Get absolute path for local storage
            file_path = default_storage.path(file_instance.file_path)
            
            # Determine content type
            content_type = file_instance.mime_type
            if not content_type or content_type == 'application/octet-stream':
                content_type = mimetypes.guess_type(file_instance.original_filename)[0] or 'application/octet-stream'

            # Open and return file
            file_handle = default_storage.open(file_instance.file_path, 'rb')
            response = FileResponse(file_handle, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{file_instance.original_filename}"'
            response['Content-Length'] = file_instance.file_size
            
            return response

        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve file: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        """Soft delete file"""
        instance = self.get_object()
        
        # Mark as deleted
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        instance.save(update_fields=['deleted_at', 'deleted_by'])
        
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore soft-deleted file (staff only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can restore files'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Get file even if deleted
        file_instance = get_object_or_404(File, pk=pk)
        
        if not file_instance.is_deleted():
            return Response(
                {'error': 'File is not deleted'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        file_instance.deleted_at = None
        file_instance.deleted_by = None
        file_instance.save(update_fields=['deleted_at', 'deleted_by'])

        serializer = self.get_serializer(file_instance)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'])
    def permanent_delete(self, request, pk=None):
        """Permanently delete file from storage and database (staff only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can permanently delete files'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        file_instance = get_object_or_404(File, pk=pk)

        # Delete from storage
        if default_storage.exists(file_instance.file_path):
            try:
                default_storage.delete(file_instance.file_path)
            except Exception as e:
                return Response(
                    {'error': f'Failed to delete file from storage: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Delete from database
        file_instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _generate_safe_filename(self, filename):
        """Generate a safe filename by removing potentially dangerous characters"""
        # Get file extension
        name, ext = os.path.splitext(filename)
        
        # Remove or replace unsafe characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        safe_name = ''.join(c if c in safe_chars else '_' for c in name)
        
        # Ensure filename isn't empty
        if not safe_name:
            safe_name = 'file'
        
        # Limit filename length (keep extension)
        max_length = 100
        if len(safe_name) > max_length:
            safe_name = safe_name[:max_length]
        
        return f"{safe_name}{ext}"