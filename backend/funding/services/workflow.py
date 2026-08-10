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
    ApplicationStatus.UNDER_REVIEW: {
        Action.INFO_REQUESTED, Action.FORWARDED, Action.DECLINED,
    },
    ApplicationStatus.INFO_REQUESTED: {Action.INFO_PROVIDED, Action.DECLINED},
    ApplicationStatus.AWAITING_DECISION: {
        Action.APPROVED, Action.DECLINED, Action.INFO_REQUESTED,
    },
    ApplicationStatus.APPROVED: {Action.SENT_TO_FINANCE},
    ApplicationStatus.DECLINED: set(),
    ApplicationStatus.SENT_TO_FINANCE: set(),
}


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


def can(application, action) -> bool:
    return action in ALLOWED_ACTIONS.get(application.status, set())


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

    event = ApplicationEvent.objects.create(
        application=locked, action=action, actor=actor, note=note,
    )

    locked.status = RESULTING_STATUS[action]
    locked.save(update_fields=['status', 'updated_at'])

    # Keep the caller's instance consistent with what was written.
    application.status = locked.status

    _announce(locked, action, note)
    return event


def _announce(application, action, note: str) -> None:
    """Tell the applicant what happened.

    Queued on commit inside the same transaction as the event, so a message can
    never describe a transition that did not persist.
    """
    from funding.services import messages

    if action == Action.SUBMITTED:
        messages.send_application_received(application)
        _request_enrolment_confirmation(application)
    elif action == Action.INFO_REQUESTED:
        messages.send_information_requested(application, note)
    elif action == Action.APPROVED:
        messages.send_decision(application, approved=True)
    elif action == Action.DECLINED:
        messages.send_decision(application, approved=False, reason=note)


# Types whose award depends on the institution confirming enrolment and the
# tuition actually billed.
NEEDS_ENROLMENT_CONFIRMATION = (
    ApplicationType.ADMISSION,
    ApplicationType.CONTINUING_FUNDING,
)


def _request_enrolment_confirmation(application) -> None:
    """Ask the institution to confirm, as soon as the application is submitted.

    Tuition is funded against the registrar's figure, so without this the
    application can never be priced for tuition at all. Failing to send must not
    fail the submission: the request can be reissued by staff.
    """
    from funding.services import verification

    if application.type not in NEEDS_ENROLMENT_CONFIRMATION:
        return
    registrar_email = (application.answers or {}).get('registrar_email')
    if not registrar_email:
        return

    try:
        verification.issue(application, registrar_email)
    except verification.VerificationError as exc:
        logger.warning(
            'Could not request enrolment confirmation for application %s: %s',
            application.pk, exc,
        )


def status_is_consistent(application) -> bool:
    """Whether the stored status matches what the events say.

    A drift check: with `record` as the only writer this should never be false,
    so if it is, something bypassed the workflow.
    """
    events = list(application.events.order_by('occurred_at', 'id'))
    if not events:
        return application.status in (ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED)
    return application.status == derive_status(events)
