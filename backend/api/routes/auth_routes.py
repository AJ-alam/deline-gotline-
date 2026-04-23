from django.urls import path
from api.controllers.auth_controller import (
    RegisterController, LoginController, 
    TokenRefreshController, MeController
)

urlpatterns = [
    path('register/', RegisterController.as_view(), name='register'),
    path('login/', LoginController.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshController.as_view(), name='token_refresh'),
    path('me/', MeController.as_view(), name='user_me'),
]
