"""Pricing an application against a rule set.

Produces a Decision: the amount, and the trace of every rule considered with the
reason it did or did not fire. The trace is the product, not a debugging aid —
a funding body has to explain any award years later, and 'the code said so' is
not an explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from funding.rules import conditions
from funding.rules.effects import EvaluationContext, Outcome, get_effect

ZERO = Decimal('0.00')


@dataclass(frozen=True)
class RuleOutcome:
    code: str
    description: str
    category: str
    applied: bool
    amount: Decimal
    explanation: str


@dataclass
class Decision:
    """The result of pricing one application against one rule set."""

    rule_set_name: str
    rule_set_version: int
    priced_on: date | None
    outcomes: list[RuleOutcome] = field(default_factory=list)
    missing_rates: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((o.amount for o in self.outcomes if o.applied), ZERO)

    @property
    def applied(self) -> list[RuleOutcome]:
        return [o for o in self.outcomes if o.applied and o.amount > 0]

    @property
    def is_complete(self) -> bool:
        """False when a rate a rule needed was not configured."""
        return not self.missing_rates

    def as_trace(self) -> dict:
        """A stored, human-readable record of how this amount was reached."""
        return {
            'rule_set': f'{self.rule_set_name} v{self.rule_set_version}',
            'priced_on': self.priced_on.isoformat() if self.priced_on else None,
            'total': str(self.total),
            'missing_rates': list(self.missing_rates),
            'rules': [
                {
                    'code': o.code,
                    'description': o.description,
                    'category': o.category,
                    'applied': o.applied,
                    'amount': str(o.amount),
                    'reason': o.explanation,
                }
                for o in self.outcomes
            ],
        }


def build_context(application, rates) -> EvaluationContext:
    """Flatten an application into the values rules read.

    Derived facts are computed once, here, rather than recomputed inside rules —
    so 'full-time' means the same thing to every rule that asks.
    """
    answers = dict(application.answers or {})

    load_key = 'fulltime' if answers.get('course_load') == 'full_time' else 'parttime'
    dependants_key = 'with_dependents' if _has_dependents(answers) else 'no_dependents'

    facts = {
        'load': load_key,
        'dependants': dependants_key,
        'months': _months(answers),
        'type': application.type,
        'stream': application.stream,
    }

    # Rules read derived facts alongside answers, so a condition can test
    # 'months' or 'stream' as naturally as an applicant's answer.
    lookup = dict(answers)
    lookup.update(facts)

    billed = _decimal(answers.get('confirmed_tuition') or answers.get('tuition_requested'))

    return EvaluationContext(
        answers=lookup,
        facts=facts,
        rates=rates,
        remaining_tuition=billed,
    )


def price(application, rule_set, rates) -> Decision:
    """Evaluate every rule in `rule_set` against `application`."""
    context = build_context(application, rates)
    decision = Decision(
        rule_set_name=rule_set.name,
        rule_set_version=rule_set.version,
        priced_on=(application.submitted_at.date() if application.submitted_at else None),
    )

    for rule in rule_set.rules.filter(is_active=True).order_by('order', 'id'):
        outcome = _apply_rule(rule, application, context)
        decision.outcomes.append(outcome)
        if outcome.applied and outcome.amount:
            context.awarded_so_far[rule.code] = outcome.amount

    decision.missing_rates = list(getattr(rates, 'missing', ()) or ())
    return decision


def _streams_for(application, context) -> set[str]:
    """Every pot this application may draw from.

    Not just `application.stream`. That column holds the *primary* stream —
    PSSSP where it applies, because it is the federal programme that funds
    tuition and a living allowance — and it decides which deadline the
    submission is measured against. But DGGR tops up rather than replaces: a
    student who qualifies for both was being funded from one of them, because
    the gate compared a rule against a single value.

    So the gate is asked against everything the applicant qualifies for, worked
    out from the same facts the sign-up screening used. A stream nobody
    qualifies for cannot appear here, and the awards a rule set produces are
    still entirely the rules' business — this only stops a rule being skipped
    for an applicant it was written for.
    """
    from funding.services import streams as streams_service

    if application.type in streams_service.ALWAYS_DGGR:
        # These are the government's own bursary funds whatever the applicant's
        # C-DFN status, and the guest path already forces them to DGGR.
        return {application.stream}

    qualifies = set(streams_service.eligible_streams(
        application.student, context.answers)) if application.student_id else set()

    # The stored stream always counts: an application the office moved into a
    # stream by hand — UCEPP is assigned, never derived — must still be priced
    # in it.
    qualifies.add(application.stream)

    declared = context.answers.get('funding_stream')
    if declared:
        qualifies.add(str(declared).lower())
    return qualifies


def _apply_rule(rule, application, context) -> RuleOutcome:
    def skipped(reason):
        return RuleOutcome(rule.code, rule.description, rule.category, False, ZERO, reason)

    if rule.applies_to_types and application.type not in rule.applies_to_types:
        return skipped(f'Does not apply to {application.get_type_display()}')

    if rule.applies_to_streams:
        if not _streams_for(application, context) & set(rule.applies_to_streams):
            return skipped('Does not apply to this funding stream')

    try:
        if not conditions.evaluate(rule.condition, context.answers):
            return skipped('Conditions not met')
    except conditions.ConditionError as exc:
        # A malformed rule must not silently award nothing, nor abort every other
        # rule. It is recorded as not applied, with the fault named.
        return skipped(f'Rule is malformed: {exc}')

    effect = get_effect(rule.effect['kind'])
    result: Outcome = effect.apply(rule.effect, context)
    return RuleOutcome(
        rule.code, rule.description, rule.category, True,
        result.amount, result.explanation,
    )


def _has_dependents(answers) -> bool:
    """Whether the dependants rate applies.

    Two schemas ask this two ways: the admission form asks a yes/no, the
    continuing-funding renewal asks how many. Asking both would let one answer
    contradict the other, so the count is the fallback and the explicit answer
    wins where a form provides it.
    """
    stated = answers.get('has_dependents')
    if isinstance(stated, bool):
        return stated
    if stated not in (None, ''):
        return str(stated).strip().lower() in ('true', 'yes', 'y', '1', 'on')

    count = answers.get('dependent_count')
    if count in (None, ''):
        return False
    try:
        return int(Decimal(str(count).strip())) > 0
    except (ArithmeticError, ValueError, TypeError):
        return False


def _months(answers) -> int:
    """Months of study, counting every month the student is in class.

    Sept 3 to Dec 20 is four monthly payments, not three: elapsed-month
    arithmetic drops the final partial month and underpays every semester.
    """
    def parse(value):
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None

    start, end = parse(answers.get('semester_start')), parse(answers.get('semester_end'))
    if not start or not end or end < start:
        return 4        # a standard semester
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _decimal(value) -> Decimal:
    if value in (None, ''):
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace('$', '').replace(',', '').strip())
    except (ArithmeticError, ValueError):
        return ZERO
