from django.db import models
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Notification for {self.user.email}: {self.title}"


class OutboundEmail(models.Model):
    """An email queued for delivery.

    Mail used to be handed to a daemon thread that returned success immediately.
    On serverless the process is frozen once the response is returned, so
    approval and denial notices were lost with no error anywhere. Sending inline
    fixed the loss but put a 30s SMTP timeout on the request path.

    Writing a row is fast and transactional: if the surrounding transaction rolls
    back, the email is never queued, so a student cannot be told about a decision
    that did not commit. A worker drains the queue and retries failures.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)

    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'outbound_email'
        ordering = ('queued_at',)
        indexes = [models.Index(fields=('status', 'queued_at'))]

    def __str__(self):
        return f'{self.subject} to {self.to_email} ({self.status})'
