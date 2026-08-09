"""Who may do what.

Named for the action, not the job title. `user.role == 'ssw' or user.role ==
'admin'` was written out at nearly every call site in the previous codebase,
slightly differently each time, which is how a director ended up able to reach
an endpoint only support workers should have had.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsStudent(BasePermission):
    message = 'Only students may do this.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.is_student)


class ReviewsApplications(BasePermission):
    message = 'Only student support workers may review applications.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.reviews_applications)


class DecidesApplications(BasePermission):
    message = 'Only the Director may approve or decline applications.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.decides_applications)


class HandlesPayments(BasePermission):
    message = 'Only Finance may do this.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.handles_payments)


class IsStaffOrOwner(BasePermission):
    """Staff see everything; a student sees only their own application."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.reviews_applications or user.decides_applications or user.handles_payments:
            return True
        owner = getattr(obj, 'student_id', None) or getattr(obj, 'user_id', None)
        # A student may read their own record but not rewrite a submitted one.
        return owner == user.id and request.method in SAFE_METHODS
