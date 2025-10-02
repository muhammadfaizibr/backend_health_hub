from rest_framework import permissions


class IsOrganizationOwner(permissions.BasePermission):
    """Permission to only allow organizations to access their own resources."""
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        if request.user.role != 'Organization':
            return False
        
        if hasattr(obj, 'organization'):
            return obj.organization.user == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsStaffOrReadOnly(permissions.BasePermission):
    """Permission to allow staff to edit, others to read only."""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        return request.user.is_authenticated and request.user.is_staff


class CanManageCredits(permissions.BasePermission):
    """Permission to manage organization credits (staff only)."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff