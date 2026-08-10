"""Sending approved awards to be paid.

The last step in the money path, and the one where a mistake reaches someone's
bank account. Two rules follow from that.

An award is dispatched once. Every line carries a dispatch stamp, and the batch
is built from a locked selection, so the same award cannot be sent twice by two
people pressing the button at the same moment.

The export carries the banking details in force when the award was approved,
taken from the student's current account record — and a student with no account
on file is reported rather than silently dropped, because a missing row in a
finance file is a person who does not get paid.
"""

from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, AuditEntry, Award,
)

logger = logging.getLogger(__name__)

COLUMNS = [
    'Reference', 'Student', 'Beneficiary number', 'Application',
    'Award', 'Amount', 'Account holder', 'Transit', 'Institution',
    'Account number', 'Approved on',
]


class DispatchError(Exception):
    """The batch could not be sent."""


def pending_awards():
    """Awards approved but not yet sent to finance."""
    return (Award.objects
            .filter(status=Award.Status.PENDING,
                    application__status=ApplicationStatus.APPROVED)
            .select_related('application', 'application__student')
            .order_by('application__student__last_name', 'application_id', 'id'))


def _bank_account(student):
    return student.bank_accounts.filter(is_current=True).first() if student else None


def preview():
    """What would be sent, and what is blocking anything from being sent.

    Staff see the problems before they commit to a dispatch, rather than
    discovering afterwards that four students were missing from the file.
    """
    ready, blocked = [], []
    for award in pending_awards():
        student = award.application.student
        account = _bank_account(student)
        if student is None:
            blocked.append({'award': award, 'reason': 'No student is attached to this application.'})
        elif not account:
            blocked.append({'award': award, 'reason': f'{student.full_name} has no bank account on file.'})
        else:
            ready.append({'award': award, 'account': account})
    return ready, blocked


def build_csv(rows) -> str:
    """The file finance receives.

    One row per award line rather than one per student: finance reconciles
    against the award categories, and a single lump sum cannot be traced back to
    the rule that produced it.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(COLUMNS)

    for row in rows:
        award, account = row['award'], row['account']
        application = award.application
        student = application.student
        decided = application.events.filter(
            action=ApplicationEvent.Action.APPROVED).order_by('-occurred_at').first()

        writer.writerow([
            award.reference or f'AWD-{award.pk}',
            student.full_name,
            student.beneficiary_number,
            application.get_type_display(),
            award.get_category_display(),
            f'{award.amount:.2f}',
            account.account_holder,
            account.transit_number,
            account.institution_number,
            account.account_number,
            decided.occurred_at.date().isoformat() if decided else '',
        ])
    return output.getvalue()


@transaction.atomic
def dispatch(actor=None) -> dict:
    """Send every ready award, and mark it sent.

    Returns the file and a summary. Awards that cannot be paid are left pending
    and reported, never quietly excluded.
    """
    ready, blocked = preview()
    if not ready:
        raise DispatchError(
            'There is nothing ready to send.'
            + (f' {len(blocked)} award(s) are blocked.' if blocked else '')
        )

    # Lock the exact rows being sent, so a second dispatch running at the same
    # moment cannot pick up the same awards.
    ids = [row['award'].pk for row in ready]
    locked = list(Award.objects.select_for_update()
                  .filter(pk__in=ids, status=Award.Status.PENDING))
    if len(locked) != len(ids):
        raise DispatchError('Some awards were dispatched by someone else. Try again.')

    csv_text = build_csv(ready)
    now = timezone.now()
    total = sum((row['award'].amount for row in ready), Decimal('0.00'))

    Award.objects.filter(pk__in=ids).update(
        status=Award.Status.SENT_TO_FINANCE,
        sent_to_finance_at=now,
        sent_to_finance_by=actor,
    )

    # The application follows its awards, through the workflow rather than by
    # assignment, so the transition is recorded like any other.
    from funding.services import workflow
    for application in Application.objects.filter(
            pk__in={row['award'].application_id for row in ready}).distinct():
        if application.status == ApplicationStatus.APPROVED:
            try:
                workflow.record(application, ApplicationEvent.Action.SENT_TO_FINANCE,
                                actor=actor)
            except workflow.InvalidTransition as exc:
                logger.warning('Application %s not moved: %s', application.pk, exc)

    AuditEntry.objects.create(
        actor=actor,
        actor_role=getattr(actor, 'role', ''),
        action='finance.dispatched',
        detail=f'{len(ready)} award(s) totalling {total} sent to finance',
    )
    logger.info('Dispatched %d award(s) totalling %s to finance.', len(ready), total)

    return {
        'csv': csv_text,
        'count': len(ready),
        'total': total,
        'blocked': blocked,
        'filename': f'dgg-awards-{now.date().isoformat()}.csv',
    }
