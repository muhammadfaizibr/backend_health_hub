from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import Settings, RateLimit
from .serializers import SettingsSerializer, RateLimitSerializer
from django.db.models import Q
from rest_framework.decorators import action
from datetime import timedelta  


class SettingsViewSet(viewsets.ModelViewSet):
    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_public', 'value_type']

    def get_queryset(self):
        if not self.request.user.is_staff:
            return self.queryset.filter(is_public=True)
        return self.queryset.all()


class RateLimitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RateLimit.objects.select_related('user')
    serializer_class = RateLimitSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['action_type', 'blocked_until']

    def get_queryset(self):
        return self.queryset.filter(Q(user=self.request.user) | Q(ip_address=self.request.META.get('REMOTE_ADDR')))

    @action(detail=False, methods=['post'])
    def increment(self, request):
        # Utility to increment rate limit, called from middleware or views
        action_type = request.data['action_type']
        user = request.user if request.user.is_authenticated else None
        ip = request.META.get('REMOTE_ADDR')
        window_start = timezone.now().replace(minute=0, second=0, microsecond=0)  # Hourly window example
        rate_limit, created = RateLimit.objects.get_or_create(
            user=user,
            ip_address=ip if not user else None,
            action_type=action_type,
            window_start=window_start,
            defaults={'attempt_count': 1}
        )
        if not created:
            rate_limit.attempt_count += 1
            rate_limit.save()
        # Check if blocked
        if rate_limit.attempt_count > 5:  # Example limit
            rate_limit.blocked_until = window_start + timedelta(hours=1)
            rate_limit.save()
        return Response({'blocked': rate_limit.blocked_until is not None})