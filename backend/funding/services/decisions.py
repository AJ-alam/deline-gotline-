"""Pricing an application and recording the result.

Every pricing produces a new AwardDecision. Nothing is edited in place, so the
reasoning behind a decision already communicated to a student cannot vanish when
someone re-runs the calculation.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from funding.models import Award, AwardDecision, RuleSet
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
    """
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
        )

    application.awarded_total = decision.total
    application.save(update_fields=['awarded_total', 'updated_at'])

    logger.info(
        'Application %s priced at %s under %s v%s (%d line(s)).',
        application.pk, decision.total, rule_set.name, rule_set.version,
        len(decision_result.applied),
    )
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
