from django.urls import path

from notifications.api.views import (
    EmailStatusView, NotificationsView, SendQueuedEmailsView,
)

urlpatterns = [
    path('notifications/', NotificationsView.as_view(), name='notifications'),
    path('tasks/send-emails/', SendQueuedEmailsView.as_view(),
         name='send-queued-emails'),
    path('tasks/email-status/', EmailStatusView.as_view(),
         name='email-status'),
]
