from rest_framework import serializers
from .models import Ticket, TicketMessage, TicketAttachment
from apps.base.serializers import UserSerializer
from datetime import timezone
from apps.files.serializers import FileSerializer


class TicketSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)
    closed_by = UserSerializer(read_only=True)
    ticket_number = serializers.ReadOnlyField()

    class Meta:
        model = Ticket
        fields = '__all__'
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Auto-generate ticket_number
        last_ticket = Ticket.objects.order_by('-created_at').first()
        validated_data['ticket_number'] = (last_ticket.ticket_number + 1) if last_ticket else 1
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'status' in validated_data:
            status = validated_data['status']
            if status == 'Resolved':
                validated_data['resolved_at'] = timezone.now()
                validated_data['resolved_by'] = self.context['request'].user
            elif status == 'Closed':
                validated_data['closed_at'] = timezone.now()
                validated_data['closed_by'] = self.context['request'].user
        return super().update(instance, validated_data)


class TicketMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = TicketMessage
        fields = '__all__'
        read_only_fields = ['id', 'sent_at']

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)


class TicketAttachmentSerializer(serializers.ModelSerializer):
    file = FileSerializer(read_only=True)

    class Meta:
        model = TicketAttachment
        fields = '__all__'
        read_only_fields = ['id', 'created_at']