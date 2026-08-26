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
    AWARDED_STATUSES, Application, ApplicationEvent, ApplicationStatus,
    AuditEntry, Award,
)

logger = logging.getLogger(__name__)

COLUMNS = [
    'Reference', 'Student', 'Beneficiary number', 'Application',
    'Amount', 'Covers', 'Account holder', 'Transit', 'Institution',
    'Account number', 'Approved on',
]


class DispatchError(Exception):
    """The batch could not be sent."""


# An award may be paid once its application has been approved. Reaching finance
# does not un-approve it, and the award's own status is what records whether the
# money has actually gone out.
# The statuses whose award the office has committed to. Imported rather than
# restated: `Award.objects.awarded()` gates on the same set, and two lists that
# must agree are two lists that can disagree.
PAYABLE_STATUSES = AWARDED_STATUSES


def pending_awards():
    """Awards approved but not yet paid.

    Keyed on the award's status, because that is the thing that records whether
    money has left. The application status only decides whether it *may*.

    SENT_TO_FINANCE has to be included. Staff can record that transition by hand
    from the application screen — the detail view offers it as the next step on
    anything approved — and doing so left the award PENDING while removing it
    from every payment run, permanently and with nothing reporting it. On one
    database this had stranded $17,100 across three awards on a single
    application: approved, owed, and invisible to the people who pay it.
    """
    # `current()` is not a nicety here. A superseded decision's lines are still
    # PENDING — nothing pays them, so nothing ever changed their status — so an
    # application priced twice offered the same award twice and the money would
    # have gone out twice.
    return (Award.objects.awarded()
            .filter(status=Award.Status.PENDING)
            .select_related('application', 'application__student')
            .order_by('application__student__last_name', 'application_id', 'id'))


def _bank_account(student):
    return student.bank_accounts.filter(is_current=True).first() if student else None


def _release_requested(application) -> bool:
    """Whether the applicant asked for the money to go to someone else.

    The graduation award offers this as a tick. Nothing here can act on it —
    paying a third party is an authorisation the office grants, not a checkbox
    — so the only safe reading is that the award must not go out in the
    automatic file.

    A flag nothing reads is how `residency_flag` came to be a dashboard count
    that could only ever be zero. A flag read *only by a screen*, while the
    payment run pays the student's own account regardless, is worse: the
    applicant asked for the money to go elsewhere, was not refused, and it went
    where they said it should not.
    """
    return bool((application.answers or {}).get('release_to_other'))


def preview():
    """What would be sent, and what is blocking anything from being sent.

    Staff see the problems before they commit to a dispatch, rather than
    discovering afterwards that four students were missing from the file.
    """
    ready, blocked = [], []

    # An award whose decision link is missing would be filtered out by
    # `current()` and disappear from this screen entirely. Nothing creates one —
    # `record_decision` is the only writer and it always sets the decision — but
    # "nothing creates one" is not a reason to let money vanish quietly if one
    # ever exists. Reported, not dropped.
    for award in (Award.objects
                  .filter(decision__isnull=True, status=Award.Status.PENDING,
                          application__status__in=PAYABLE_STATUSES)
                  .select_related('application', 'application__student')):
        blocked.append({
            'award': award,
            'reason': ('This award is not attached to a pricing decision, so it '
                       'cannot be checked against one. Re-price the application.'),
        })

    for award in pending_awards():
        application = award.application
        student = application.student
        account = _bank_account(student)
        if _release_requested(application):
            recipient = (application.answers or {}).get('release_recipient')
            blocked.append({
                'award': award,
                'reason': (
                    'Payment was requested to another person'
                    + (f' ({recipient})' if recipient else '')
                    + '. Release of funds is arranged by the office, not by the '
                      'payment run.'
                ),
            })
        elif student is None:
            blocked.append({'award': award, 'reason': 'No student is attached to this application.'})
        elif not account:
            blocked.append({'award': award, 'reason': f'{student.full_name} has no bank account on file.'})
        else:
            ready.append({'award': award, 'account': account})
    return ready, blocked


def payment_batches(rows):
    """What finance is actually asked to do: pay one amount, once, per
    application.

    The file used to carry one row per award *line*. An application priced
    across two streams and two categories became four rows against one bank
    account, and the office asked for the opposite: tell finance the amount to
    pay, not the rules that produced it. The breakdown is not lost — it is on
    the application, on the approval letter and in the decision history, all of
    which are the office's own records rather than a payment instruction.

    Grouped by application, not by student. An award belongs to an application,
    and a student with two funded applications is owed two payments that must
    each be traceable to the decision behind it; merging them would produce a
    figure no single decision accounts for.

    `Covers` keeps the categories as a readable list, so a reconciler can still
    see what one payment is made up of without the file pretending to be a
    ledger.
    """
    batches: dict[int, dict] = {}
    for row in rows:
        award, account = row['award'], row['account']
        application = award.application
        batch = batches.get(application.pk)
        if batch is None:
            batch = batches[application.pk] = {
                'application': application,
                'student': application.student,
                'account': account,
                'awards': [],
                'amount': Decimal('0.00'),
                'categories': [],
            }
        batch['awards'].append(award)
        batch['amount'] += award.amount
        label = award.get_category_display()
        if label not in batch['categories']:
            batch['categories'].append(label)
    return list(batches.values())


def batch_reference(application, when) -> str:
    """One reference per payment, because there is now one payment.

    Derived from the application rather than from any single award line: the
    line references still exist on the awards themselves, but a lump sum that
    quoted one of them would name a part as though it were the whole.
    """
    return f'DGG-{when:%Y%m%d}-A{application.pk:06d}'


def build_csv(rows) -> str:
    """The file finance receives: one row per application, one amount to pay."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(COLUMNS)

    now = timezone.now()
    for batch in payment_batches(rows):
        application = batch['application']
        student = batch['student']
        account = batch['account']
        decided = application.events.filter(
            action=ApplicationEvent.Action.APPROVED).order_by('-occurred_at').first()

        writer.writerow([
            batch_reference(application, now),
            student.full_name,
            student.beneficiary_number,
            application.get_type_display(),
            f"{batch['amount']:.2f}",
            '; '.join(batch['categories']),
            account.account_holder,
            account.transit_number,
            account.institution_number,
            account.account_number,
            decided.occurred_at.date().isoformat() if decided else '',
        ])
    return output.getvalue()


@transaction.atomic
def dispatch(actor=None) -> dict:
    """Send every ready award, and mark it paid.

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

    now = timezone.now()

    # The reference finance reconciles against. `Award.reference` is unique and
    # was written by nothing, so every row in every file said 'AWD-<primary
    # key>' — the database's own counter, handed to a bank. Assigned before the
    # file is built so the file and the record carry the same string, and only
    # if the award has none: a reference that changes is not a reference.
    for row in ready:
        award = row['award']
        if not award.reference:
            award.reference = f'DGG-{now:%Y%m%d}-{award.pk:06d}'
    Award.objects.bulk_update([row['award'] for row in ready], ['reference'])

    csv_text = build_csv(ready)
    total = sum((row['award'].amount for row in ready), Decimal('0.00'))

    # PAID, not SENT_TO_FINANCE. Nothing anywhere wrote PAID, so
    # `Award.objects.paid()` — which exists precisely so that money paid under a
    # decision since superseded still counts as paid — could only ever return
    # nothing, and the student's dashboard reported $0.00 paid against an
    # awarded total in the millions. Dispatching the file is the act this
    # system can observe; the timestamps below still record when it went and
    # who sent it.
    Award.objects.filter(pk__in=ids).update(
        status=Award.Status.PAID,
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
