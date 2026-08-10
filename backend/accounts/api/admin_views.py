"""Who has an account, and what they may do.

Reading the directory is open to staff — a support worker needs to find a
student. Changing a role or deactivating an account is restricted to
administrators, because both grant or remove the power to decide funding.
"""

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from accounts.services import administration


class DirectoryUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        # Deliberately narrow: a directory is for finding someone and setting
        # what they may do, not for reading their address or banking.
        fields = ('id', 'email', 'first_name', 'last_name', 'full_name',
                  'role', 'role_label', 'is_active', 'beneficiary_number',
                  'date_joined')
        read_only_fields = fields


def _staff(user):
    return bool(user and user.is_authenticated and (
        user.reviews_applications or user.decides_applications or user.handles_payments
    ))


class DirectoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _staff(request.user):
            return Response({'detail': 'Only staff may view the directory.'},
                            status=status.HTTP_403_FORBIDDEN)

        people = administration.directory(
            search=request.query_params.get('search', '').strip(),
            role=request.query_params.get('role', '').strip(),
            include_inactive=request.query_params.get('include_inactive') == 'true',
        )
        return Response({
            'roles': [{'value': value, 'label': label} for value, label in Role.choices],
            'results': DirectoryUserSerializer(people[:200], many=True).data,
        })


class DirectoryUserView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not (request.user.is_authenticated and request.user.role == Role.ADMIN):
            return Response(
                {'detail': 'Only an administrator may change an account.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            person = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'No such account.'},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            if 'role' in request.data:
                person = administration.change_role(person, request.data['role'],
                                                    actor=request.user)
            if 'is_active' in request.data:
                person = administration.set_active(person, bool(request.data['is_active']),
                                                   actor=request.user)
        except administration.AdministrationError as exc:
            # 409 rather than 400: the request is well formed, the system state
            # is what refuses it.
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(DirectoryUserSerializer(person).data)
