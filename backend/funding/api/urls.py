from django.urls import include, path
from rest_framework.routers import DefaultRouter

from funding.api.views import ApplicationViewSet, SchemaView

router = DefaultRouter()
router.register('applications', ApplicationViewSet, basename='application')

urlpatterns = [
    # No 'forms/forms/' stutter: the resource is named once.
    path('schemas/', SchemaView.as_view(), name='schema-list'),
    path('schemas/<str:slug>/', SchemaView.as_view(), name='schema-detail'),
    path('', include(router.urls)),
]
