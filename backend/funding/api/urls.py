from django.urls import include, path
from rest_framework.routers import DefaultRouter

from funding.api.document_read import DocumentView
from funding.api.document_views import DocumentUploadView
from funding.api.finance_views import DispatchView, PendingAwardsView
from funding.api.policy_views import (
    PolicySettingDetailView, PolicySettingsView, RuleSetsView,
)
from funding.api.views import (
    ApplicationViewSet, DashboardView, EnrolmentPreviewView,
    EnrollmentVerificationView, GuestApplicationView, PrefillView, SchemaView,
)

router = DefaultRouter()
router.register('applications', ApplicationViewSet, basename='application')

urlpatterns = [
    # No 'forms/forms/' stutter: the resource is named once.
    path('schemas/', SchemaView.as_view(), name='schema-list'),
    path('schemas/<str:slug>/', SchemaView.as_view(), name='schema-detail'),
    # Not under schemas/: a schema is public and cached, this is one student's
    # own answers. Sharing a path invites sharing a cache entry.
    path('form-prefill/<str:slug>/', PrefillView.as_view(), name='form-prefill'),
    # Public: the two one-off awards can be claimed without an account.
    path('guest-applications/', GuestApplicationView.as_view(), name='guest-applications'),
    # Public, token-authenticated: the registrar has no account.
    path('enrolment/<str:token>/', EnrollmentVerificationView.as_view(),
         name='enrollment-verification'),
    path('documents/', DocumentUploadView.as_view(), name='document-upload'),
    path('documents/<int:pk>/', DocumentView.as_view(), name='document-read'),
    # What the registrar will receive, shown to the student before they submit.
    path('enrolment-preview/', EnrolmentPreviewView.as_view(),
         name='enrolment-preview'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('finance/pending/', PendingAwardsView.as_view(), name='finance-pending'),
    path('finance/dispatch/', DispatchView.as_view(), name='finance-dispatch'),
    path('policy/rates/', PolicySettingsView.as_view(), name='policy-rates'),
    path('policy/rates/<int:pk>/', PolicySettingDetailView.as_view(),
         name='policy-rate-detail'),
    path('policy/rule-sets/', RuleSetsView.as_view(), name='policy-rule-sets'),
    path('', include(router.urls)),
]
