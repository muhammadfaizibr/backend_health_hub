from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Q, Prefetch
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    User, UserLanguage, Education, Experience,
    Certification, AvailabilitySlot, ServiceFee, Wallet
)
from .serializers import (
    UserSerializer, UserCreateSerializer, UserLanguageSerializer,
    EducationSerializer, ExperienceSerializer, CertificationSerializer,
    AvailabilitySlotSerializer, ServiceFeeSerializer, WalletSerializer
)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role', 'is_active', 'gender']
    search_fields = ['first_name', 'last_name', 'email', 'phone_number']
    ordering_fields = ['created_at', 'first_name', 'last_name', 'email']
    ordering = ['-created_at']

    def get_permissions(self):
        """Assign permissions based on action."""
        if self.action == 'create':
            return [AllowAny()]
        elif self.action in ['me', 'update_profile']:
            return [IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        else:
            return [IsAdminUser()]

    def get_serializer_class(self):
        """Return appropriate serializer class."""
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        """Optimize queryset with prefetch and filter soft-deleted users."""
        queryset = User.objects.active_users().prefetch_related(
            Prefetch('languages', queryset=UserLanguage.objects.all())
        )
        
        # Allow admin to see all users
        if self.request.user.is_staff:
            queryset = User.objects.all().prefetch_related('languages')
        
        return queryset

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current authenticated user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch', 'put'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """Update current user profile."""
        partial = request.method == 'PATCH'
        serializer = self.get_serializer(request.user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def soft_delete(self, request, pk=None):
        """Soft delete a user."""
        user = self.get_object()
        user.soft_delete()
        return Response({'status': 'User soft deleted'}, status=status.HTTP_204_NO_CONTENT)


class UserLanguageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user languages."""
    
    queryset = UserLanguage.objects.all()
    serializer_class = UserLanguageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['language_code']

    def get_queryset(self):
        """Filter languages for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user')
        return self.queryset.filter(user=self.request.user).select_related('user')

    def perform_create(self, serializer):
        """Automatically assign current user to language."""
        serializer.save(user=self.request.user)


class EducationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing education records."""
    
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'field', 'degree']
    search_fields = ['school', 'degree', 'field']
    ordering_fields = ['start_date', 'end_date']
    ordering = ['-start_date']

    def get_queryset(self):
        """Filter education for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user')
        return self.queryset.filter(user=self.request.user).select_related('user')

    def perform_create(self, serializer):
        """Assign current user if not provided."""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Ensure users can only update their own records."""
        instance = self.get_object()
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only update your own education records.")
        serializer.save()

    def perform_destroy(self, instance):
        """Ensure users can only delete their own records."""
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own education records.")
        instance.delete()


class ExperienceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing work experience."""
    
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'employment_type']
    search_fields = ['title', 'company_or_organization', 'location']
    ordering_fields = ['start_date', 'end_date']
    ordering = ['-start_date']

    def get_queryset(self):
        """Filter experience for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user')
        return self.queryset.filter(user=self.request.user).select_related('user')

    def perform_create(self, serializer):
        """Assign current user if not provided."""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Ensure users can only update their own records."""
        instance = self.get_object()
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only update your own experience records.")
        serializer.save()

    def perform_destroy(self, instance):
        """Ensure users can only delete their own records."""
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own experience records.")
        instance.delete()


class CertificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing certifications."""
    
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'issuing_organization']
    search_fields = ['title', 'issuing_organization', 'credential_id']
    ordering_fields = ['issue_date', 'expiration_date']
    ordering = ['-issue_date']

    def get_queryset(self):
        """Filter certifications for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user', 'file')
        return self.queryset.filter(user=self.request.user).select_related('user', 'file')

    def perform_create(self, serializer):
        """Assign current user if not provided."""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Ensure users can only update their own records."""
        instance = self.get_object()
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only update your own certification records.")
        serializer.save()

    def perform_destroy(self, instance):
        """Ensure users can only delete their own records."""
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own certification records.")
        instance.delete()


class AvailabilitySlotViewSet(viewsets.ModelViewSet):
    """ViewSet for managing availability slots."""
    
    queryset = AvailabilitySlot.objects.all()
    serializer_class = AvailabilitySlotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'day_of_week', 'is_active']
    ordering_fields = ['day_of_week', 'start_time']
    ordering = ['day_of_week', 'start_time']

    def get_queryset(self):
        """Filter slots for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user')
        return self.queryset.filter(user=self.request.user, is_active=True).select_related('user')

    def perform_create(self, serializer):
        """Assign current user if not provided."""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Ensure users can only update their own records."""
        instance = self.get_object()
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only update your own availability slots.")
        serializer.save()

    def perform_destroy(self, instance):
        """Ensure users can only delete their own records."""
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own availability slots.")
        instance.delete()

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_availability(self, request):
        """Get availability slots for the current user."""
        slots = self.queryset.filter(user=request.user, is_active=True).order_by('day_of_week', 'start_time')
        serializer = self.get_serializer(slots, many=True)
        return Response(serializer.data)


class ServiceFeeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing service fees."""
    
    queryset = ServiceFee.objects.all()
    serializer_class = ServiceFeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'duration', 'is_active', 'currency']
    ordering_fields = ['duration', 'fee']
    ordering = ['duration']

    def get_queryset(self):
        """Filter fees for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user')
        return self.queryset.filter(user=self.request.user, is_active=True).select_related('user')

    def perform_create(self, serializer):
        """Assign current user if not provided."""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Ensure users can only update their own records."""
        instance = self.get_object()
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only update your own service fees.")
        serializer.save()

    def perform_destroy(self, instance):
        """Ensure users can only delete their own records."""
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own service fees.")
        instance.delete()

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_fees(self, request):
        """Get service fees for the current user."""
        fees = self.queryset.filter(user=request.user, is_active=True).order_by('duration')
        serializer = self.get_serializer(fees, many=True)
        return Response(serializer.data)


class WalletViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user wallets."""
    
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        """Filter wallet for current user or allow admin to see all."""
        if self.request.user.is_staff:
            return self.queryset.select_related('user')
        return self.queryset.filter(user=self.request.user).select_related('user')

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_wallet(self, request):
        """Get wallet for the current user."""
        try:
            wallet = Wallet.objects.select_related('user').get(user=request.user)
            serializer = self.get_serializer(wallet)
            return Response(serializer.data)
        except Wallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found for this user.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Update wallet with optimistic locking."""
        instance = self.get_object()
        
        # Ensure user can only update their own wallet
        if not request.user.is_staff and instance.user != request.user:
            raise PermissionDenied("You can only update your own wallet.")
        
        # Optimistic locking check
        provided_version = request.data.get('version')
        if provided_version is not None and int(provided_version) != instance.version:
            raise ValidationError({
                'version': 'Wallet has been updated by another process. Please refresh and try again.'
            })
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Increment version on balance updates
        if any(field in request.data for field in ['available_balance', 'pending_balance', 'total_lifetime_earnings']):
            serializer.validated_data['version'] = instance.version + 1
        
        self.perform_update(serializer)
        return Response(serializer.data)