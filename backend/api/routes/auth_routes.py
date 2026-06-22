from django.urls import path
from api.controllers.auth_controller import (
    RegisterController, LoginController,
    TokenRefreshController, MeController,
    ForgotPasswordController, ResetPasswordController,
    TestEmailController,
    StaffUserListController, StaffUserDetailController,
)

urlpatterns = [
    path('register/', RegisterController.as_view(), name='register'),
    path('login/', LoginController.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshController.as_view(), name='token_refresh'),
    path('me/', MeController.as_view(), name='user_me'),
    path('forgot-password/', ForgotPasswordController.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordController.as_view(), name='reset_password'),
    path('test-email/', TestEmailController.as_view(), name='test_email'),
    path('staff-users/', StaffUserListController.as_view(), name='staff_users'),
    path('staff-users/<int:pk>/', StaffUserDetailController.as_view(), name='staff_user_detail'),
]
