from rest_framework import serializers
from django.utils import timezone
from .models import Room, Thread, Message
from apps.base.serializers import UserSerializer


class RoomSerializer(serializers.ModelSerializer):
    case_id = serializers.UUIDField(source='case.id', read_only=True)
    case_title = serializers.CharField(source='case.title', read_only=True)
    thread_count = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'case', 'case_id', 'case_title', 
            'thread_count', 'message_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_thread_count(self, obj):
        return obj.threads.count()

    def get_message_count(self, obj):
        return Message.objects.filter(
            thread__room=obj, 
            deleted_at__isnull=True
        ).count()


class ThreadSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    room_id = serializers.UUIDField(source='room.id', read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = [
            'id', 'room', 'room_id', 'created_by', 'title', 'body',
            'message_count', 'last_message_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_message_count(self, obj):
        return obj.messages.filter(deleted_at__isnull=True).count()

    def get_last_message_at(self, obj):
        last_message = obj.messages.filter(
            deleted_at__isnull=True
        ).order_by('-sent_at').first()
        return last_message.sent_at if last_message else None

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        if len(value) > 255:
            raise serializers.ValidationError("Title exceeds maximum length.")
        return value.strip()

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Body cannot be empty.")
        return value.strip()


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    thread_id = serializers.UUIDField(source='thread.id', read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'thread', 'thread_id', 'sender', 'body',
            'sent_at', 'edited_at', 'deleted_at',
            'is_edited', 'is_deleted'
        ]
        read_only_fields = ['id', 'sender', 'sent_at', 'edited_at', 'deleted_at']

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message body cannot be empty.")
        if len(value) > 10000:
            raise serializers.ValidationError("Message exceeds maximum length of 10,000 characters.")
        return value.strip()

    def update(self, instance, validated_data):
        """Handle message editing."""
        if 'body' in validated_data:
            instance.body = validated_data['body']
            instance.edited_at = timezone.now()
            instance.save(update_fields=['body', 'edited_at'])
        return instance