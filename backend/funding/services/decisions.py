"""Pricing an application and recording the result.

Every pricing produces a new AwardDecision. Nothing is edited in place, so the
reasoning behind a decision already communicated to a student cannot vanish when
someone re-runs the calculation.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from funding.models import AWARDED_STATUSES, Award, AwardDecision, RuleSet
from funding.rules.engine import price
from funding.services.policy import PolicyBook

logger = logging.getLogger(__name__)


class NoRuleSetInForce(Exception):
    """No published rule set covered the date this application was submitted."""


class IncompletePolicyError(Exception):
    """A rate a rule needed is not configured.

    An award computed from absent configuration reads as a real decision of
    $0.00, and payment lines get written for it.
    """

    def __init__(self, missing):
        self.missing = sorted(missing)
        super().__init__('Missing policy rates: ' + ', '.join(self.missing))


def _refuse_if_paid(application) -> None:
    """Stop before touching an award any of which has been paid."""
    if application.awards.filter(status=Award.Status.PAID).exists():
        raise AlreadyPaidError(
            'Part of this award has already been paid. It cannot be priced or '
            'edited again after money has gone out.')


def preview(application, rule_set=None):
    """Price without recording anything.

    Never raises for incomplete policy — staff need to see the breakdown *and*
    what is missing from it, rather than an error page.
    """
    rule_set = rule_set or _rule_set_for(application)
    return price(application, rule_set, PolicyBook.for_application(application))


@transaction.atomic
def record_decision(application, actor=None, rule_set=None, allow_incomplete=False):
    """Price the application and store the result as the current decision.

    The previous decision is superseded, not deleted.

    Refused before the institution has confirmed the enrolment, on the types
    whose award depends on it. `preview` is deliberately not — staff need to see
    a working before they chase a registrar. The difference is that recording
    writes a figure onto the application, and tuition is funded against the
    registrar's number: priced without it, the tuition rules award nothing, so
    the total is not a small error but a wrong answer that reads like a real
    one. The same guard already stops the application being forwarded or
    approved; it was missing from the one step that produces the amount.
    """
    from funding.services import workflow

    _refuse_if_paid(application)
    if not workflow.enrolment_is_confirmed(
            application, workflow.Action.APPROVED):
        raise workflow.EnrolmentNotConfirmed(application)

    rule_set = rule_set or _rule_set_for(application)
    decision_result = price(application, rule_set, PolicyBook.for_application(application))

    if not decision_result.is_complete and not allow_incomplete:
        raise IncompletePolicyError(decision_result.missing_rates)

    previous = (AwardDecision.objects
                .select_for_update()
                .filter(application=application, is_current=True)
                .first())
    if previous is not None:
        # Clear the flag before inserting the replacement: the unique constraint
        # allows only one current decision per application.
        previous.is_current = False
        previous.save(update_fields=['is_current'])

        # A superseded decision's unpaid lines are not owed any more, and they
        # said PENDING forever — a status that means "waiting to be paid" on
        # money nothing will ever pay. Every reader was already scoped by
        # `current()`, so this changes no total; it stops the table describing
        # $1.2m of cancelled awards as outstanding. Lines already PAID are left
        # exactly as they are: money that left the bank under a decision since
        # superseded still left the bank.
        previous.lines.filter(status=Award.Status.PENDING).update(
            status=Award.Status.CANCELLED)

    decision = AwardDecision.objects.create(
        application=application,
        rule_set=rule_set,
        rule_set_version=rule_set.version,
        total=decision_result.total,
        inputs=dict(application.answers or {}),
        trace=decision_result.as_trace(),
        is_complete=decision_result.is_complete,
        priced_on=decision_result.priced_on,
        created_by=actor,
    )

    if previous is not None:
        previous.superseded_by = decision
        previous.save(update_fields=['superseded_by'])

    for outcome in decision_result.applied:
        Award.objects.create(
            application=application,
            decision=decision,
            rule_code=outcome.code,
            category=outcome.category,
            amount=outcome.amount,
            detail=outcome.detail,
        )

    application.awarded_total = decision.total
    application.save(update_fields=['awarded_total', 'updated_at'])

    # The approval letter normally rides along with the approval email. It
    # cannot when the office approves *before* pricing — there was no award to
    # describe at that moment — and nothing in the workflow requires the two in
    # either order. Without this the student got no letter at all, silently, on
    # a path the office is free to take. Sent here too when an approved
    # application is re-priced, because the letter they are already holding
    # names figures that have since been superseded.
    if application.status in AWARDED_STATUSES:
        from funding.services import messages
        messages.send_approval_letter(application)

    logger.info(
        'Application %s priced at %s under %s v%s (%d line(s)).',
        application.pk, decision.total, rule_set.name, rule_set.version,
        len(decision_result.applied),
    )
    return decision


class AwardEditError(Exception):
    """The breakdown cannot be set to this."""


class AlreadyPaidError(Exception):
    """Money has gone out under this application; its award is settled.

    Re-pricing supersedes the current decision and writes a fresh set of lines,
    and a fresh line is PENDING. On an application the payment run has already
    dispatched, that puts money back in the run: `finance.pending_awards()`
    selects PENDING lines on the current decision of an application in a payable
    status, and `sent_to_finance` is one. Re-pricing a dispatched award offered
    every dollar of it for payment a second time — $14,850 of it, on the
    application this was found against.

    `record_manual_decision` has always refused this. `record_decision` — the
    path the "Record award" button takes — did not, and it is the one anybody
    would press.
    """


@transaction.atomic
def record_manual_decision(application, lines, actor=None, note: str = ''):
    """The office setting the breakdown by hand.

    The rules produce an award for the ordinary case. They cannot know that a
    student's institution charges a fee nothing has a rate for, or that the
    office agreed something at the counter — and until this existed the only
    ways to express that were to edit a policy rate, which changes what
    *everyone* is paid, or to pay the wrong amount.

    Recorded as a decision like any other: it supersedes rather than overwrites,
    it carries a trace saying who set it and why, and an appeal argues against
    it the same way. What it does not do is pretend to be the rules — every line
    says it was entered by a person.

    Re-pricing from the rules replaces it, which is why the screen warns before
    doing so. Lines already paid are never touched.
    """
    _refuse_if_paid(application)

    cleaned = []
    for line in lines:
        category = str(line.get('category') or '').strip()
        if category not in Award.Category.values:
            raise AwardEditError(f'{category or "(blank)"} is not an award category.')
        try:
            amount = Decimal(str(line.get('amount')).replace('$', '').replace(',', '').strip())
        except (InvalidOperation, ArithmeticError, AttributeError, TypeError):
            raise AwardEditError(f'{line.get("amount")!r} is not an amount.')
        if amount < 0:
            raise AwardEditError('An award line cannot be negative.')
        cleaned.append({
            'category': category,
            'amount': amount.quantize(Decimal('0.01')),
            'description': str(line.get('description') or '').strip()
                           or Award.Category(category).label,
        })

    if not cleaned:
        raise AwardEditError('An award needs at least one line.')

    rule_set = _rule_set_for(application)
    total = sum((line['amount'] for line in cleaned), Decimal('0.00'))
    who = getattr(actor, 'full_name', '') or 'the office'

    previous = (AwardDecision.objects.select_for_update()
                .filter(application=application, is_current=True).first())
    if previous is not None:
        previous.is_current = False
        previous.save(update_fields=['is_current'])
        previous.lines.filter(status=Award.Status.PENDING).update(
            status=Award.Status.CANCELLED)

    decision = AwardDecision.objects.create(
        application=application,
        rule_set=rule_set,
        rule_set_version=rule_set.version,
        total=total,
        inputs=dict(application.answers or {}),
        trace={
            'rule_set': f'Set by hand ({rule_set.name} v{rule_set.version} in force)',
            'priced_on': timezone.now().date().isoformat(),
            'total': str(total),
            'missing_rates': [],
            'set_by_hand': True,
            'set_by': who,
            'note': note,
            'rules': [
                {
                    'code': f'manual_{index + 1}',
                    'description': line['description'],
                    'category': line['category'],
                    'applied': True,
                    'amount': str(line['amount']),
                    'reason': f'Entered by {who}' + (f' — {note}' if note else ''),
                }
                for index, line in enumerate(cleaned)
            ],
        },
        is_complete=True,
        priced_on=timezone.now().date(),
        created_by=actor,
    )

    if previous is not None:
        previous.superseded_by = decision
        previous.save(update_fields=['superseded_by'])

    for index, line in enumerate(cleaned):
        Award.objects.create(
            application=application, decision=decision,
            rule_code=f'manual_{index + 1}',
            category=line['category'], amount=line['amount'],
        )

    application.awarded_total = total
    application.save(update_fields=['awarded_total', 'updated_at'])

    # Same reason as the priced path: the office setting the breakdown by hand
    # on an approved application changes what the student was told they are
    # getting, and the letter they are holding names the old figures.
    if application.status in AWARDED_STATUSES:
        from funding.services import messages
        messages.send_approval_letter(application)

    logger.info('Application %s awarded %s by hand by %s (%d line(s)).',
                application.pk, total, who, len(cleaned))
    return decision


def current_decision(application):
    return application.decisions.filter(is_current=True).first()


def decision_history(application):
    """Every pricing, newest first. The record an appeal is argued from."""
    return application.decisions.all()


def _rule_set_for(application) -> RuleSet:
    """The rule set that was in force when the application was submitted.

    Not the newest one: a policy change must not retroactively reprice a
    decision that was already made and communicated.
    """
    when = (application.submitted_at.date()
            if application.submitted_at else timezone.now().date())
    rule_set = RuleSet.in_force_on(when)
    if rule_set is None:
        raise NoRuleSetInForce(
            f'No published rule set was in force on {when}.'
        )
    return rule_set
