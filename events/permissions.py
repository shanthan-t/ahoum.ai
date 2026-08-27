from rest_framework import permissions

from .exceptions import NotFoundException, PermissionDeniedException


class IsFacilitator(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if (
            not hasattr(request.user, "profile")
            or request.user.profile.role != "facilitator"
        ):
            raise PermissionDeniedException(
                detail="You do not have permission to perform this action.",
                code="permission_denied",
            )
        return True


class IsSeeker(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if (
            not hasattr(request.user, "profile")
            or request.user.profile.role != "seeker"
        ):
            raise PermissionDeniedException(
                detail="You do not have permission to perform this action.",
                code="permission_denied",
            )
        return True


class IsEventOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.created_by == request.user:
            return True
        raise NotFoundException(detail="Not found.", code="not_found")
