from rest_framework import status, generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from users.serializers import UserSerializer, RegisterSerializer, CustomTokenObtainPairSerializer
from api.utils.responses import api_response

User = get_user_model()

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
        return api_response(False, serializer.errors, "Update failed", status.HTTP_400_BAD_REQUEST)
