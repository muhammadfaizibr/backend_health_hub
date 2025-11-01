from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import (
    Profile, MedicalHistory, Case, AppointmentTimeSlot, Appointment, Report
)
from .serializers import (
    ProfileSerializer, MedicalHistorySerializer, CaseSerializer,
    AppointmentTimeSlotSerializer, AppointmentSerializer, CreateAppointmentSerializer, ReportSerializer 
)
from apps.base.models import User
from apps.doctors.models import Profile as DoctorProfile
from apps.translators.models import Profile as TranslatorProfile
from django.utils import timezone
from datetime import timedelta
from rest_framework.serializers import ValidationError


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.select_related('user')
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'Patient':
            return self.queryset.filter(user=self.request.user)
        elif self.request.user.is_staff:
            return self.queryset.all()
        return Profile.objects.none()

    def perform_create(self, serializer):
        if self.request.user.role != 'Patient':
            raise ValidationError({'error': 'Only patients can create profiles.'})
        
        # Check if profile already exists
        if Profile.objects.filter(user=self.request.user).exists():
            raise ValidationError({'error': 'Profile already exists for this user.'})
        
        serializer.save(user=self.request.user)

class MedicalHistoryViewSet(viewsets.ModelViewSet):
    queryset = MedicalHistory.objects.select_related('patient', 'created_by', 'updated_by')
    serializer_class = MedicalHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type', 'is_active']

    def get_queryset(self):
        if self.request.user.role == 'Patient':
            return self.queryset.filter(patient__user=self.request.user)
        return self.queryset.all() if self.request.user.is_staff else self.queryset.none()

    def perform_create(self, serializer):
        if self.request.user.role in ['Patient', 'Admin']:
            serializer.save(created_by=self.request.user)
        else:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)


class CaseViewSet(viewsets.ModelViewSet):
    queryset = Case.objects.select_related('patient', 'doctor', 'created_by', 'closed_by').prefetch_related('appointments')
    serializer_class = CaseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def get_queryset(self):
        if self.request.user.role == 'Patient':
            return self.queryset.filter(patient__user=self.request.user)
        elif self.request.user.role == 'Doctor':
            doctor_profile = DoctorProfile.objects.filter(user=self.request.user).first()
            if doctor_profile:
                return self.queryset.filter(Q(doctor=doctor_profile) | Q(created_by=self.request.user))
        return self.queryset.all() if self.request.user.is_staff else self.queryset.none()

    @action(detail=True, methods=['patch'])
    def assign_doctor(self, request, pk=None):
        case = self.get_object()
        doctor_id = request.data.get('doctor_id')
        try:
            doctor = DoctorProfile.objects.get(id=doctor_id)
            case.doctor = doctor
            case.save()
            return Response(CaseSerializer(case).data)
        except DoctorProfile.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

    def perform_update(self, serializer):
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == 'Closed':
            serializer.validated_data['closed_at'] = timezone.now()
            serializer.save(closed_by=self.request.user)
        else:
            serializer.save()

class AppointmentTimeSlotViewSet(viewsets.ModelViewSet):
    queryset = AppointmentTimeSlot.objects.select_related(
        'case', 
        'case__patient', 
        'case__doctor', 
        'created_by'
    ).filter(is_booked=False)
    serializer_class = AppointmentTimeSlotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['case', 'date', 'timezone', 'is_booked']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        if user.role == 'Doctor':
            # Show time slots for cases assigned to this doctor
            doctor = DoctorProfile.objects.filter(user=user).first()
            if doctor:
                return qs.filter(case__doctor=doctor)
        elif user.role == 'Patient':
            # Show time slots for patient's own cases
            patient = Profile.objects.filter(user=user).first()
            if patient:
                return qs.filter(case__patient=patient)
        elif user.is_staff:
            # Staff can see all time slots
            return qs
            
        return qs.none()

    def perform_create(self, serializer):
        """Set the created_by field to the current user."""
        serializer.save(created_by=self.request.user)

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.select_related(
        'case', 'time_slot', 'translator', 'cancelled_by', 'created_by'
    ).prefetch_related('case__patient', 'case__doctor')
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'is_follow_up', 'case']

    def get_queryset(self):
        if self.request.user.role == 'Patient':
            return self.queryset.filter(case__patient__user=self.request.user)
        elif self.request.user.role == 'Doctor':
            doctor = DoctorProfile.objects.filter(user=self.request.user).first()
            if doctor:
                return self.queryset.filter(case__doctor=doctor)
            return self.queryset.none()
        elif self.request.user.role == 'Translator':
            trans = TranslatorProfile.objects.filter(user=self.request.user).first()
            if trans:
                return self.queryset.filter(translator=trans)
            return self.queryset.none()
        return self.queryset.all() if self.request.user.is_staff else self.queryset.none()

    @action(detail=False, methods=['post'], url_path='book')
    def book_appointment(self, request):
        """
        Book an appointment with automatic case and time slot creation.
        This endpoint handles the entire booking process in a single transaction.
        """
        serializer = CreateAppointmentSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save()
        
        # Return the created appointment with full details
        response_serializer = AppointmentSerializer(appointment)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        appointment = self.get_object()
        if appointment.status != 'pending_confirmation' or request.user != appointment.created_by:
            return Response({'error': 'Cannot confirm this appointment.'}, status=status.HTTP_400_BAD_REQUEST)
        
        appointment.status = 'confirmed'
        appointment.save()
        from apps.base.utils.email import send_appointment_confirmation
        # Get doctor from the case
        doctor_user = appointment.case.doctor.user
        send_appointment_confirmation(appointment, appointment.case.patient, doctor_user)
        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        reason = request.data.get('cancellation_reason', request.data.get('reason', ''))
        appointment.status = 'cancelled'
        appointment.cancellation_reason = reason
        appointment.cancelled_by = request.user
        appointment.cancelled_at = timezone.now()
        appointment.time_slot.is_booked = False
        appointment.time_slot.save()
        appointment.save()
        return Response(AppointmentSerializer(appointment).data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.select_related('case', 'appointment', 'file', 'uploaded_by')
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['case', 'appointment', 'report_type']  # Add this line

    def get_queryset(self):
        queryset = self.queryset
        
        if self.request.user.role == 'Patient':
            queryset = queryset.filter(case__patient__user=self.request.user)
        elif self.request.user.role == 'Doctor':
            doctor = DoctorProfile.objects.filter(user=self.request.user).first()
            if doctor:
                queryset = queryset.filter(case__doctor=doctor)
            else:
                return queryset.none()
        elif not self.request.user.is_staff:
            return queryset.none()
        
        # Filter by appointment if provided in query params
        appointment_id = self.request.query_params.get('appointment')
        if appointment_id:
            queryset = queryset.filter(appointment_id=appointment_id)
            
        return queryset

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)