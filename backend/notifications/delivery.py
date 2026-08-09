"""Queueing and delivering email.

Callers enqueue; a worker delivers. Delivery goes through Django's configured
EMAIL_BACKEND rather than a hand-rolled smtplib client, so the test suite uses
the locmem backend and can assert on what was sent — the previous transport
bypassed Django entirely and was untestable.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import OutboundEmail

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


def enqueue(to_email: str, subject: str, body_html: str, body_text: str = '') -> OutboundEmail | None:
    """Queue one email. Returns None when there is no address to send to."""
    if not to_email:
        logger.warning('Not queueing %r — no recipient address.', subject)
        return None
    return OutboundEmail.objects.create(
        to_email=to_email,
        subject=subject,
        body_html=body_html,
        body_text=body_text or '',
    )


def enqueue_on_commit(to_email: str, subject: str, body_html: str, body_text: str = '') -> None:
    """Queue only if the surrounding transaction commits.

    A decision email must never go out for a decision that rolled back.
    """
    transaction.on_commit(
        lambda: enqueue(to_email, subject, body_html, body_text)
    )


def deliver(email: OutboundEmail) -> bool:
    """Attempt one delivery. Records the outcome; never raises."""
    email.attempts += 1
    try:
        message = EmailMultiAlternatives(
            subject=email.subject,
            body=email.body_text or _strip_html(email.body_html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email.to_email],
        )
        message.attach_alternative(email.body_html, 'text/html')
        message.send(fail_silently=False)
    except Exception as exc:
        email.last_error = f'{type(exc).__name__}: {exc}'[:1000]
        # Give up only after repeated failure, so one flaky SMTP call does not
        # permanently discard a decision notice.
        email.status = (
            OutboundEmail.Status.FAILED
            if email.attempts >= MAX_ATTEMPTS
            else OutboundEmail.Status.PENDING
        )
        email.save(update_fields=['attempts', 'last_error', 'status'])
        logger.warning(
            'Email %s to %s failed (attempt %d/%d): %s',
            email.pk, email.to_email, email.attempts, MAX_ATTEMPTS, email.last_error,
        )
        return False

    email.status = OutboundEmail.Status.SENT
    email.sent_at = timezone.now()
    email.last_error = ''
    email.save(update_fields=['attempts', 'status', 'sent_at', 'last_error'])
    return True


def deliver_pending(limit: int = 50) -> dict:
    """Drain the queue. Returns counts for the caller to log."""
    pending = (OutboundEmail.objects
               .filter(status=OutboundEmail.Status.PENDING,
                       attempts__lt=MAX_ATTEMPTS)
               .order_by('queued_at')[:limit])

    sent = failed = 0
    for email in pending:
        if deliver(email):
            sent += 1
        else:
            failed += 1
    return {'sent': sent, 'failed': failed}


def _strip_html(html: str) -> str:
    """A plain-text fallback so the message is readable without HTML."""
    import re
    text = re.sub(r'<br\s*/?>|</p>|</div>|</tr>', '\n', html or '', flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()
