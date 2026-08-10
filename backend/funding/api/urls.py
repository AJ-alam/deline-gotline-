from django.urls import include, path
from rest_framework.routers import DefaultRouter

from funding.api.finance_views import DispatchView, PendingAwardsView
from funding.api.policy_views import (
    PolicySettingDetailView, PolicySettingsView, RuleSetsView,
)
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
    path('finance/pending/', PendingAwardsView.as_view(), name='finance-pending'),
    path('finance/dispatch/', DispatchView.as_view(), name='finance-dispatch'),
    path('policy/rates/', PolicySettingsView.as_view(), name='policy-rates'),
    path('policy/rates/<int:pk>/', PolicySettingDetailView.as_view(),
         name='policy-rate-detail'),
    path('policy/rule-sets/', RuleSetsView.as_view(), name='policy-rule-sets'),
    path('', include(router.urls)),
]
