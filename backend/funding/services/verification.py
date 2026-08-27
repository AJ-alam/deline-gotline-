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
# student's own answers through this route, and every one of them must be a
# field the admission schema itself defines — otherwise the application would
# end up carrying answers its own schema cannot validate.
CONFIRMABLE_KEYS = ('confirmed_tuition', 'course_load', 'semester_start', 'semester_end')

# How the enrolment verification is filled in from the application it came from.
# Left of the arrow is a field on the generated form; right is where the answer
# comes from. Anything absent here the registrar fills in themselves.
#
# Date of birth and SIN are deliberately not carried across. The institution
# does not need either to confirm an enrolment, and a government identifier
# does not belong in an unencrypted mailbox.
PREFILL = {
    'student_number': 'student_number',
    'student_phone': 'phone',
    'student_email': 'email',
    'institution_name': 'institution_name',
    'program': 'program',
    'credential_level': 'credential_level',
    'course_load': 'course_load',
    'semester': 'semester',
    'program_year': 'program_year',
    'program_length_years': 'program_length_years',
    'semester_start': 'semester_start',
    'semester_end': 'semester_end',
    'confirmed_tuition': 'tuition_requested',
    'institution_email': 'registrar_email',
    'institution_phone': 'institution_phone',
}


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

    created = EnrollmentVerification.objects.create(
        application=application,
        registrar_email=registrar_email,
        token=secrets.token_urlsafe(TOKEN_BYTES),
        expires_at=timezone.now() + validity,
    )
    # Queued on commit: a registrar must never receive a link to a request that
    # was rolled back.
    from funding.services.messages import send_enrolment_request
    send_enrolment_request(created)
    return created


def reissue_if_address_changed(application) -> EnrollmentVerification | None:
    """Re-ask the institution when the address on the application has moved.

    `registrar_email` became a stored answer when the renewal started asking for
    one, which made it editable — by the student answering a request for more
    information, and by the office amending a filed application. Nothing noticed
    the change. The application recorded the corrected address while the only
    live link sat in the wrong institution's mailbox, and no screen said the two
    disagreed.

    That is the office's most common corrective action. A registrar's address
    bounces, the reviewer asks the student to fix it, the student fixes it, and
    the request is never sent again — with tuition funded against the
    registrar's figure, the application then cannot be priced by anybody.

    Deliberately narrow:

      - only for types that need a confirmation at all;
      - never over a *completed* one, which `issue` refuses anyway: the
        institution has already answered and the answer is what tuition is
        funded against. An address corrected after that is a correction to the
        record, not a reason to ask again;
      - only when the address actually differs, so an edit that changes a
        misspelled programme does not send an institution a second link and
        invalidate the one its registrar is part-way through filling in.

    Returns the new verification, or None when nothing needed doing.
    """
    from funding.services.workflow import NEEDS_ENROLMENT_CONFIRMATION

    if application.type not in NEEDS_ENROLMENT_CONFIRMATION:
        return None

    wanted = str((application.answers or {}).get('registrar_email') or '').strip()
    if not wanted:
        return None

    existing = EnrollmentVerification.objects.filter(application=application).first()
    if existing is not None:
        if existing.status == EnrollmentVerification.Status.COMPLETED:
            return None
        if existing.registrar_email.strip().lower() == wanted.lower():
            return None

    try:
        return issue(application, wanted)
    except VerificationError as exc:
        # Never fail the edit over this. The student has just answered a request
        # for more information, or the office has just corrected a form; losing
        # that write because a mail row could not be queued would be worse than
        # the stale link, and staff can reissue by hand.
        logger.warning(
            'Could not re-issue the enrolment request for application %s: %s',
            application.pk, exc)
        return None


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


def student_name(application) -> str:
    """Who the application is about, however its schema asks the question.

    Most forms ask for a first and last name. The continuing-funding renewal
    asks for one `full_name`, because it shows what is already on file for
    confirmation rather than collecting it. Both spellings resolve here, so
    nothing downstream has to know which schema it is looking at — a registrar's
    email addressed to "A student" is how that goes wrong.
    """
    answers = application.answers or {}
    for key in ('full_name', 'student_name'):
        single = str(answers.get(key) or '').strip()
        if single:
            return single
    parts = f"{answers.get('first_name', '')} {answers.get('last_name', '')}".strip()
    return parts or (application.student.full_name if application.student else '')


def prefill_for(application) -> dict:
    """The enrolment verification, already filled in from the application.

    The registrar confirms rather than retypes. Every value here came from the
    student, which is exactly why the form says so: the institution is being
    asked to check these against its own records, not to trust them.
    """
    answers = application.answers or {}
    filled = {'student_name': student_name(application)}
    for target, source in PREFILL.items():
        value = answers.get(source)
        if value not in (None, ''):
            filled[target] = value
    return filled


def context_for(verification: EnrollmentVerification) -> dict:
    """What the registrar is shown.

    Deliberately narrow: enough to identify the student and confirm the
    enrolment. Not their address, banking, beneficiary number, date of birth or
    SIN — the registrar is answering one question, not reviewing a file.
    """
    application = verification.application
    return {
        'student_name': student_name(application),
        'institution_name': (application.answers or {}).get('institution_name', ''),
        'program': (application.answers or {}).get('program', ''),
        'expires_at': verification.expires_at.isoformat(),
        'note_to_registrar': (
            'The student has verified their identity and contact information '
            'through the DGG Student Portal. Their date of birth and Social '
            'Insurance Number have been withheld from this form to protect '
            'their identity.'
        ),
        # What the form arrives with already filled in.
        'prefill': prefill_for(application),
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
    # The institution's declaration in full, kept with the verification rather
    # than merged into the student's answers.
    locked.answers = {
        key: (value if isinstance(value, (str, int, float, bool)) else str(value))
        for key, value in cleaned.items()
    }
    locked.save(update_fields=[
        'confirmed_enrolled', 'confirmed_course_load', 'registrar_name',
        'responded_at', 'status', 'answers',
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
