from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from .models import Ticket, TicketMessage, TicketAttachment
from .serializers import TicketSerializer, TicketMessageSerializer, TicketAttachmentSerializer
from rest_framework.serializers import ValidationError



class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.select_related('created_by', 'assigned_to', 'resolved_by', 'closed_by')
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'category', 'priority']

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TicketMessageViewSet(viewsets.ModelViewSet):
    queryset = TicketMessage.objects.select_related('ticket', 'sender')
    serializer_class = TicketMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        ticket_id = self.kwargs.get('ticket_pk')
        return self.queryset.filter(ticket_id=ticket_id)

    def perform_create(self, serializer):
        ticket = Ticket.objects.get(id=self.kwargs['ticket_pk'])
        if not self.request.user.is_staff and ticket.created_by != self.request.user:
            raise ValidationError("Cannot add message to this ticket.")
        serializer.save(ticket=ticket)


class TicketAttachmentViewSet(viewsets.ModelViewSet):
    queryset = TicketAttachment.objects.select_related('ticket_message', 'file')
    serializer_class = TicketAttachmentSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]  # Attachments managed by staff

    def get_queryset(self):
        message_id = self.kwargs.get('message_pk')
        return self.queryset.filter(ticket_message_id=message_id)