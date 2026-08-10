from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.api.admin_views import DirectoryUserView, DirectoryView
from accounts.api.views import MeView, RegisterView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token-obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('people/', DirectoryView.as_view(), name='directory'),
    path('people/<int:pk>/', DirectoryUserView.as_view(), name='directory-user'),
]
