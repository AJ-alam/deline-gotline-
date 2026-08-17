"""Moving an application through review.

Status is not set directly. Every change is an event, and the status column is
what the events fold to — kept in sync by the one function that appends them.

The old model had a mutable status alongside sixteen timestamp and actor columns
recording the same history. They could disagree, and did: a record could be
'approved' with no approval event, or carry a decided_at with a pending status.
Here the event log is the truth and the column is a cached read.
"""

from __future__ import annotations

import logging

from django.db import transaction

from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    EnrollmentVerification,
)

logger = logging.getLogger(__name__)

Action = ApplicationEvent.Action

# What each action means for the application's state.
RESULTING_STATUS = {
    Action.SUBMITTED: ApplicationStatus.SUBMITTED,
    Action.REVIEWED: ApplicationStatus.UNDER_REVIEW,
    Action.INFO_REQUESTED: ApplicationStatus.INFO_REQUESTED,
    Action.INFO_PROVIDED: ApplicationStatus.UNDER_REVIEW,
    Action.FORWARDED: ApplicationStatus.AWAITING_DECISION,
    Action.APPROVED: ApplicationStatus.APPROVED,
    Action.DECLINED: ApplicationStatus.DECLINED,
    Action.SENT_TO_FINANCE: ApplicationStatus.SENT_TO_FINANCE,
}

# Which actions may follow a given status. Encoded here rather than scattered
# across view code, so an invalid transition is impossible to perform rather
# than merely discouraged.
ALLOWED_ACTIONS = {
    ApplicationStatus.DRAFT: {Action.SUBMITTED},
    ApplicationStatus.SUBMITTED: {Action.REVIEWED, Action.INFO_REQUESTED, Action.DECLINED},
    # A reviewed application can be forwarded to the director, or decided here
    # and now. §13 puts the final decision with the Director of Education, and
    # an administrator holds that authority — `decides_applications` is what the
    # endpoint checks, and a support worker is refused by it.
    #
    # Deciding used to require FORWARDED first, which is not a shortcut being
    # closed but a lie being told: the forward notifies the director that an
    # application is *waiting for them*, and the administrator then approved it
    # a second later. The director read one notice asking them to act on
    # something already decided, followed by another saying it had been. They
    # are still told either way — see `_announce`.
    ApplicationStatus.UNDER_REVIEW: {
        Action.INFO_REQUESTED, Action.FORWARDED, Action.APPROVED, Action.DECLINED,
    },
    ApplicationStatus.INFO_REQUESTED: {Action.INFO_PROVIDED, Action.DECLINED},
    ApplicationStatus.AWAITING_DECISION: {
        Action.APPROVED, Action.DECLINED, Action.INFO_REQUESTED,
    },
    ApplicationStatus.APPROVED: {Action.SENT_TO_FINANCE},
    ApplicationStatus.DECLINED: set(),
    ApplicationStatus.SENT_TO_FINANCE: set(),
}


class EnrolmentNotConfirmed(Exception):
    """The institution has not confirmed this enrolment yet.

    Tuition is funded against the registrar's figure, never the student's
    estimate. Approving before that figure exists means approving an amount
    nobody has verified, so the application cannot leave review until the
    enrolment verification comes back.
    """

    def __init__(self, application):
        self.application = application
        verification = getattr(application, 'enrollment_verification', None)
        state = verification.status if verification else 'not requested'
        super().__init__(
            'The institution has not confirmed this enrolment yet '
            f'(enrolment verification: {state}). Tuition is funded against the '
            'registrar’s figure, so this application cannot be forwarded or '
            'decided until the verification is returned.'
        )


class InvalidTransition(Exception):
    """This action cannot follow the application's current status."""

    def __init__(self, application, action):
        self.action = action
        self.current = application.status
        allowed = ALLOWED_ACTIONS.get(application.status, set())
        super().__init__(
            f'Cannot {action} an application that is '
            f'{application.get_status_display().lower()}. '
            + (f'Allowed: {", ".join(sorted(allowed))}.' if allowed
               else 'It has reached a final state.')
        )


def derive_status(events) -> str:
    """Fold an event sequence to a status.

    The single definition of what a history means. Anything reconstructing an
    application's state — a repair command, an import, a test — uses this rather
    than reimplementing the mapping.
    """
    status = ApplicationStatus.DRAFT
    for event in events:
        mapped = RESULTING_STATUS.get(event.action)
        if mapped:
            status = mapped
    return status


# Types whose award depends on the institution confirming enrolment and the
# tuition actually billed.
NEEDS_ENROLMENT_CONFIRMATION = (
    ApplicationType.ADMISSION,
    ApplicationType.CONTINUING_FUNDING,
)


def can(application, action) -> bool:
    return action in ALLOWED_ACTIONS.get(application.status, set())


# Actions that commit the office to an amount, and so cannot be taken before
# the institution has confirmed what it is charging.
NEEDS_CONFIRMED_ENROLMENT = {Action.FORWARDED, Action.APPROVED}


def enrolment_is_confirmed(application, action) -> bool:
    """Whether this action is allowed to proceed on the enrolment evidence.

    Declining is deliberately not gated: an application that will never be
    approved should not be held open waiting on a registrar who may never
    answer. Nor are types that do not fund tuition — a graduation bursary has
    no institution to ask.
    """
    if action not in NEEDS_CONFIRMED_ENROLMENT:
        return True
    if application.type not in NEEDS_ENROLMENT_CONFIRMATION:
        return True

    verification = EnrollmentVerification.objects.filter(
        application=application).first()
    return bool(
        verification
        and verification.status == EnrollmentVerification.Status.COMPLETED
        and verification.confirmed_enrolled
    )


@transaction.atomic
def record(application, action, actor=None, note='') -> ApplicationEvent:
    """Append an event and move the application to the status it implies.

    The only way status changes. Nothing else assigns to the column.
    """
    if action not in RESULTING_STATUS:
        raise InvalidTransition(application, action)

    # Lock the row so two staff acting at once cannot interleave a transition
    # against a status one of them has already moved past.
    locked = Application.objects.select_for_update().get(pk=application.pk)
    if not can(locked, action):
        raise InvalidTransition(locked, action)
    if not enrolment_is_confirmed(locked, action):
        raise EnrolmentNotConfirmed(locked)

    event = ApplicationEvent.objects.create(
        application=locked, action=action, actor=actor, note=note,
    )

    locked.status = RESULTING_STATUS[action]
    locked.save(update_fields=['status', 'updated_at'])

    # Which term this is for, and whether it made the cut-off. Decided here
    # because this is the one point every submission passes through, and decided
    # now rather than on read so that editing a deadline later cannot make an
    # application that was on time retroactively late.
    if action == Action.SUBMITTED:
        from funding.services import deadlines
        deadlines.stamp(locked)

    # Keep the caller's instance consistent with what was written.
    application.status = locked.status
    application.semester = locked.semester
    application.academic_year = locked.academic_year
    application.submitted_after_deadline = locked.submitted_after_deadline

    _announce(locked, action, note, actor)
    return event


def _announce(application, action, note: str, actor=None) -> None:
    """Tell the applicant what happened — and the office whose turn it is.

    Queued on commit inside the same transaction as the event, so a message can
    never describe a transition that did not persist.
    """
    from funding.services import messages

    if action == Action.SUBMITTED:
        # An application with no account behind it still has someone waiting on
        # it; the student messages all require `student` and would say nothing.
        if application.student_id:
            messages.send_application_received(application)
        else:
            messages.send_guest_application_received(application)
        _request_enrolment_confirmation(application)
    elif action == Action.INFO_REQUESTED:
        messages.send_information_requested(application, note)
    elif action == Action.APPROVED:
        messages.send_decision(application, approved=True)
    elif action == Action.DECLINED:
        messages.send_decision(application, approved=False, reason=note)
    elif action == Action.FORWARDED:
        # Nothing told a director an application was waiting for them. The
        # queue showed it; knowing to look at the queue was the whole problem.
        messages.send_awaiting_decision(application)
    elif action == Action.INFO_PROVIDED:
        messages.send_information_provided(application)

    # An administrator may decide instead of forwarding. The director does not
    # make that decision but still answers for it, so they are told.
    from accounts.models import Role
    if (action in (Action.APPROVED, Action.DECLINED)
            and getattr(actor, 'role', None) == Role.ADMIN):
        messages.send_decided_by_the_office(
            application, actor, approved=action == Action.APPROVED)


def _request_enrolment_confirmation(application) -> None:
    """Ask the institution to confirm, as soon as the application is submitted.

    Tuition is funded against the registrar's figure, so without this the
    application can never be priced for tuition at all. Failing to send must not
    fail the submission: the request can be reissued by staff.
    """
    from funding.services import verification

    if application.type not in NEEDS_ENROLMENT_CONFIRMATION:
        return
    registrar_email = registrar_email_for(application)
    if not registrar_email:
        return

    try:
        verification.issue(application, registrar_email)
    except verification.VerificationError as exc:
        logger.warning(
            'Could not request enrolment confirmation for application %s: %s',
            application.pk, exc,
        )


def registrar_email_for(application) -> str:
    """Where to send the enrolment verification for this application.

    Public because the preview endpoint has to answer the same question: a
    student is shown what their registrar will receive *before* submitting, and
    a preview addressed to nobody would be a preview of the wrong thing.

    The continuing-funding renewal does not ask for a registrar's address: the
    student gave one on the application that got them funded in the first place,
    and retyping it every semester is how a typo reaches an institution. So it
    falls back to the most recent earlier application by the same student that
    carries one.

    Without this the renewal would submit, promise the student that their
    registrar had been contacted, and silently contact nobody — tuition is
    funded against the registrar's figure, so nothing could ever be awarded
    for it.
    """
    own = str((application.answers or {}).get('registrar_email') or '').strip()
    if own:
        return own
    if not application.student_id:
        return ''

    earlier = (
        Application.objects
        .filter(student_id=application.student_id, submitted_at__isnull=False)
        # An unsaved draft — which is what the preview endpoint builds — has no
        # pk, and excluding pk=None would exclude nothing while looking as
        # though it excluded something.
        .exclude(pk=application.pk if application.pk else 0)
        .order_by('-submitted_at', '-id')
        .values_list('answers', flat=True)
    )
    for answers in earlier:
        carried = str((answers or {}).get('registrar_email') or '').strip()
        if carried:
            return carried
    return ''


def record_amendment(application, actor, note: str = '') -> ApplicationEvent:
    """The office correcting a filed application, on the applicant's behalf.

    Separate from `record` because it is not a transition: an amendment leaves
    the application exactly where it sits in the queue. Routing it through
    `record` would need AMENDED in RESULTING_STATUS, and every status a
    correction touched would be rewritten to whatever that mapping said — a
    decided application quietly reopened by a typo fix.

    It is still an event, so the history says who changed what and when, and the
    applicant is told. An office that can rewrite an application silently is an
    office nobody can appeal against.
    """
    event = ApplicationEvent.objects.create(
        application=application, action=Action.AMENDED, actor=actor, note=note,
    )

    from funding.services import messages
    messages.send_application_amended(application, actor=actor, note=note)
    return event


def status_is_consistent(application) -> bool:
    """Whether the stored status matches what the events say.

    A drift check: with `record` as the only writer this should never be false,
    so if it is, something bypassed the workflow.
    """
    events = list(application.events.order_by('occurred_at', 'id'))
    if not events:
        return application.status in (ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED)
    return application.status == derive_status(events)
