from rest_framework import status, generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from users.serializers import UserSerializer, RegisterSerializer, CustomTokenObtainPairSerializer
from api.utils.responses import api_response
import uuid, logging
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

User = get_user_model()
logger = logging.getLogger(__name__)

class RegisterController(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return api_response(True, serializer.data, "User registered successfully", status.HTTP_201_CREATED)
        return api_response(False, serializer.errors, "Registration failed", status.HTTP_400_BAD_REQUEST)

class LoginController(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            return api_response(True, response.data, "Login successful")
        return api_response(False, response.data, "Login failed", response.status_code)

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
        return self.request.user

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


class ForgotPasswordController(generics.GenericAPIView):
    """
    POST /api/auth/forgot-password/
    Body: { "email": "student@example.com" }

    Generates a 30-minute reset token, stores it in Django's cache,
    and sends the reset link via email_sender.send_password_reset().
    Always returns 200 so we don't leak whether an email exists.
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return api_response(False, None, "Email is required", status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Return 200 to avoid leaking whether the email exists
            return api_response(True, None, "If that email is registered you will receive a reset link shortly.")

        # Generate a secure token valid for 30 minutes
        token = uuid.uuid4().hex
        cache_key = f"pwd_reset_{token}"
        cache.set(cache_key, user.pk, timeout=1800)  # 30 min

        # Build reset URL
        from django.conf import settings as django_settings
        frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173')
        reset_link = f"{frontend_url}/reset-password?token={token}"

        try:
            from email_sender import send_password_reset
            ok = send_password_reset(
                student_email=user.email,
                student_name=getattr(user, 'full_name', None) or user.get_full_name() or user.email,
                reset_link=reset_link,
            )
            if not ok:
                logger.error("send_password_reset returned False for %s", email)
        except Exception as exc:
            logger.error("send_password_reset raised: %s", exc)

        return api_response(True, None, "If that email is registered you will receive a reset link shortly.")


class ResetPasswordController(generics.GenericAPIView):
    """
    POST /api/auth/reset-password/
    Body: { "token": "<uuid>", "password": "newpass123" }
    """
    permission_classes = (permissions.AllowAny,)

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
            return api_response(False, None, "User not found", status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=['password'])
        cache.delete(cache_key)  # one-time use

        logger.info("Password reset successful for user %s", user.email)
        return api_response(True, None, "Password has been reset successfully. You can now log in.")
