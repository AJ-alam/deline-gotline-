from rest_framework import status, generics, permissions
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from users.serializers import UserSerializer, RegisterSerializer, CustomTokenObtainPairSerializer
from users.permissions import IsAdminUser, IsDirectorUser
from api.utils.responses import api_response
import uuid, logging
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

User = get_user_model()
logger = logging.getLogger(__name__)

class AuthRateThrottle(AnonRateThrottle):
    rate = '10/minute'
    scope = 'auth'

    def allow_request(self, request, view):
        from django.conf import settings as _s
        if getattr(_s, 'TESTING', False):
            return True
        return super().allow_request(request, view)


class RegisterController(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer
    throttle_classes = [AuthRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                self.perform_create(serializer)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Registration failed during create_user: %s", e)
                return api_response(False, None, str(e) or "Account creation failed. Please try again.", status.HTTP_500_INTERNAL_SERVER_ERROR)
            return api_response(True, serializer.data, "User registered successfully", status.HTTP_201_CREATED)
        # Flatten first field-level error for the client
        first_msg = "Registration failed"
        errs = serializer.errors
        if errs:
            first_key = next(iter(errs))
            first_val = errs[first_key]
            first_msg = f"{first_key.replace('_', ' ').title()}: {first_val[0] if isinstance(first_val, list) else first_val}"
        return api_response(False, errs, first_msg, status.HTTP_400_BAD_REQUEST)

class LoginController(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            logger.info("Successful login from IP %s", request.META.get('REMOTE_ADDR'))
            return api_response(True, response.data, "Login successful")
        logger.warning("Failed login attempt from IP %s", request.META.get('REMOTE_ADDR'))
        return api_response(False, None, "Invalid credentials", response.status_code)

class TokenRefreshController(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            return api_response(True, response.data, "Token refreshed successfully")
        return api_response(False, response.data, "Token refresh failed", response.status_code)

class MeController(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        # Fetch user + profile in a single JOIN so the serializer
        # doesn't fire a second query when it reads profile fields.
        return User.objects.select_related('profile').get(pk=self.request.user.pk)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return api_response(True, serializer.data, "User profile retrieved")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return api_response(True, serializer.data, "User profile updated")
        # Log the exact errors for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Profile update failed for user {instance.email}: {serializer.errors}")
        return api_response(False, serializer.errors, "Update failed", status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


class PasswordResetRateThrottle(AnonRateThrottle):
    rate = '5/hour'
    scope = 'password_reset'


class ForgotPasswordController(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request, *args, **kwargs):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return api_response(False, None, "Email is required", status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Always return 200 — never reveal whether an account exists
            return api_response(True, None, "If that email is registered you will receive a reset link shortly.")

        token = uuid.uuid4().hex
        cache.set(f"pwd_reset_{token}", user.pk, timeout=1800)  # 30 min, one-time use

        # Use the configured FRONTEND_URL — never trust the HTTP_ORIGIN header
        from django.conf import settings as django_settings
        frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        reset_link = f"{frontend_url}/reset-password?token={token}"

        try:
            from email_sender import send_password_reset
            ok = send_password_reset(
                student_email=user.email,
                student_name=getattr(user, 'full_name', None) or user.get_full_name() or user.email,
                reset_link=reset_link,
            )
            if not ok:
                logger.error("send_password_reset returned False for user pk=%s", user.pk)
        except Exception:
            logger.exception("send_password_reset failed for user pk=%s", user.pk)

        return api_response(True, None, "If that email is registered you will receive a reset link shortly.")


class ResetPasswordController(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request, *args, **kwargs):
        token    = (request.data.get('token') or '').strip()
        password = (request.data.get('password') or '').strip()

        if not token or not password:
            return api_response(False, None, "Token and password are required", status.HTTP_400_BAD_REQUEST)

        cache_key = f"pwd_reset_{token}"
        user_pk = cache.get(cache_key)
        if not user_pk:
            return api_response(False, None, "Reset link is invalid or has expired", status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return api_response(False, None, "Reset link is invalid or has expired", status.HTTP_400_BAD_REQUEST)

        # Run Django's password validators before accepting the new password
        try:
            validate_password(password, user)
        except DjangoValidationError as e:
            return api_response(False, {'password': list(e.messages)}, "Password does not meet requirements", status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=['password'])
        cache.delete(cache_key)  # invalidate token immediately after use

        logger.info("Password reset successful for user pk=%s", user.pk)
        return api_response(True, None, "Password has been reset successfully. You can now log in.")


class StaffUserListController(generics.GenericAPIView):
    """
    Director-only: list all admin/director accounts and create new ones.
    GET  /api/auth/staff-users/
    POST /api/auth/staff-users/
    """
    permission_classes = (IsDirectorUser,)

    def get(self, request):
        users = (
            User.objects
            .filter(role__in=['admin', 'director', 'ssw'])
            .order_by('role', 'full_name')
        )
        data = [
            {
                'id': u.id,
                'full_name': u.full_name,
                'email': u.email,
                'role': u.role,
                'is_active': u.is_active,
                'date_joined': u.date_joined.strftime('%Y-%m-%d'),
            }
            for u in users
        ]
        return api_response(True, data, f"{len(data)} staff users")

    def post(self, request):
        email     = (request.data.get('email') or '').strip().lower()
        full_name = (request.data.get('full_name') or '').strip()
        role      = (request.data.get('role') or 'admin').strip()
        password  = (request.data.get('password') or '').strip()

        if not email or '@' not in email:
            return api_response(False, None, "A valid email address is required", status.HTTP_400_BAD_REQUEST)
        if not full_name:
            return api_response(False, None, "Full name is required", status.HTTP_400_BAD_REQUEST)
        if role not in ('admin', 'director', 'ssw'):
            return api_response(False, None, "Role must be 'admin', 'director', or 'ssw'", status.HTTP_400_BAD_REQUEST)
        if not password:
            return api_response(False, None, "Password is required", status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email).exists():
            return api_response(False, None, "A user with this email already exists", status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(password)
        except DjangoValidationError as e:
            return api_response(False, {'password': list(e.messages)}, "Password does not meet requirements", status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            is_staff=True,
            is_superuser=(role == 'admin'),
            is_active=True,
        )
        logger.info("Staff user created: %s (%s) by director %s", email, role, request.user.email)
        return api_response(
            True,
            {'id': user.id, 'email': user.email, 'full_name': user.full_name, 'role': user.role},
            f"Account created for {full_name}",
            status.HTTP_201_CREATED,
        )


class StaffUserDetailController(generics.GenericAPIView):
    """
    Director-only: update or delete a single admin/director account.
    PUT    /api/auth/staff-users/<pk>/
    DELETE /api/auth/staff-users/<pk>/
    """
    permission_classes = (IsDirectorUser,)

    def _get_user(self, pk):
        try:
            return User.objects.get(pk=pk, role__in=['admin', 'director', 'ssw'])
        except User.DoesNotExist:
            return None

    def put(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return api_response(False, None, "Staff user not found", status.HTTP_404_NOT_FOUND)

        full_name = (request.data.get('full_name') or user.full_name).strip()
        role      = (request.data.get('role') or user.role).strip()
        password  = (request.data.get('password') or '').strip()
        is_active = request.data.get('is_active', user.is_active)

        if role not in ('admin', 'director', 'ssw'):
            return api_response(False, None, "Role must be 'admin', 'director', or 'ssw'", status.HTTP_400_BAD_REQUEST)

        # Guard: cannot demote the only active director
        if user.role == 'director' and role != 'director':
            remaining = User.objects.filter(role='director', is_active=True).exclude(pk=pk).count()
            if remaining == 0:
                return api_response(False, None, "Cannot change role — this is the only active director", status.HTTP_400_BAD_REQUEST)

        user.full_name   = full_name
        user.role        = role
        user.is_staff    = True
        user.is_superuser = (role == 'admin')
        user.is_active   = bool(is_active)

        if password:
            try:
                validate_password(password, user)
            except DjangoValidationError as e:
                return api_response(False, {'password': list(e.messages)}, "Password does not meet requirements", status.HTTP_400_BAD_REQUEST)
            user.set_password(password)

        user.save()
        logger.info("Staff user updated: pk=%s by director %s", pk, request.user.email)
        return api_response(True, {
            'id': user.id, 'email': user.email,
            'full_name': user.full_name, 'role': user.role, 'is_active': user.is_active,
        }, "User updated successfully")

    def delete(self, request, pk):
        if str(request.user.pk) == str(pk):
            return api_response(False, None, "You cannot delete your own account", status.HTTP_400_BAD_REQUEST)

        user = self._get_user(pk)
        if not user:
            return api_response(False, None, "Staff user not found", status.HTTP_404_NOT_FOUND)

        if user.role == 'director':
            remaining = User.objects.filter(role='director', is_active=True).exclude(pk=pk).count()
            if remaining == 0:
                return api_response(False, None, "Cannot delete the only active director", status.HTTP_400_BAD_REQUEST)

        email = user.email
        user.delete()
        logger.info("Staff user deleted: %s by director %s", email, request.user.email)
        return api_response(True, None, f"User {email} deleted")


class TestEmailController(generics.GenericAPIView):
    """
    POST /api/auth/test-email/
    Body: { "type": "received|approved|rejected|processed|reset|finance" }
    Admin/director-only endpoint to verify email delivery end-to-end.
    """
    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        email_type = (request.data.get('type') or 'received').strip()
        target = request.user.email
        name   = getattr(request.user, 'full_name', None) or request.user.get_full_name() or request.user.email

        try:
            from email_sender import (
                send_application_received,
                send_application_decision,
                send_funding_processed,
                send_password_reset,
                send_finance_report,
            )
            from datetime import datetime

            if email_type == 'received':
                ok = send_application_received(target, name, 'FS-0001', 'Admission Application', datetime.now())

            elif email_type == 'approved':
                ok = send_application_decision(
                    target, name, 'FS-0001', 'Admission Application',
                    approved=True, semester='Fall', year='2025',
                    funding_breakdown=[
                        {'name': 'Tuition Bursary', 'amount': 3500},
                        {'name': 'Living Allowance', 'amount': 1200},
                    ],
                    total_amount=4700,
                )

            elif email_type == 'rejected':
                ok = send_application_decision(
                    target, name, 'FS-0001', 'Admission Application',
                    approved=False,
                    rejection_reason='Incomplete documentation submitted.',
                )

            elif email_type == 'processed':
                ok = send_funding_processed(
                    target, name, 'Admission Application', 'Fall', '2025',
                    total_amount=4700,
                    funding_breakdown=[
                        {'name': 'Tuition Bursary', 'amount': 3500},
                        {'name': 'Living Allowance', 'amount': 1200},
                    ],
                )

            elif email_type == 'reset':
                ok = send_password_reset(target, name, 'http://localhost:5173/reset-password?token=test-token-123')

            elif email_type == 'finance':
                csv_bytes = b'Submission ID,Student Name,Status\nFS-0001,Test Student,accepted\n'
                ok = send_finance_report(csv_bytes=csv_bytes, total_students=1, triggered_by=name)

            else:
                return api_response(False, None, f"Unknown type '{email_type}'. Use: received|approved|rejected|processed|reset|finance", status.HTTP_400_BAD_REQUEST)

            if ok:
                return api_response(True, {'sent_to': target, 'type': email_type}, f"Test email '{email_type}' sent to {target}")
            else:
                return api_response(False, None, "email_sender returned False — check server logs for SMTP errors", status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception:
            logger.exception("TestEmailController failed for user pk=%s type=%s", request.user.pk, email_type)
            return api_response(False, None, "Email delivery failed — check server logs", status.HTTP_500_INTERNAL_SERVER_ERROR)
