from rest_framework.permissions import BasePermission


class IsManager(BasePermission):
    message = 'גישה מותרת למנהלים בלבד'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_manager
        )


class IsWorkerOrManager(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.is_manager or request.user.is_worker)
        )
