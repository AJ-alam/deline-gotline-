from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Allows access to admin (SSW/staff), director, and ssw users.
    Finance role is excluded — finance users only access the payment list endpoint.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ['admin', 'director', 'ssw'])

class IsDirectorUser(permissions.BasePermission):
    """
    Allows access only to Director users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'director')

class IsStudentUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'student')

class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
            
        if request.user.role in ['admin', 'director', 'ssw']:
            return True
        
        if hasattr(obj, 'student'):
            return obj.student == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user
