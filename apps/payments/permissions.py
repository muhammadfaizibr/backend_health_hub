from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to access it.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Staff have full access
        if request.user.is_staff:
            return True
        
        # Check ownership based on object type
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'wallet'):
            return obj.wallet.user == request.user
        elif hasattr(obj, 'transaction'):
            return obj.transaction.user == request.user
        
        return False


class IsOrganizationOrAdmin(permissions.BasePermission):
    """
    Permission for organization-related billing operations.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_staff or (
            hasattr(request.user, 'role') and request.user.role == 'Organization'
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        if hasattr(obj, 'organization'):
            return obj.organization.user == request.user
        
        return False