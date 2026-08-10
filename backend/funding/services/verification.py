"""Asking an institution to confirm a student's enrolment.

Tuition is funded against the registrar's figure, never the student's estimate,
so nothing can be awarded for tuition until this comes back. That makes the link
sent to the registrar a route into the money path, and it is treated as one:
the token is random, single-use, expiring, and reveals only what the registrar
needs to answer the question.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from funding.models import Application, EnrollmentVerification
from funding.schemas import ValidationError, get_schema

logger = logging.getLogger(__name__)

# Long enough that guessing is not worth attempting, short enough to paste.
TOKEN_BYTES = 32
DEFAULT_VALIDITY = timedelta(days=30)

# What the registrar confirms, copied onto the application when they answer.
# Only these keys are accepted: a registrar must not be able to rewrite the
# student's own answers through this route.
CONFIRMABLE_KEYS = ('confirmed_tuition', 'course_load', 'semester_start', 'semester_end')


class VerificationError(Exception):
    """The link is not usable."""


def issue(application: Application, registrar_email: str,
          validity: timedelta = DEFAULT_VALIDITY) -> EnrollmentVerification:
    """Create (or replace) the verification request for an application."""
    if not registrar_email:
        raise VerificationError('No registrar email was given.')

    # Read from the database rather than the reverse accessor: a caller holding
    # an Application fetched before the verification was completed would see a
    # stale cached copy and reissue over a confirmation that already happened.
    existing = EnrollmentVerification.objects.filter(application=application).first()
    if existing is not None:
        if existing.status == EnrollmentVerification.Status.COMPLETED:
            raise VerificationError('Enrolment has already been verified.')
        # Reissuing invalidates the previous link rather than leaving two live.
        existing.delete()

    return EnrollmentVerification.objects.create(
        application=application,
        registrar_email=registrar_email,
        token=secrets.token_urlsafe(TOKEN_BYTES),
        expires_at=timezone.now() + validity,
    )


def resolve(token: str) -> EnrollmentVerification:
    """Find a usable verification by token.

    Every failure raises the same error: distinguishing 'expired' from 'unknown'
    would tell someone probing tokens which guesses were close.
    """
    try:
        verification = (EnrollmentVerification.objects
                        .select_related('application', 'application__student')
                        .get(token=token))
    except EnrollmentVerification.DoesNotExist:
        raise VerificationError('This link is not valid.')

    if verification.status == EnrollmentVerification.Status.COMPLETED:
        raise VerificationError('This enrolment has already been confirmed.')
    if verification.expires_at <= timezone.now():
        verification.status = EnrollmentVerification.Status.EXPIRED
        verification.save(update_fields=['status'])
        raise VerificationError('This link has expired.')

    return verification


def context_for(verification: EnrollmentVerification) -> dict:
    """What the registrar is shown.

    Deliberately narrow: the student's name and programme, enough to look them
    up. Not their address, banking, beneficiary number or anything else on the
    application — the registrar is answering one question, not reviewing a file.
    """
    answers = verification.application.answers or {}
    student = verification.application.student
    return {
        'student_name': (
            f"{answers.get('first_name', '')} {answers.get('last_name', '')}".strip()
            or (student.full_name if student else '')
        ),
        'date_of_birth': answers.get('date_of_birth', ''),
        'institution_name': answers.get('institution_name', ''),
        'program': answers.get('program', ''),
        'semester': answers.get('semester', ''),
        'expires_at': verification.expires_at.isoformat(),
    }


@transaction.atomic
def complete(verification: EnrollmentVerification, submitted: dict) -> EnrollmentVerification:
    """Record the registrar's answers and copy the confirmed facts across.

    Single-use: the row is locked and re-checked, so a link opened twice cannot
    be submitted twice and change an award after a decision was made on it.
    """
    locked = (EnrollmentVerification.objects
              .select_for_update()
              .select_related('application')
              .get(pk=verification.pk))
    if locked.status == EnrollmentVerification.Status.COMPLETED:
        raise VerificationError('This enrolment has already been confirmed.')

    schema = get_schema('enrollment_verification')
    try:
        cleaned = schema.clean(submitted)
    except ValidationError:
        raise

    locked.confirmed_enrolled = bool(cleaned.get('is_enrolled'))
    locked.confirmed_course_load = str(cleaned.get('course_load') or '')
    locked.registrar_name = str(cleaned.get('registrar_name') or '')
    locked.responded_at = timezone.now()
    locked.status = EnrollmentVerification.Status.COMPLETED
    locked.save(update_fields=[
        'confirmed_enrolled', 'confirmed_course_load', 'registrar_name',
        'responded_at', 'status',
    ])

    application = locked.application
    answers = dict(application.answers or {})
    for key in CONFIRMABLE_KEYS:
        if key in cleaned:
            answers[key] = (
                str(cleaned[key]) if not isinstance(cleaned[key], (str, int, float, bool))
                else cleaned[key]
            )
    application.answers = answers
    application.save(update_fields=['answers', 'updated_at'])

    logger.info(
        'Enrolment verified for application %s by %s (enrolled=%s).',
        application.pk, locked.registrar_name or locked.registrar_email,
        locked.confirmed_enrolled,
    )
    return locked
