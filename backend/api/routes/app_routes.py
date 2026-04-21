from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import (
    UserDocumentViewSet, ProfileViewSet, ApplicationViewSet, 
    DocumentViewSet, AuditLogViewSet, PaymentViewSet, AppealViewSet
)
from api.controllers.policy_controller import PolicyViewSet

router = DefaultRouter()
router.register(r'user-documents', UserDocumentViewSet, basename='user-documents')
router.register(r'profiles', ProfileViewSet, basename='profiles')
router.register(r'applications', ApplicationViewSet, basename='applications')
router.register(r'documents', DocumentViewSet, basename='documents')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-logs')
router.register(r'payments', PaymentViewSet, basename='payments')
router.register(r'appeals', AppealViewSet, basename='appeals')
router.register(r'policy', PolicyViewSet, basename='policy')

urlpatterns = [
    path('auth/', include('api.routes.auth_routes')),
    path('forms/', include('api.routes.form_routes')),
    path('', include(router.urls)),
]
