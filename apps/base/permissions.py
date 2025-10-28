from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """Custom permission to only allow owners of an object or admins to edit it."""

    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user.is_staff:
            return True
        
        # Check if object has a user field
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # For User model itself
        if obj == request.user:
            return True
        
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow read access to all, but write access only to owner or admin."""

    def has_object_permission(self, request, view, obj):
        # Read permissions allowed for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for owner or admin
        if request.user.is_staff:
            return True
        
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return obj == request.user
    
class BaseReadOnlyPermission:
    """
    Custom permission class:
    - Read access for authenticated users (to view doctor profiles)
    - Write access only for owner or staff
    """
    def has_permission(self, request, view):
        # Allow authenticated users to read
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user and request.user.is_authenticated
        # Only authenticated users can write
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow read access for all authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        # Allow write access only for owner or staff
        return obj.user == request.user or request.user.is_staff
