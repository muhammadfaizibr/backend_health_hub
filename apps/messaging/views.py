from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Max
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Room, Thread, Message
from .serializers import RoomSerializer, ThreadSerializer, MessageSerializer
from apps.patients.models import Case


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['case']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Room.objects.select_related('case__patient__user', 'case__doctor__user')
        user = self.request.user

        if user.role == 'Patient':
            return queryset.filter(case__patient__user=user)
        elif user.role == 'Doctor':
            return queryset.filter(case__doctor__user=user)
        elif user.is_staff:
            return queryset
        
        return queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        case_id = self.request.data.get('case')
        
        if not case_id:
            raise ValidationError({'case': 'Case ID is required.'})
        
        try:
            case = Case.objects.select_related('patient__user', 'doctor__user').get(id=case_id)
        except Case.DoesNotExist:
            raise ValidationError({'case': 'Case not found.'})
        
        # Check if room already exists
        if hasattr(case, 'chat_room'):
            raise ValidationError({'case': 'Chat room already exists for this case.'})
        
        # Permission check
        user = self.request.user
        if case.patient.user != user and case.doctor.user != user:
            raise PermissionDenied("You don't have permission to create a room for this case.")
        
        serializer.save(case=case)

    @action(detail=True, methods=['get'])
    def threads(self, request, pk=None):
        """Get all threads in a room."""
        room = self.get_object()
        threads = room.threads.select_related('created_by').annotate(
            message_count=Count('messages', filter=Q(messages__deleted_at__isnull=True)),
            last_message_at=Max('messages__sent_at', filter=Q(messages__deleted_at__isnull=True))
        ).order_by('-last_message_at')
        
        page = self.paginate_queryset(threads)
        if page is not None:
            serializer = ThreadSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ThreadSerializer(threads, many=True)
        return Response(serializer.data)


class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.all()
    serializer_class = ThreadSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['room']
    search_fields = ['title', 'body']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Thread.objects.select_related(
            'room__case__patient__user',
            'room__case__doctor__user',
            'created_by'
        )
        user = self.request.user

        if user.role == 'Patient':
            return queryset.filter(room__case__patient__user=user)
        elif user.role == 'Doctor':
            return queryset.filter(room__case__doctor__user=user)
        elif user.is_staff:
            return queryset
        
        return queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        room_id = self.request.data.get('room')
        
        if not room_id:
            raise ValidationError({'room': 'Room ID is required.'})
        
        try:
            room = Room.objects.select_related('case__patient__user', 'case__doctor__user').get(id=room_id)
        except Room.DoesNotExist:
            raise ValidationError({'room': 'Room not found.'})
        
        # Permission check
        user = self.request.user
        if room.case.patient.user != user and room.case.doctor.user != user:
            raise PermissionDenied("You don't have permission to create threads in this room.")
        
        serializer.save(room=room, created_by=user)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get all messages in a thread."""
        thread = self.get_object()
        messages = thread.messages.filter(
            deleted_at__isnull=True
        ).select_related('sender').order_by('sent_at')
        
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['thread', 'sender']
    ordering = ['sent_at']

    def get_queryset(self):
        queryset = Message.objects.select_related(
            'thread__room__case__patient__user',
            'thread__room__case__doctor__user',
            'sender'
        ).filter(deleted_at__isnull=True)