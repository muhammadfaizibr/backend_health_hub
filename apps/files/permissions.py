from rest_framework import permissions


class IsOwnerOrRelatedUser(permissions.BasePermission):
    """
    Custom permission to only allow owners, related users, or staff to access files.
    Public files are accessible to all authenticated users.
    """

    def has_object_permission(self, request, view, obj):
        # Staff can access everything
        if request.user.is_staff:
            return True

        # Public files are readable by everyone
        if obj.is_public and request.method in permissions.SAFE_METHODS:
            return True

        # Owner and related user have full access
        if obj.uploaded_by == request.user or obj.related_to_user == request.user:
            return True

        return False


class CanDeleteFile(permissions.BasePermission):
    """
    Permission to check if user can delete a file.
    Only owner or staff can delete.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.uploaded_by == request.user


class CanRestoreFile(permissions.BasePermission):
    """
    Only staff can restore deleted files.
    """

    def has_permission(self, request, view):
        return request.user.is_staff