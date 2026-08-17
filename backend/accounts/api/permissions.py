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
        if owner != user.id:
            return False
        if request.method in SAFE_METHODS:
            return True

        # One write, and only one. A student may answer a request for more
        # information on their own application — that is the whole point of
        # asking — and may do nothing else to it. The view checks the status as
        # well: this says who, `ApplicationViewSet.revise` says when.
        #
        # Named rather than opened by method, because "a student may POST to
        # their own application" would also hand them `transition` and
        # `price`.
        return getattr(view, 'action', None) == 'revise'
