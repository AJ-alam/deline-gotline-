from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProfileViewSet, ApplicationViewSet, DocumentViewSet, 
    AuditLogViewSet, RegisterView, UserDetailView, UserDocumentViewSet,
    PaymentViewSet, AppealViewSet, SharedApplicationView
)
from .controllers.policy_controller import PolicyViewSet

router = DefaultRouter()
router.register(r'profiles', ProfileViewSet)
router.register(r'applications', ApplicationViewSet)
router.register(r'documents', DocumentViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'user-documents', UserDocumentViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'appeals', AppealViewSet)
router.register(r'shared-view', SharedApplicationView, basename='shared-view')
router.register(r'register', RegisterView, basename='register')
router.register(r'users', UserDetailView, basename='users')
router.register(r'policy', PolicyViewSet, basename='policy')

urlpatterns = [
    path('', include(router.urls)),
]
