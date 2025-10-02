from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, TicketMessageViewSet, TicketAttachmentViewSet

router = DefaultRouter()
router.register(r'tickets', TicketViewSet)

# Use unique named groups for nested paths to avoid regex group redefinition
message_router = DefaultRouter()
message_router.register(r'messages', TicketMessageViewSet, basename='ticket-message')

attachment_router = DefaultRouter()
attachment_router.register(r'attachments', TicketAttachmentViewSet, basename='ticket-message-attachment')

urlpatterns = [
    path('', include(router.urls)),
    # Use unique pk names: ticket_pk for outer, message_pk for inner
    path('tickets/<uuid:ticket_pk>/', include(message_router.urls)),
    path('tickets/<uuid:ticket_pk>/messages/<uuid:message_pk>/', include(attachment_router.urls)),
]