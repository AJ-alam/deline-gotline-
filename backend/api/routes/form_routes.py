from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.controllers.form_controller import FormController, SubmissionController, FormBPublicView

router = DefaultRouter()
router.register(r'forms', FormController, basename='forms')
router.register(r'submissions', SubmissionController, basename='submissions')

urlpatterns = [
    path('', include(router.urls)),
    path('form-b/<str:token>/', FormBPublicView.as_view(), name='form-b-public'),
]
