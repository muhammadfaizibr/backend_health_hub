from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Q, Avg, Count, Prefetch

from .models import (
    Profile, 
    # DoctorExperience, DoctorEducation, DoctorCertification, ConsultationFee, DoctorAvailability, 
    Prescription, PrescriptionItem, DoctorReview
)
from .serializers import (
    ProfileSerializer, 
    # DoctorExperienceSerializer, DoctorEducationSerializer, DoctorCertificationSerializer, ConsultationFeeSerializer, DoctorAvailabilitySerializer,
    PrescriptionSerializer, PrescriptionItemSerializer, DoctorReviewSerializer
)


class ProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for doctor profiles."""
    
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['specialization', 'is_verified', 'years_of_experience']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'specialization', 'about']
    ordering_fields = ['created_at', 'years_of_experience']
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
        
        # Check if profile already exists
        if Profile.objects.filter(user=self.request.user).exists():
            raise ValidationError("Doctor profile already exists for this user.")
        
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        """Get current user's doctor profile."""
        try:
            profile = Profile.objects.select_related('user').annotate(
                avg_rating=Avg('reviews__rating', filter=Q(reviews__status='Published')),
                review_count=Count('reviews', filter=Q(reviews__status='Published'))
            ).get(user=request.user)
            serializer = self.get_serializer(profile)
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
        
        serializer = DoctorReviewSerializer(reviews, many=True)
        return Response(serializer.data)


# class DoctorExperienceViewSet(viewsets.ModelViewSet):
#     """ViewSet for doctor experience records."""
    
#     queryset = DoctorExperience.objects.all()
#     serializer_class = DoctorExperienceSerializer
#     permission_classes = [IsAuthenticated]
#     filter_backends = [DjangoFilterBackend, OrderingFilter]
#     filterset_fields = ['doctor']
#     ordering_fields = ['experience__start_date']
#     ordering = ['-experience__start_date']

#     def get_queryset(self):
#         """Filter experience based on user role."""
#         queryset = self.queryset.select_related('doctor__user', 'experience')
        
#         if self.request.user.role == 'Doctor':
#             doctor_profile = Profile.objects.filter(user=self.request.user).first()
#             if doctor_profile:
#                 return queryset.filter(doctor=doctor_profile)
#             return DoctorExperience.objects.none()
#         elif self.request.user.is_staff:
#             return queryset
#         else:
#             # Others can see experiences of verified doctors
#             return queryset.filter(doctor__is_verified=True)

#     def perform_create(self, serializer):
#         """Create experience for current doctor."""
#         if self.request.user.role != 'Doctor' and not self.request.user.is_staff:
#             raise PermissionDenied("Only doctors can create experience records.")
        
#         doctor_profile = Profile.objects.filter(user=self.request.user).first()
#         if not doctor_profile:
#             raise ValidationError("Doctor profile not found.")
        
#         serializer.save(doctor=doctor_profile)


# class DoctorEducationViewSet(viewsets.ModelViewSet):
#     """ViewSet for doctor education records."""
    
#     queryset = DoctorEducation.objects.all()
#     serializer_class = DoctorEducationSerializer
#     permission_classes = [IsAuthenticated]
#     filter_backends = [DjangoFilterBackend, OrderingFilter]
#     filterset_fields = ['doctor']
#     ordering_fields = ['education__start_date']
#     ordering = ['-education__start_date']

#     def get_queryset(self):
#         """Filter education based on user role."""
#         queryset = self.queryset.select_related('doctor__user', 'education')
        
#         if self.request.user.role == 'Doctor':
#             doctor_profile = Profile.objects.filter(user=self.request.user).first()
#             if doctor_profile:
#                 return queryset.filter(doctor=doctor_profile)
#             return DoctorEducation.objects.none()
#         elif self.request.user.is_staff:
#             return queryset
#         else:
#             return queryset.filter(doctor__is_verified=True)

#     def perform_create(self, serializer):
#         """Create education for current doctor."""
#         if self.request.user.role != 'Doctor' and not self.request.user.is_staff:
#             raise PermissionDenied("Only doctors can create education records.")
        
#         doctor_profile = Profile.objects.filter(user=self.request.user).first()
#         if not doctor_profile:
#             raise ValidationError("Doctor profile not found.")
        
#         serializer.save(doctor=doctor_profile)


# class DoctorCertificationViewSet(viewsets.ModelViewSet):
#     """ViewSet for doctor certifications."""
    
#     queryset = DoctorCertification.objects.all()
#     serializer_class = DoctorCertificationSerializer
#     permission_classes = [IsAuthenticated]
#     filter_backends = [DjangoFilterBackend, OrderingFilter]
#     filterset_fields = ['doctor']
#     ordering_fields = ['certification__issue_date']
#     ordering = ['-certification__issue_date']

#     def get_queryset(self):
#         """Filter certifications based on user role."""
#         queryset = self.queryset.select_related('doctor__user', 'certification')
        
#         if self.request.user.role == 'Doctor':
#             doctor_profile = Profile.objects.filter(user=self.request.user).first()
#             if doctor_profile:
#                 return queryset.filter(doctor=doctor_profile)
#             return DoctorCertification.objects.none()
#         elif self.request.user.is_staff:
#             return queryset
#         else:
#             return queryset.filter(doctor__is_verified=True)

#     def perform_create(self, serializer):
#         """Create certification for current doctor."""
#         if self.request.user.role != 'Doctor' and not self.request.user.is_staff:
#             raise PermissionDenied("Only doctors can create certification records.")
        
#         doctor_profile = Profile.objects.filter(user=self.request.user).first()
#         if not doctor_profile:
#             raise ValidationError("Doctor profile not found.")
        
#         serializer.save(doctor=doctor_profile)


# class ConsultationFeeViewSet(viewsets.ModelViewSet):
#     """ViewSet for consultation fees."""
    
#     queryset = ConsultationFee.objects.all()
#     serializer_class = ConsultationFeeSerializer
#     permission_classes = [IsAuthenticated]
#     filter_backends = [DjangoFilterBackend, OrderingFilter]
#     filterset_fields = ['doctor']
#     ordering_fields = ['service_fee__duration']
#     ordering = ['service_fee__duration']

#     def get_queryset(self):
#         """Filter consultation fees based on user role."""
#         queryset = self.queryset.select_related('doctor__user', 'service_fee')
        
#         if self.request.user.role == 'Doctor':
#             doctor_profile = Profile.objects.filter(user=self.request.user).first()
#             if doctor_profile:
#                 return queryset.filter(doctor=doctor_profile)
#             return ConsultationFee.objects.none()
#         elif self.request.user.is_staff:
#             return queryset
#         else:
#             return queryset.filter(doctor__is_verified=True)

#     def perform_create(self, serializer):
#         """Create consultation fee for current doctor."""
#         if self.request.user.role != 'Doctor' and not self.request.user.is_staff:
#             raise PermissionDenied("Only doctors can create consultation fees.")
        
#         doctor_profile = Profile.objects.filter(user=self.request.user).first()
#         if not doctor_profile:
#             raise ValidationError("Doctor profile not found.")
        
#         serializer.save(doctor=doctor_profile)


# class DoctorAvailabilityViewSet(viewsets.ModelViewSet):
#     """ViewSet for doctor availability."""
    
#     queryset = DoctorAvailability.objects.all()
#     serializer_class = DoctorAvailabilitySerializer
#     permission_classes = [IsAuthenticated]
#     filter_backends = [DjangoFilterBackend, OrderingFilter]
#     filterset_fields = ['doctor', 'availability_slot__day_of_week']
#     ordering_fields = ['availability_slot__day_of_week', 'availability_slot__start_time']
#     ordering = ['availability_slot__day_of_week', 'availability_slot__start_time']

#     def get_queryset(self):
#         """Filter availability based on user role."""
#         queryset = self.queryset.select_related('doctor__user', 'availability_slot')
        
#         if self.request.user.role == 'Doctor':
#             doctor_profile = Profile.objects.filter(user=self.request.user).first()
#             if doctor_profile:
#                 return queryset.filter(doctor=doctor_profile)
#             return DoctorAvailability.objects.none()
#         elif self.request.user.is_staff:
#             return queryset
#         else:
#             return queryset.filter(doctor__is_verified=True)

#     def perform_create(self, serializer):
#         """Create availability for current doctor."""
#         if self.request.user.role != 'Doctor' and not self.request.user.is_staff:
#             raise PermissionDenied("Only doctors can create availability.")
        
#         doctor_profile = Profile.objects.filter(user=self.request.user).first()
#         if not doctor_profile:
#             raise ValidationError("Doctor profile not found.")
        
#         serializer.save(doctor=doctor_profile)


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
                    raise ValidationError("Appointment must belong to the specified case.")
                kwargs['appointment'] = appointment
            
            serializer.save(**kwargs)
        except Case.DoesNotExist:
            raise ValidationError("Case not found.")
        except Appointment.DoesNotExist:
            raise ValidationError("Appointment not found.")

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
    filterset_fields = ['doctor', 'patient', 'status', 'rating']
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
            raise ValidationError("Patient profile not found.")
        
        doctor_id = self.request.data.get('doctor_id')
        appointment_id = self.request.data.get('appointment_id')
        
        try:
            doctor = Profile.objects.get(pk=doctor_id)
            
            from apps.patients.models import Appointment
            kwargs = {'patient': patient_profile, 'doctor': doctor}
            
            if appointment_id:
                appointment = Appointment.objects.get(pk=appointment_id)
                # Verify appointment belongs to patient and doctor
                if appointment.case.patient != patient_profile:
                    raise ValidationError("Appointment does not belong to you.")
                if appointment.time_slot.doctor != doctor:
                    raise ValidationError("Appointment is not with this doctor.")
                kwargs['appointment'] = appointment
            
            serializer.save(**kwargs)
        except Profile.DoesNotExist:
            raise ValidationError("Doctor not found.")
        except Appointment.DoesNotExist:
            raise ValidationError("Appointment not found.")

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