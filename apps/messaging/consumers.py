import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message, Thread, Room
from .serializers import MessageSerializer


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Check authentication
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Check permission to access room
        has_permission = await self.check_room_permission(user, self.room_id)
        if not has_permission:
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_body = text_data_json.get('message')
            thread_id = text_data_json.get('thread_id')
            action = text_data_json.get('action', 'send')  # send, edit, delete

            if not message_body or not thread_id:
                await self.send(text_data=json.dumps({
                    'error': 'Message and thread_id are required'
                }))
                return

            user = self.scope['user']

            if action == 'send':
                # Save new message
                saved_message = await self.save_message(user, thread_id, message_body)
                
                if saved_message:
                    # Broadcast to room group
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': saved_message
                        }
                    )
            
            elif action == 'edit':
                message_id = text_data_json.get('message_id')
                if message_id:
                    edited_message = await self.edit_message(user, message_id, message_body)
                    if edited_message:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'message_edited',
                                'message': edited_message
                            }
                        )
            
            elif action == 'delete':
                message_id = text_data_json.get('message_id')
                if message_id:
                    deleted = await self.delete_message(user, message_id)
                    if deleted:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'message_deleted',
                                'message_id': message_id
                            }
                        )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))

    async def chat_message(self, event):
        """Receive message from room group and send to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message']
        }))

    async def message_edited(self, event):
        """Handle edited message."""
        await self.send(text_data=json.dumps({
            'type': 'edit',
            'data': event['message']
        }))

    async def message_deleted(self, event):
        """Handle deleted message."""
        await self.send(text_data=json.dumps({
            'type': 'delete',
            'message_id': event['message_id']
        }))

    @database_sync_to_async
    def check_room_permission(self, user, room_id):
        """Check if user has permission to access the room."""
        try:
            room = Room.objects.select_related(
                'case__patient__user',
                'case__doctor__user'
            ).get(id=room_id)
            
            return (
                room.case.patient.user == user or
                room.case.doctor.user == user or
                user.is_staff
            )
        except Room.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, user, thread_id, body):
        """Save message to database."""
        try:
            thread = Thread.objects.select_related(
                'room__case__patient__user',
                'room__case__doctor__user'
            ).get(id=thread_id)
            
            # Check permission
            case = thread.room.case
            if case.patient.user != user and case.doctor.user != user:
                return None
            
            message = Message.objects.create(
                thread=thread,
                sender=user,
                body=body
            )
            
            return MessageSerializer(message).data
        except Thread.DoesNotExist:
            return None
        except Exception:
            return None

    @database_sync_to_async
    def edit_message(self, user, message_id, body):
        """Edit existing message."""
        try:
            message = Message.objects.get(id=message_id, sender=user, deleted_at__isnull=True)
            message.body = body
            message.edited_at = timezone.now()
            message.save(update_fields=['body', 'edited_at'])
            
            return MessageSerializer(message).data
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_message(self, user, message_id):
        """Soft delete a message."""
        try:
            message = Message.objects.get(id=message_id)
            
            # Check permission
            if message.sender != user and not user.is_staff:
                return False
            
            message.deleted_at = timezone.now()
            message.save(update_fields=['deleted_at'])
            
            return True
        except Message.DoesNotExist:
            return False