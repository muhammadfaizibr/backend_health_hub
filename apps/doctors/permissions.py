from rest_framework import permissions


class IsDoctorOrReadOnly(permissions.BasePermission):
    """Allow write access only to doctors, read access to authenticated users."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.role == 'Doctor'


class IsDoctorOwnerOrReadOnly(permissions.BasePermission):
    """Allow write access only to the doctor who owns the record."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if request.user.is_staff:
            return True
        
        # Check if object has a doctor field
        if hasattr(obj, 'doctor'):
            return obj.doctor.user == request.user
        
        # For Profile model itself
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsPatientOwnerOrDoctor(permissions.BasePermission):
    """Allow access to patient owner or assigned doctor."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        # For prescriptions
        if hasattr(obj, 'case'):
            if obj.case.patient.user == request.user:
                return True
            if obj.case.doctor and obj.case.doctor.user == request.user:
                return True
        
        return False