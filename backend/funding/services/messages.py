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
    from funding.services.verification import student_name

    application = verification.application
    answers = application.answers or {}
    # Resolved in one place: this used to read first_name/last_name directly and
    # would have addressed a continuing-funding registrar's email to "A student".
    student = student_name(application)
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
            f'/applications/{application.pk}', Notification.Kind.RECEIVED)


def send_guest_application_received(application) -> None:
    """The only acknowledgement someone applying without an account gets.

    Every other message here needs `application.student` and returns early
    without one, so a guest submission would otherwise be met with silence: no
    email, no portal notice, and no way to check. The address comes from the
    answers, and the reference number is the only handle they have on it.
    """
    email = (application.answers or {}).get('email')
    if not email:
        return

    body = (
        f'<p>We have received your {escape(application.get_type_display().lower())}.</p>'
        '<p>You applied without a portal account, so please keep this reference '
        'number — it is how the Education Department will find your '
        'application.</p>'
        f'<p style="font-size:20px;font-weight:bold;letter-spacing:0.04em;">'
        f'DGG-{application.pk:06d}</p>'
        '<p>Staff will review it and contact you at this address. If you create '
        'a portal account later, they can attach this application to it.</p>'
    )
    enqueue_on_commit(
        email,
        f'We received your {application.get_type_display().lower()} '
        f'(DGG-{application.pk:06d})',
        _wrap('Application received', body),
    )


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
    _notify(student, heading, 'Your application has been decided.',
            f'/applications/{application.pk}',
            Notification.Kind.APPROVED if approved else Notification.Kind.DECLINED)


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
    _notify(student, 'More information needed',
            note or 'Please review your application.',
            f'/applications/{application.pk}', Notification.Kind.ACTION_NEEDED)


def send_application_amended(application, actor=None, note: str = '') -> None:
    """The office changed something on a filed application.

    Told to the applicant without being asked for, because it is their
    application and somebody else has altered what it says. A correction the
    applicant never hears about is indistinguishable from a record that was
    never right — and it is the version they would be held to on appeal.
    """
    student = application.student
    if not student:
        return

    who = getattr(actor, 'full_name', '') or 'The Education Department'
    body = (
        f'<p>{escape(who)} has updated your '
        f'{escape(application.get_type_display())} application.</p>'
        + (f'<p><strong>What changed:</strong> {escape(note)}</p>' if note else '')
        + '<p>Please open it and check that everything is correct. Tell the '
          'office if anything is wrong.</p>'
        + _button(_frontend(f'/applications/{application.pk}'), 'Open your application')
    )
    enqueue_on_commit(
        student.email, 'Your application has been updated by the office',
        _wrap('Your application has been updated', body),
    )
    _notify(student, 'Your application was updated by the office',
            note or f'{who} changed some of your answers. Please check them.',
            f'/applications/{application.pk}', Notification.Kind.AMENDED)


def send_amended_while_awaiting_decision(application, actor=None,
                                         note: str = '') -> None:
    """The answers changed under a director who is mid-decision.

    An amendment leaves the application exactly where it sits, which is the
    point of it — but where it sits may be the director's queue. They were asked
    to decide one thing and are now deciding another, with nothing on the screen
    saying so. That is the same fault as forwarding an application and approving
    it a second later: somebody is asked to act on a state that has since
    changed and is not told.

    Only the applicant was told. They are not the person about to sign it off.
    """
    from accounts.models import Role

    who = getattr(actor, 'full_name', '') or 'The Education Department'
    applicant = application.student.full_name if application.student else 'A claimant'
    tell_the_office(
        application, [Role.DIRECTOR],
        'An application waiting on you has changed',
        f'{who} amended {applicant}’s {application.get_type_display()} while it '
        f'was awaiting your decision.'
        + (f' What changed: {note}' if note else ''))


def tell_the_office(application, roles, title: str, message: str) -> None:
    """A notice for the people whose turn it is.

    Only in the portal, and no email: the office works from these screens all
    day, and a mailbox filling with copies of what the queue already shows is a
    mailbox that gets filtered. The applicant's messages still go by both,
    because they are not sitting in the portal waiting.

    Everything up to now told only the applicant. A reviewer had no way to know
    a student had answered a request except by opening the queue and looking,
    and a director had no way to know an application was waiting for them at
    all.
    """
    from accounts.models import User

    for person in User.objects.filter(role__in=roles, is_active=True):
        _notify(person, title, message, f'/applications/{application.pk}',
                Notification.Kind.ACTION_NEEDED)


def send_awaiting_decision(application) -> None:
    """A director has an application to decide."""
    from accounts.models import Role

    who = application.student.full_name if application.student else 'A claimant'
    tell_the_office(
        application, [Role.DIRECTOR, Role.ADMIN],
        'An application is waiting for a decision',
        f'{who}’s {application.get_type_display()} has been forwarded for a decision.')


def send_information_provided(application) -> None:
    """A student has answered what was asked."""
    from accounts.models import Role

    who = application.student.full_name if application.student else 'A claimant'
    tell_the_office(
        application, [Role.SUPPORT_WORKER, Role.ADMIN],
        'A student has answered your request',
        f'{who} has updated their {application.get_type_display()} and sent it back.')


def send_decided_by_the_office(application, actor, approved: bool) -> None:
    """An administrator decided without the director.

    The office asked for this: an administrator may approve rather than forward.
    The director is told after the fact, because a decision made without them is
    still a decision they answer for.
    """
    from accounts.models import Role

    who = application.student.full_name if application.student else 'A claimant'
    tell_the_office(
        application, [Role.DIRECTOR],
        f'{"Approved" if approved else "Declined"} by {getattr(actor, "full_name", "the office")}',
        f'{who}’s {application.get_type_display()} was '
        f'{"approved" if approved else "declined"} without being forwarded.')


# ── In-portal ───────────────────────────────────────────────────────────────

def _notify(user, title: str, message: str, link: str = '',
            kind: str = Notification.Kind.GENERAL) -> None:
    """A notice inside the portal, alongside the email.

    Never raises: a person's application must not fail because a notice could
    not be written.
    """
    try:
        Notification.objects.create(
            user=user, kind=kind, title=title, message=message, link=link)
    except Exception:
        logger.exception('Could not record a notification for user %s', getattr(user, 'pk', '?'))
