from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError  # Changed import
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Q, Avg, Count, Value, CharField
from django.db.models.functions import Concat

from .models import (
    Profile, 
    Prescription, PrescriptionItem, DoctorReview
)
from .serializers import (
    ProfileSerializer, 
    PrescriptionSerializer, PrescriptionItemSerializer, DoctorReviewSerializer
)


class ProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for doctor profiles with enhanced search and filter."""
    
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['specialization', 'is_verified', 'years_of_experience']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'specialization', 'about']
    ordering_fields = ['created_at', 'years_of_experience', 'avg_rating']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter profiles based on user role with optimized queries."""
        queryset = self.queryset.select_related('user').annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__status='Published')),
            review_count=Count('reviews', filter=Q(reviews__status='Published'))
        )
        
        if self.request.user.role == 'Doctor':
            return queryset.filter(user=self.request.user)
        elif self.request.user.is_staff:
            return queryset
        else:
            # Patients and others can only see verified doctors
            return queryset.filter(is_verified=True)

    def perform_create(self, serializer):
        """Create profile for current user if they're a doctor."""
        if self.request.user.role != 'Doctor':
            raise PermissionDenied("Only doctors can create doctor profiles.")
        
        if Profile.objects.filter(user=self.request.user).exists():
            raise ValidationError({'error': 'Doctor profile already exists for this user.'})
        
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def search_doctors(self, request):
        """
        Enhanced search endpoint with category-first approach.
        
        Query parameters:
        - search: Search term (searches in category first, then name/other fields)
        - category: Filter by exact category
        - location: Filter by location
        - min_experience: Minimum years of experience
        - max_experience: Maximum years of experience
        - ordering: Sort by 'years_of_experience', '-years_of_experience', 'created_at', '-created_at'
        """
        
        # Start with optimized query
        queryset = Profile.objects.select_related('user').annotate(
            full_name_computed=Concat(
                'user__first_name', 
                Value(' '), 
                'user__last_name',
                output_field=CharField()
            ),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__status='Published')),
            review_count=Count('reviews', filter=Q(reviews__status='Published'))
        )
        
        # Only show verified doctors for patients
        if not request.user.is_staff:
            queryset = queryset.filter(is_verified=True)
        
        # CATEGORY-BASED SEARCH
        search_query = request.query_params.get('search', '').strip()
        search_type = request.query_params.get('search_type', 'category')  # 'category' or 'general'
        
        if search_query:
            if search_type == 'general':
                # General search across all fields (when user clicks "Search for...")
                q_objects = Q()
                search_terms = search_query.split()
                
                for term in search_terms:
                    q_objects |= Q(user__first_name__icontains=term)
                    q_objects |= Q(user__last_name__icontains=term)
                    q_objects |= Q(full_name_computed__icontains=term)
                    q_objects |= Q(user__email__icontains=term)
                    q_objects |= Q(about__icontains=term)
                    q_objects |= Q(specialization__icontains=term)
                
                queryset = queryset.filter(q_objects).distinct()
            else:
                # Category search (default - filters by category display name)
                # Get matching categories
                from .models import DOCTOR_CATEGORIES
                matching_categories = [
                    code for code, label in DOCTOR_CATEGORIES 
                    if search_query.lower() in label.lower()
                ]
                
                if matching_categories:
                    queryset = queryset.filter(category__in=matching_categories)
                else:
                    # No matching categories found
                    queryset = queryset.none()
        
        # Filter by exact category (if provided separately)
        category = request.query_params.get('category', '').strip()
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by experience range
        min_experience = request.query_params.get('min_experience')
        if min_experience:
            try:
                queryset = queryset.filter(years_of_experience__gte=int(min_experience))
            except (ValueError, TypeError):
                pass
        
        max_experience = request.query_params.get('max_experience')
        if max_experience:
            try:
                queryset = queryset.filter(years_of_experience__lte=int(max_experience))
            except (ValueError, TypeError):
                pass
        
        # Filter by location
        location = request.query_params.get('location', '').strip()
        if location:
            queryset = queryset.filter(
                Q(location__icontains=location) | Q(user__location__icontains=location)
            )
        
        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        valid_orderings = {
            'years_of_experience': 'years_of_experience',
            '-years_of_experience': '-years_of_experience',
            'created_at': 'created_at',
            '-created_at': '-created_at',
        }
        
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProfileSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProfileSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def categories(self, request):
        """Get list of all doctor categories with their display names."""
        from .models import DOCTOR_CATEGORIES
        
        search = request.query_params.get('search', '').strip().lower()
        
        categories = [
            {
                'value': code,
                'label': label
            }
            for code, label in DOCTOR_CATEGORIES
            if not search or search in label.lower()
        ]
        
        return Response({
            'categories': categories
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        """Get current user's doctor profile."""
        try:
            profile = Profile.objects.select_related('user').annotate(
                avg_rating=Avg('reviews__rating', filter=Q(reviews__status='Published')),
                review_count=Count('reviews', filter=Q(reviews__status='Published'))
            ).get(user=request.user)
            serializer = self.get_serializer(profile, context={'request': request})
            return Response(serializer.data)
        except Profile.DoesNotExist:
            return Response(
                {'error': 'Doctor profile not found for this user.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def reviews(self, request, pk=None):
        """Get all reviews for a doctor."""
        doctor = self.get_object()
        reviews = doctor.reviews.filter(status='Published').select_related(
            'patient__user'
        ).order_by('-created_at')
        
        from .serializers import DoctorReviewSerializer
        serializer = DoctorReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def specializations(self, request):
        """Get list of all unique specializations."""
        specializations = Profile.objects.filter(
            is_verified=True
        ).values_list('specialization', flat=True).distinct().order_by('specialization')
        
        return Response({
            'specializations': [s for s in specializations if s]
        })


class PrescriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for prescriptions."""
    
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['case', 'appointment']
    ordering_fields = ['created_at', 'start_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter prescriptions based on user role."""
        queryset = self.queryset.select_related(
            'case__patient__user',
            'appointment',
            'created_by'
        ).prefetch_related('items')
        
        if self.request.user.role == 'Patient':
            return queryset.filter(case__patient__user=self.request.user)
        elif self.request.user.role == 'Doctor':
            doctor_profile = Profile.objects.filter(user=self.request.user).first()
            if doctor_profile:
                return queryset.filter(case__doctor=doctor_profile)
        elif self.request.user.is_staff:
            return queryset
        
        return Prescription.objects.none()

    def perform_create(self, serializer):
        """Create prescription with created_by tracking."""
        if self.request.user.role not in ['Doctor', 'Admin'] and not self.request.user.is_staff:
            raise PermissionDenied("Only doctors can create prescriptions.")
        
        from apps.patients.models import Case, Appointment
        
        case_id = self.request.data.get('case_id')
        appointment_id = self.request.data.get('appointment_id')
        
        try:
            case = Case.objects.get(pk=case_id)
            kwargs = {'case': case, 'created_by': self.request.user}
            
            if appointment_id:
                appointment = Appointment.objects.get(pk=appointment_id)
                if appointment.case != case:
                    raise ValidationError({'appointment': 'Appointment must belong to the specified case.'})
                kwargs['appointment'] = appointment
            
            serializer.save(**kwargs)
        except Case.DoesNotExist:
            raise ValidationError({'case': 'Case not found.'})
        except Appointment.DoesNotExist:
            raise ValidationError({'appointment': 'Appointment not found.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_items(self, request, pk=None):
        """Add prescription items to a prescription."""
        prescription = self.get_object()
        
        if request.user.role != 'Doctor' and not request.user.is_staff:
            raise PermissionDenied("Only doctors can add prescription items.")
        
        items_data = request.data.get('items', [])
        
        if not items_data:
            return Response(
                {'error': 'No items provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_items = []
        for item_data in items_data:
            item_data['prescription'] = prescription.id
            serializer = PrescriptionItemSerializer(data=item_data)
            if serializer.is_valid():
                item = serializer.save(prescription=prescription)
                created_items.append(item)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(
            PrescriptionItemSerializer(created_items, many=True).data,
            status=status.HTTP_201_CREATED
        )


class PrescriptionItemViewSet(viewsets.ModelViewSet):
    """ViewSet for prescription items."""
    
    queryset = PrescriptionItem.objects.all()
    serializer_class = PrescriptionItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['prescription']

    def get_queryset(self):
        """Filter prescription items based on user role."""
        queryset = self.queryset.select_related('prescription__case__patient__user')
        
        if self.request.user.role == 'Patient':
            return queryset.filter(prescription__case__patient__user=self.request.user)
        elif self.request.user.role == 'Doctor':
            doctor_profile = Profile.objects.filter(user=self.request.user).first()
            if doctor_profile:
                return queryset.filter(prescription__case__doctor=doctor_profile)
        elif self.request.user.is_staff:
            return queryset
        
        return PrescriptionItem.objects.none()

    def perform_create(self, serializer):
        """Only doctors can create prescription items."""
        if self.request.user.role != 'Doctor' and not self.request.user.is_staff:
            raise PermissionDenied("Only doctors can create prescription items.")
        
        serializer.save()


class DoctorReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for doctor reviews."""
    
    queryset = DoctorReview.objects.all()
    serializer_class = DoctorReviewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['doctor', 'patient', 'status', 'rating', 'appointment']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        """Filter reviews based on user role."""
        queryset = self.queryset.select_related(
            'patient__user',
            'doctor__user',
            'appointment',
            'updated_by'
        )
        
        if self.request.user.role == 'Patient':
            patient_profile = self.get_patient_profile()
            if patient_profile:
                return queryset.filter(patient=patient_profile)
        elif self.request.user.role == 'Doctor':
            doctor_profile = Profile.objects.filter(user=self.request.user).first()
            if doctor_profile:
                return queryset.filter(doctor=doctor_profile)
        elif self.request.user.is_staff:
            return queryset
        else:
            # Others can only see published reviews
            return queryset.filter(status='Published')
        
        return DoctorReview.objects.none()

    def get_patient_profile(self):
        """Get patient profile for current user."""
        from apps.patients.models import Profile as PatientProfile
        return PatientProfile.objects.filter(user=self.request.user).first()

    def perform_create(self, serializer):
        """Create review for current patient."""
        if self.request.user.role != 'Patient':
            raise PermissionDenied("Only patients can create reviews.")
        
        patient_profile = self.get_patient_profile()
        if not patient_profile:
            raise ValidationError({'patient': 'Patient profile not found.'})
        
        appointment_id = self.request.data.get('appointment_id')
        
        try:
            
            from apps.patients.models import Appointment
            appointment = Appointment.objects.get(pk=appointment_id)
            doctor = Profile.objects.get(pk=appointment.case.doctor.id)
            kwargs = {'patient': patient_profile, 'doctor': doctor}
            
            if appointment_id:
                # Verify appointment belongs to patient and doctor
                if appointment.case.patient != patient_profile:
                    raise ValidationError({'appointment': 'Appointment does not belong to you.'})
                if appointment.case.doctor != doctor:
                    raise ValidationError({'appointment': 'Appointment is not with this doctor.'})
                kwargs['appointment'] = appointment
            
            serializer.save(**kwargs)
        except Profile.DoesNotExist:
            raise ValidationError({'doctor': 'Doctor not found.'})
        except Appointment.DoesNotExist:
            raise ValidationError({'appointment': 'Appointment not found.'})

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def moderate(self, request, pk=None):
        """Moderate a review (admin/staff only)."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff can moderate reviews.")
        
        review = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(DoctorReview.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        review.status = new_status
        review.updated_by = request.user
        review.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        serializer = self.get_serializer(review)
        return Response(serializer.data)