"""Whether outbound email can actually leave this deployment.

The enrolment verification is the message the whole tuition path depends on:
until the registrar opens their link no tuition can be confirmed and no
application can be forwarded. It is queued on commit and delivered by a
separate worker, so it fails silently in three independent places —
credentials not set, the worker never run, or the link pointing at a frontend
that is not there.

This module is the single assessment of all three. `manage.py email_status`
renders it as text and `GET /api/tasks/email-status/` renders it as JSON; both
are renderers over this dict and neither decides anything itself. A second
description of what "healthy email" means is a second thing to disagree — the
same reason the three approval-letter renderers all lay out `letters_for`.

Nothing here sends, retries or mutates a row: a diagnostic that changes the
thing it is measuring cannot be run to find out what is wrong.

**No secret is ever reported.** `EMAIL_HOST_PASSWORD` is described as set or
not set and never returned, because this reaches whoever holds `TASK_TOKEN`
and a diagnostic is not an escape hatch for reading credentials.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import get_connection
from django.db.models import Count
from django.core.mail.backends.console import EmailBackend as ConsoleBackend
from django.core.mail.backends.locmem import EmailBackend as LocmemBackend

from .models import OutboundEmail

# Addresses that mean "this machine". A registrar anywhere else cannot open a
# link to one, and the failure is invisible from the office, whose own browser
# resolves it perfectly.
LOCAL_HOSTS = ('localhost', '127.0.0.1', '0.0.0.0', '::1')

# How many distinct pending recipients to name. Enough to tell testing from a
# real intake; not so many that the answer is a wall.
RECIPIENT_SAMPLE = 40


def backend_kind(backend_path: str) -> str:
    """Which family the configured backend belongs to.

    By class rather than by dotted path: the local console backend here is a
    subclass that writes UTF-8, and matching on the path reported it as SMTP
    and complained about credentials it does not need.
    """
    try:
        connection = get_connection(backend=backend_path, fail_silently=True)
    except Exception:
        return 'unknown'
    if isinstance(connection, LocmemBackend):
        return 'locmem'
    if isinstance(connection, ConsoleBackend):
        return 'console'
    return 'smtp'


def email_health() -> dict:
    """Everything known about whether mail can leave, and what is wrong.

    `problems` are reasons no email will arrive; `notes` are things worth
    knowing that are not faults. The caller renders them and decides nothing.
    """
    problems: list[str] = []
    notes: list[str] = []

    backend = settings.EMAIL_BACKEND
    kind = backend_kind(backend)

    delivery = {
        'backend': backend,
        'kind': kind,
        'host': settings.EMAIL_HOST,
        'port': settings.EMAIL_PORT,
        'use_tls': settings.EMAIL_USE_TLS,
        'username': settings.EMAIL_HOST_USER or '',
        # Set or not set. Never the value — see the module docstring.
        'password_set': bool(settings.EMAIL_HOST_PASSWORD),
        'from_email': settings.DEFAULT_FROM_EMAIL,
    }

    if kind == 'console':
        notes.append(
            'The console backend prints mail to the terminal running the '
            'worker instead of sending it. Fine for local work; nothing '
            'reaches a real registrar.'
        )
    elif kind == 'locmem':
        problems.append('The locmem backend discards mail. It is for tests only.')
    else:
        if not settings.EMAIL_HOST_USER:
            problems.append('EMAIL_HOST_USER is not set, so SMTP cannot authenticate.')
        if not settings.EMAIL_HOST_PASSWORD:
            problems.append('EMAIL_HOST_PASSWORD is not set, so SMTP cannot authenticate.')

    # ── The link inside the message ──
    frontend = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
    links = {
        'frontend_url': frontend,
        'registrar_link': f'{frontend}/enrolment/<token>' if frontend else '',
    }
    if not frontend:
        problems.append(
            'FRONTEND_URL is not set, so the registrar link has no host and '
            'the enrolment form cannot be opened.'
        )
    elif (urlparse(frontend).hostname or '') in LOCAL_HOSTS:
        # A problem rather than a note on a deployed process: mail really does
        # go out, carrying a link only the sender's own machine can open, and
        # the registrar has no way to report that back.
        #
        # `TESTING` as well as `DEBUG`, because the test settings are a
        # deployment by neither name nor intent and run with DEBUG off. Without
        # it every suite that renders this report starts failing on a localhost
        # address it is supposed to have.
        message = (
            f'FRONTEND_URL is {frontend}, which points at the machine running '
            'this process. A registrar elsewhere cannot open that link.'
        )
        local_process = settings.DEBUG or getattr(settings, 'TESTING', False)
        (notes if local_process else problems).append(message)

    # ── The queue ──
    counts = {status: OutboundEmail.objects.filter(status=status).count()
              for status, _ in OutboundEmail.Status.choices}
    oldest = (OutboundEmail.objects
              .filter(status=OutboundEmail.Status.PENDING)
              .order_by('queued_at')
              .values_list('queued_at', flat=True)
              .first())
    # Who the backlog would reach if it were drained now.
    #
    # Distinct addresses with counts rather than 112 rows: the question this
    # answers is "is this real people or a morning of testing", and a handful of
    # repeated addresses answers it where a list nobody reads to the end does
    # not. Capped, because a genuine backlog after an outage is unbounded and a
    # diagnostic that returns a megabyte is one that times out.
    #
    # Behind the task token, and these are addresses the office already sees on
    # the applications themselves — but it is still the one personal data this
    # endpoint returns, which is why it is a summary and not the rows.
    recipients = list(
        OutboundEmail.objects
        .filter(status=OutboundEmail.Status.PENDING)
        .values('to_email')
        .annotate(count=Count('id'))
        .order_by('-count', 'to_email')[:RECIPIENT_SAMPLE]
    )
    distinct_recipients = (OutboundEmail.objects
                           .filter(status=OutboundEmail.Status.PENDING)
                           .values('to_email').distinct().count())

    last_failure = (OutboundEmail.objects
                    .filter(status=OutboundEmail.Status.FAILED)
                    .order_by('-queued_at')
                    .first())

    queue = {
        'pending': counts.get('pending', 0),
        'sent': counts.get('sent', 0),
        'failed': counts.get('failed', 0),
        'oldest_pending_at': oldest.isoformat() if oldest else None,
        'last_error': last_failure.last_error if last_failure else '',
        'distinct_recipients': distinct_recipients,
        'pending_recipients': recipients,
    }

    # Nothing has ever been delivered from this database. The queue filling
    # while `sent` stays at nought is exactly what a scheduler that was never
    # set up looks like, and it is indistinguishable from working software
    # from every screen in the portal.
    if queue['pending'] and not queue['sent']:
        problems.append(
            f"{queue['pending']} messages are queued and none has ever been "
            'sent from this database. Nothing drains the queue by itself — '
            'POST /api/tasks/send-emails/ must be called on a schedule.'
        )
    elif queue['pending']:
        notes.append(
            f"{queue['pending']} messages are waiting. That is ordinary if the "
            'scheduler runs in the next few minutes, and a stopped scheduler '
            'if it does not — compare oldest_pending_at against now.'
        )
    if last_failure:
        problems.append(f'Last delivery failure: {last_failure.last_error}')

    return {
        'delivery': delivery,
        'links': links,
        'queue': queue,
        'problems': problems,
        'notes': notes,
        'deliverable': not problems,
    }
