from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormViewSet, FormSubmissionViewSet

router = DefaultRouter()
router.register(r'forms', FormViewSet, basename='form')
router.register(r'submissions', FormSubmissionViewSet, basename='submission')

urlpatterns = [
    path('', include(router.urls)),
]
