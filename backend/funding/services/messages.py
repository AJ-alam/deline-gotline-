"""What the portal tells people, and when.

Every message is queued on transaction commit, so a student is never told about
a decision that rolled back and a registrar never receives a link to a request
that was not saved.

Templates are plain functions returning a subject and a body. The previous
implementation held 379 lines of inline HTML inside a utilities module and sent
through a hand-rolled SMTP client that bypassed Django, so nothing about it
could be tested.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils.html import escape

from notifications.delivery import enqueue_on_commit
from notifications.models import Notification

logger = logging.getLogger(__name__)


def _frontend(path: str) -> str:
    base = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    return f"{base}/{path.lstrip('/')}"


def _wrap(heading: str, body_html: str) -> str:
    """The one email shell. Table-based, because mail clients are not browsers."""
    return (
        '<html><body style="margin:0;padding:24px;background:#faf8f4;'
        'font-family:Arial,Helvetica,sans-serif;color:#1a1814;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border:1px solid #e2dbcd;border-radius:10px;'
        'overflow:hidden;">'
        '<tr><td style="background:#1a1814;padding:20px 28px;">'
        '<div style="color:#e5a662;font-size:16px;font-weight:bold;">'
        'Deline Got’ı̨nę Government</div>'
        '<div style="color:#b8b1a4;font-size:12px;">Student Funding</div>'
        '</td></tr>'
        f'<tr><td style="padding:28px;">'
        f'<h1 style="margin:0 0 16px;font-size:19px;">{escape(heading)}</h1>'
        f'{body_html}</td></tr>'
        '<tr><td style="background:#f4f0e8;padding:14px 28px;font-size:11px;'
        'color:#7a7264;border-top:1px solid #e2dbcd;">'
        'This message was sent automatically. Please do not reply.'
        '</td></tr></table></td></tr></table></body></html>'
    )


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0;"><a href="{escape(url)}" '
        'style="background:#b8823c;color:#ffffff;padding:12px 22px;'
        'border-radius:6px;text-decoration:none;display:inline-block;">'
        f'{escape(label)}</a></p>'
        f'<p style="font-size:12px;color:#7a7264;">If the button does not work, '
        f'paste this address into your browser:<br>{escape(url)}</p>'
    )


# ── Registrar ───────────────────────────────────────────────────────────────

def send_enrolment_request(verification) -> None:
    """The link the whole tuition path depends on.

    Tuition is funded against the institution's figure, so until this arrives
    nothing can be awarded for it.
    """
    application = verification.application
    answers = application.answers or {}
    student = f"{answers.get('first_name', '')} {answers.get('last_name', '')}".strip()
    url = _frontend(f'/enrolment/{verification.token}')

    body = (
        f'<p>{escape(student or "A student")} has applied for post-secondary '
        'funding from the Deline Got’ı̨nę Government and named your '
        'institution.</p>'
        '<p>Before tuition can be funded we need the enrolment and the amount '
        'your institution has billed for the semester. The form takes a minute '
        'and does not require an account.</p>'
        f'<table role="presentation" cellpadding="4" style="font-size:14px;">'
        f'<tr><td style="color:#7a7264;">Student</td><td>{escape(student)}</td></tr>'
        f'<tr><td style="color:#7a7264;">Programme</td>'
        f'<td>{escape(str(answers.get("program", "")))}</td></tr>'
        f'<tr><td style="color:#7a7264;">Institution</td>'
        f'<td>{escape(str(answers.get("institution_name", "")))}</td></tr>'
        '</table>'
        + _button(url, 'Confirm enrolment')
        + '<p style="font-size:12px;color:#7a7264;">This link can be used once '
        'and expires in 30 days.</p>'
    )

    enqueue_on_commit(
        verification.registrar_email,
        f'Enrolment confirmation requested for {student or "a student"}',
        _wrap('Confirm a student’s enrolment', body),
    )


# ── Student ─────────────────────────────────────────────────────────────────

def send_application_received(application) -> None:
    student = application.student
    if not student:
        return

    body = (
        f'<p>We have received your {escape(application.get_type_display().lower())}.</p>'
        '<p>A student support worker will review it. You will hear from us when '
        'the review is complete, and you can check the status at any time.</p>'
        + _button(_frontend(f'/applications/{application.pk}'), 'View your application')
    )
    enqueue_on_commit(
        student.email,
        f'We received your {application.get_type_display().lower()}',
        _wrap('Application received', body),
    )
    _notify(student, 'Application received',
            f'Your {application.get_type_display().lower()} has been received.',
            f'/applications/{application.pk}')


def send_decision(application, approved: bool, reason: str = '') -> None:
    student = application.student
    if not student:
        return

    if approved:
        heading, subject = 'Your application was approved', 'Your funding application was approved'
        body = (
            '<p>Your application has been approved.</p>'
            '<p>The breakdown of your award, and the rule behind each part of it, '
            'is shown on your application.</p>'
        )
    else:
        heading, subject = 'A decision on your application', 'A decision on your funding application'
        body = (
            '<p>After review, your application was not approved.</p>'
            + (f'<p><strong>Reason:</strong> {escape(reason)}</p>' if reason else '')
            + '<p>If your circumstances have changed, or you believe the decision '
            'should be reconsidered, you may submit an appeal.</p>'
        )

    body += _button(_frontend(f'/applications/{application.pk}'), 'View your application')
    enqueue_on_commit(student.email, subject, _wrap(heading, body))
    _notify(student, heading,
            'Your application has been decided.', f'/applications/{application.pk}')


def send_information_requested(application, note: str = '') -> None:
    student = application.student
    if not student:
        return

    body = (
        '<p>We need a little more information before your application can be '
        'reviewed further.</p>'
        + (f'<p><strong>What we need:</strong> {escape(note)}</p>' if note else '')
        + _button(_frontend(f'/applications/{application.pk}'), 'Open your application')
    )
    enqueue_on_commit(
        student.email, 'More information needed for your application',
        _wrap('More information needed', body),
    )
    _notify(student, 'More information needed', note or 'Please review your application.',
            f'/applications/{application.pk}')


# ── In-portal ───────────────────────────────────────────────────────────────

def _notify(user, title: str, message: str, link: str = '') -> None:
    """A notice inside the portal, alongside the email.

    Never raises: a person's application must not fail because a notice could
    not be written.
    """
    try:
        Notification.objects.create(user=user, title=title, message=message, link=link)
    except Exception:
        logger.exception('Could not record a notification for user %s', getattr(user, 'pk', '?'))
