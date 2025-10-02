from rest_framework import permissions


class IsTranslatorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow translators to edit their own profile.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and hasattr(request.user, 'translator_profile')

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Staff can edit any profile
        if request.user.is_staff:
            return True
        
        # Translators can only edit their own profile
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'translator'):
            return obj.translator.user == request.user
        
        return False


class IsPatientOrStaff(permissions.BasePermission):
    """
    Custom permission for review management.
    Patients can create/edit their own reviews.
    Staff can moderate all reviews.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Staff have full access
        if request.user.is_staff:
            return True
        
        # Patients can create reviews
        if request.method == 'POST':
            return hasattr(request.user, 'patient_profile')
        
        # Anyone can read published reviews
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return False

    def has_object_permission(self, request, view, obj):
        # Staff have full access
        if request.user.is_staff:
            return True
        
        # Patients can only edit their own reviews
        if hasattr(request.user, 'patient_profile'):
            return obj.patient == request.user.patient_profile
        
        # Read-only for others
        if request.method in permissions.SAFE_METHODS:
            return obj.status == 'Published'
        
        return False


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Generic permission for translator-owned resources.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Staff have full access
        if request.user.is_staff:
            return True
        
        # Check if user owns the resource
        if hasattr(obj, 'translator'):
            return obj.translator.user == request.user
        
        return False