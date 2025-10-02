from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoomViewSet, ThreadViewSet, MessageViewSet

app_name = 'messaging'

router = DefaultRouter()
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'threads', ThreadViewSet, basename='thread')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]