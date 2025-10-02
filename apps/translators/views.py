from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import (
    Profile, TranslatorExperience, TranslatorEducation, TranslatorCertification,
    TranslationLanguage, TranslationFee, TranslatorAvailability, TranslatorReview
)
from .serializers import (
    ProfileSerializer, TranslatorExperienceSerializer, TranslatorEducationSerializer,
    TranslatorCertificationSerializer, TranslationLanguageSerializer, TranslationFeeSerializer,
    TranslatorAvailabilitySerializer, TranslatorReviewSerializer
)
from .permissions import IsTranslatorOrReadOnly, IsPatientOrStaff
from rest_framework.serializers import ValidationError


class ProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing translator profiles.
    Translators can only access their own profile.
    Staff can access all profiles.
    """
    
    queryset = Profile.objects.select_related('user').prefetch_related(
        'experiences__experience',
        'educations__education',
        'certifications__certification',
        'languages',
        'fees__service_fee',
        'availabilities__availability_slot'
    )
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_verified', 'area_of_focus', 'currency']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'area_of_focus']
    ordering_fields = ['created_at', 'is_verified']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'role') and user.role == 'Translator':
            return self.queryset.filter(user=user)
        else:
            # Other users can only view verified profiles
            return self.queryset.filter(is_verified=True)

    @transaction.atomic
    def perform_create(self, serializer):
        if self.request.user.role == 'Translator':
            # Check if profile already exists
            if Profile.objects.filter(user=self.request.user).exists():
                raise ValidationError("Translator profile already exists for this user.")
            serializer.save(user=self.request.user)
        else:
            raise ValidationError("Only translators can create a translator profile.")

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify(self, request, pk=None):
        """Admin action to verify a translator profile."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can verify profiles.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        profile = self.get_object()
        profile.is_verified = True
        profile.save()
        
        return Response({'message': 'Profile verified successfully.'})


class TranslatorExperienceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translator experiences."""
    
    queryset = TranslatorExperience.objects.select_related('translator__user', 'experience')
    serializer_class = TranslatorExperienceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'translator_profile'):
            return self.queryset.filter(translator=user.translator_profile)
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        translator = get_object_or_404(Profile, user=self.request.user)
        serializer.save(translator=translator)


class TranslatorEducationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translator education."""
    
    queryset = TranslatorEducation.objects.select_related('translator__user', 'education')
    serializer_class = TranslatorEducationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'translator_profile'):
            return self.queryset.filter(translator=user.translator_profile)
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        translator = get_object_or_404(Profile, user=self.request.user)
        serializer.save(translator=translator)


class TranslatorCertificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translator certifications."""
    
    queryset = TranslatorCertification.objects.select_related('translator__user', 'certification')
    serializer_class = TranslatorCertificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'translator_profile'):
            return self.queryset.filter(translator=user.translator_profile)
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        translator = get_object_or_404(Profile, user=self.request.user)
        serializer.save(translator=translator)


class TranslationFeeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translation fees."""
    
    queryset = TranslationFee.objects.select_related('translator__user', 'service_fee')
    serializer_class = TranslationFeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'translator_profile'):
            return self.queryset.filter(translator=user.translator_profile)
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        translator = get_object_or_404(Profile, user=self.request.user)
        serializer.save(translator=translator)


class TranslatorAvailabilityViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translator availability."""
    
    queryset = TranslatorAvailability.objects.select_related('translator__user', 'availability_slot')
    serializer_class = TranslatorAvailabilitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'translator_profile'):
            return self.queryset.filter(translator=user.translator_profile)
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        translator = get_object_or_404(Profile, user=self.request.user)
        serializer.save(translator=translator)


class TranslationLanguageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translation languages."""
    
    queryset = TranslationLanguage.objects.select_related('translator__user')
    serializer_class = TranslationLanguageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['language_code', 'proficiency_level']
    search_fields = ['language_code']
    ordering = ['proficiency_level', 'language_code']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'translator_profile'):
            return self.queryset.filter(translator=user.translator_profile)
        return self.queryset.none()

    @transaction.atomic
    def perform_create(self, serializer):
        translator = get_object_or_404(Profile, user=self.request.user)
        serializer.save(translator=translator)


class TranslatorReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for managing translator reviews."""
    
    queryset = TranslatorReview.objects.select_related(
        'patient__user', 'translator__user', 'appointment', 'updated_by'
    )
    serializer_class = TranslatorReviewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'rating', 'translator']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff:
            return self.queryset.all()
        elif hasattr(user, 'patient_profile'):
            # Patients see their own reviews
            return self.queryset.filter(patient=user.patient_profile)
        elif hasattr(user, 'translator_profile'):
            # Translators see published reviews about them
            return self.queryset.filter(translator=user.translator_profile, status='Published')
        else:
            # Public can only see published reviews
            return self.queryset.filter(status='Published')

    @transaction.atomic
    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'patient_profile'):
            raise ValidationError("Only patients can create reviews.")
        serializer.save(patient=self.request.user.patient_profile)

    @transaction.atomic
    def perform_update(self, serializer):
        # Only staff can update status
        if 'status' in serializer.validated_data and not self.request.user.is_staff:
            raise ValidationError("Only staff can change review status.")
        
        if self.request.user.is_staff and 'status' in serializer.validated_data:
            serializer.save(updated_by=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def flag(self, request, pk=None):
        """Flag a review for moderation."""
        review = self.get_object()
        review.status = 'Flagged'
        review.save()
        return Response({'message': 'Review flagged for moderation.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def publish(self, request, pk=None):
        """Publish a flagged/hidden review (staff only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can publish reviews.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        review = self.get_object()
        review.status = 'Published'
        review.updated_by = request.user
        review.save()
        
        return Response({'message': 'Review published successfully.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def hide(self, request, pk=None):
        """Hide a review (staff only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can hide reviews.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        review = self.get_object()
        review.status = 'Hidden'
        review.updated_by = request.user
        review.save()
        
        return Response({'message': 'Review hidden successfully.'})