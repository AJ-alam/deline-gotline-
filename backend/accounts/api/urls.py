from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.api.admin_views import DirectoryUserView, DirectoryView
from accounts.api.profile_views import (
    BankingProfileView, EligibilityProfileView, EnrolmentProfileView,
)
from accounts.api.views import EligibilityView, MeView, RegisterView

urlpatterns = [
    path('auth/eligibility/', EligibilityView.as_view(), name='eligibility'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token-obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
    # The student's own profile. Under `me/` because that is exactly what it is:
    # nothing here can name anybody else.
    path('me/eligibility/', EligibilityProfileView.as_view(), name='me-eligibility'),
    path('me/enrolment/', EnrolmentProfileView.as_view(), name='me-enrolment'),
    path('me/banking/', BankingProfileView.as_view(), name='me-banking'),
    path('people/', DirectoryView.as_view(), name='directory'),
    path('people/<int:pk>/', DirectoryUserView.as_view(), name='directory-user'),
]
