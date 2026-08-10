from django.urls import include, path
from rest_framework.routers import DefaultRouter

from funding.api.views import (
    ApplicationViewSet, EnrollmentVerificationView, SchemaView,
)

router = DefaultRouter()
router.register('applications', ApplicationViewSet, basename='application')

urlpatterns = [
    # No 'forms/forms/' stutter: the resource is named once.
    path('schemas/', SchemaView.as_view(), name='schema-list'),
    path('schemas/<str:slug>/', SchemaView.as_view(), name='schema-detail'),
    # Public, token-authenticated: the registrar has no account.
    path('enrolment/<str:token>/', EnrollmentVerificationView.as_view(),
         name='enrollment-verification'),
    path('', include(router.urls)),
]
