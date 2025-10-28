from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Q, Prefetch
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db import IntegrityError

from .models import (
    User, UserLanguage, Education, Experience,
    Certification, AvailabilitySlot, ServiceFee, Wallet
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserLanguageSerializer,
    EducationSerializer, ExperienceSerializer, CertificationSerializer,
    AvailabilitySlotSerializer, ServiceFeeSerializer, WalletSerializer,
    UserLoginSerializer, ChangePasswordSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from .permissions import BaseReadOnlyPermission

class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    Returns user data with JWT tokens upon successful registration.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """Handle user registration."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

class UserLoginView(generics.GenericAPIView):
    """
    API endpoint for user login.
    Returns user data with JWT tokens upon successful authentication.
    """
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Handle user login."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Serialize the user object using UserSerializer
        user_data = UserSerializer(serializer.validated_data['user']).data
        
        return Response({
            'user': user_data,
            'access_token': serializer.validated_data['access_token'],
            'refresh_token': serializer.validated_data['refresh_token'],
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """
    API endpoint for user logout.
    Blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle user logout by blacklisting refresh token."""
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'message': 'Successfully logged out.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': 'Invalid token or token already blacklisted.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChangePasswordView(generics.UpdateAPIView):
    """
    API endpoint for changing password for authenticated users.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        """Handle password change."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {'message': 'Password changed successfully.'},
            status=status.HTTP_200_OK
        )


class ForgotPasswordView(generics.GenericAPIView):
    """
    API endpoint for requesting password reset.
    Sends password reset email with token.
    """
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Handle forgot password request."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.context.get('user')
        
        if user:
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create reset link (adjust URL based on your frontend)
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
            
            # Send email (configure your email backend in settings)
            try:
                send_mail(
                    subject='Password Reset Request',
                    message=f'Click the link below to reset your password:\n\n{reset_link}\n\nThis link will expire in 24 hours.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as e:
                # Log the error but don't reveal it to user
                pass
        
        # Always return success to prevent email enumeration
        return Response(
            {'message': 'If an account exists with this email, a password reset link has been sent.'},
            status=status.HTTP_200_OK
        )


class ResetPasswordView(generics.GenericAPIView):
    """
    API endpoint for resetting password with token.
    """
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Handle password reset."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {'message': 'Password has been reset successfully.'},
            status=status.HTTP_200_OK
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
        if self.action in ['me', 'update_profile', 'delete_account']:
            return [IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        else:
            return [IsAdminUser()]

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
        
        # Prevent role change via this endpoint
        if 'role' in request.data and not request.user.is_staff:
            return Response(
                {'error': 'You cannot change your role.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(request.user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def delete_account(self, request):
        """Soft delete current user account."""
        user = request.user
        user.soft_delete()
        return Response(
            {'message': 'Account deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def soft_delete(self, request, pk=None):
        """Soft delete a user (admin only)."""
        user = self.get_object()
        user.soft_delete()
        return Response(
            {'message': 'User soft deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def activate(self, request, pk=None):
        """Activate a user account (admin only)."""
        user = self.get_object()
        user.is_active = True
        user.deleted_at = None
        user.save(update_fields=['is_active', 'deleted_at'])
        return Response(
            {'message': 'User activated successfully.'},
            status=status.HTTP_200_OK
        )



class UserLanguageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user languages."""
    
    queryset = UserLanguage.objects.all()
    serializer_class = UserLanguageSerializer
    permission_classes = [IsAuthenticated, BaseReadOnlyPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['language_code', 'user']

    def get_queryset(self):
        """
        Allow filtering by user parameter for public viewing.
        If no filter, show only current user's languages.
        """
        queryset = self.queryset.select_related('user')
        
        # Allow filtering by user parameter (for viewing doctor profiles)
        user_id = self.request.query_params.get('user', None)
        if user_id:
            return queryset.filter(user_id=user_id)
        
        # If no user filter and not staff, show only own records
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        
        return queryset

    def perform_create(self, serializer):
        """Automatically assign current user to language."""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Ensure users can only update their own records."""
        instance = self.get_object()
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only update your own language records.")
        serializer.save()

    def perform_destroy(self, instance):
        """Ensure users can only delete their own records."""
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own language records.")
        instance.delete()


class EducationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing education records."""
    
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated, BaseReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'field', 'degree']
    search_fields = ['school', 'degree', 'field']
    ordering_fields = ['start_date', 'end_date']
    ordering = ['-start_date']

    def get_queryset(self):
        """
        Allow filtering by user parameter for public viewing.
        If no filter, show only current user's education.
        """
        queryset = self.queryset.select_related('user')
        
        # Allow filtering by user parameter (for viewing doctor profiles)
        user_id = self.request.query_params.get('user', None)
        if user_id:
            return queryset.filter(user_id=user_id)
        
        # If no user filter and not staff, show only own records
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        
        return queryset

    def perform_create(self, serializer):
        """Assign current user."""
        serializer.save(user=self.request.user)

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
    permission_classes = [IsAuthenticated, BaseReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'employment_type']
    search_fields = ['title', 'company_or_organization', 'location']
    ordering_fields = ['start_date', 'end_date']
    ordering = ['-start_date']

    def get_queryset(self):
        """
        Allow filtering by user parameter for public viewing.
        If no filter, show only current user's experience.
        """
        queryset = self.queryset.select_related('user')
        
        # Allow filtering by user parameter (for viewing doctor profiles)
        user_id = self.request.query_params.get('user', None)
        if user_id:
            return queryset.filter(user_id=user_id)
        
        # If no user filter and not staff, show only own records
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        
        return queryset

    def perform_create(self, serializer):
        """Assign current user."""
        serializer.save(user=self.request.user)

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
    permission_classes = [IsAuthenticated, BaseReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'issuing_organization']
    search_fields = ['title', 'issuing_organization', 'credential_id']
    ordering_fields = ['issue_date', 'expiration_date']
    ordering = ['-issue_date']

    def get_queryset(self):
        """
        Allow filtering by user parameter for public viewing.
        If no filter, show only current user's certifications.
        """
        queryset = self.queryset.select_related('user', 'file')
        
        # Allow filtering by user parameter (for viewing doctor profiles)
        user_id = self.request.query_params.get('user', None)
        if user_id:
            return queryset.filter(user_id=user_id)
        
        # If no user filter and not staff, show only own records
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        
        return queryset

    def perform_create(self, serializer):
        """Assign current user."""
        serializer.save(user=self.request.user)

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
    permission_classes = [IsAuthenticated, BaseReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'day_of_week', 'is_active']
    ordering_fields = ['day_of_week', 'start_time']
    ordering = ['day_of_week', 'start_time']

    def get_queryset(self):
        """
        Allow filtering by user parameter for public viewing.
        If no filter, show only current user's slots.
        """
        queryset = self.queryset.select_related('user')
        
        # Allow filtering by user parameter (for viewing doctor profiles)
        user_id = self.request.query_params.get('user', None)
        if user_id:
            return queryset.filter(user_id=user_id)
        
        # If no user filter and not staff, show only own records
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        
        return queryset

    def perform_create(self, serializer):
        """Assign current user."""
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Handle creation with duplicate detection."""
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError as e:
            if 'unique constraint' in str(e).lower() or 'duplicate key' in str(e).lower():
                return Response(
                    {
                        "error": "Duplicate availability slot",
                        "detail": "An availability slot with this day, start time, and end time already exists."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            raise

    def update(self, request, *args, **kwargs):
        """Handle update with duplicate detection."""
        try:
            return super().update(request, *args, **kwargs)
        except IntegrityError as e:
            if 'unique constraint' in str(e).lower() or 'duplicate key' in str(e).lower():
                return Response(
                    {
                        "error": "Duplicate availability slot",
                        "detail": "An availability slot with this day, start time, and end time already exists."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            raise

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
        slots = self.queryset.filter(user=request.user).order_by('day_of_week', 'start_time')
        serializer = self.get_serializer(slots, many=True)
        return Response(serializer.data)


class ServiceFeeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing service fees."""
    
    queryset = ServiceFee.objects.all()
    serializer_class = ServiceFeeSerializer
    permission_classes = [IsAuthenticated, BaseReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'duration', 'is_active', 'currency']
    ordering_fields = ['duration', 'fee']
    ordering = ['duration']

    def get_queryset(self):
        """
        Allow filtering by user parameter for public viewing.
        If no filter, show only current user's fees.
        """
        queryset = self.queryset.select_related('user')
        
        # Allow filtering by user parameter (for viewing doctor profiles)
        user_id = self.request.query_params.get('user', None)
        if user_id:
            return queryset.filter(user_id=user_id)
        
        # If no user filter and not staff, show only own records
        if not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        
        return queryset

    def perform_create(self, serializer):
        """Assign current user."""
        serializer.save(user=self.request.user)

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
        fees = self.queryset.filter(user=request.user).order_by('duration')
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