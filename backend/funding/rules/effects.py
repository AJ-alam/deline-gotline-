"""What a rule awards, once it applies.

Each effect kind is a named calculator, registered here and parameterised by
data on the rule. The set is closed and enumerable: an auditor can be shown
every way this system is capable of producing money, which a general expression
language would make impossible.

Every calculator returns an Outcome carrying the amount *and* the sentence
explaining it. An award nobody can explain is an award nobody can defend.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal('0.00')

_REGISTRY: dict[str, 'Effect'] = {}


class EffectError(Exception):
    """An effect is malformed or names an unknown calculator."""


@dataclass(frozen=True)
class Outcome:
    amount: Decimal
    explanation: str


@dataclass
class EvaluationContext:
    """Everything a calculator may read.

    `remaining_tuition` is shared and mutable across rules on purpose: tuition is
    allocated against one real bill, so no two streams can fund the same dollar.
    Every other input is read-only.
    """

    answers: dict
    facts: dict                 # derived values: months, load_key, dependants_key
    rates: object               # PolicyBook — .rate(section, key)
    remaining_tuition: Decimal = ZERO
    awarded_so_far: dict = None

    def __post_init__(self):
        if self.awarded_so_far is None:
            self.awarded_so_far = {}

    def resolve(self, template: str) -> str:
        """Fill a key template such as '{load}_{dependants}' or '{credential}'.

        Reads derived facts and the applicant's answers alike, so a rate key can
        be driven by an answer (the credential earned) as readily as by something
        computed (full-time or part-time).
        """
        values = dict(self.answers)
        values.update(self.facts)
        try:
            return template.format(**values)
        except KeyError as exc:
            raise EffectError(
                f'template {template!r} refers to {exc.args[0]!r}, '
                'which is neither an answer nor a derived fact'
            )


class Effect:
    """Base class. Subclasses register a `kind` and implement `apply`."""

    kind: str = ''
    required_params: tuple[str, ...] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.kind:
            if cls.kind in _REGISTRY:
                raise EffectError(f'duplicate effect kind {cls.kind!r}')
            _REGISTRY[cls.kind] = cls()

    def validate(self, params: dict) -> None:
        missing = [p for p in self.required_params if p not in params]
        if missing:
            raise EffectError(
                f'effect {self.kind!r} is missing {", ".join(sorted(missing))}'
            )

    def apply(self, params: dict, context: EvaluationContext) -> Outcome:
        raise NotImplementedError


class FlatRate(Effect):
    """A fixed configured amount. Bursaries, scholarships, book allowances."""

    kind = 'flat_rate'
    required_params = ('section', 'key')

    def apply(self, params, context):
        key = context.resolve(params['key'])
        amount = context.rates.rate(params['section'], key)
        return Outcome(amount, f'{params["section"]}:{key} = ${amount}')


class RatePerMonth(Effect):
    """A monthly rate for every month the student is in class."""

    kind = 'rate_per_month'
    required_params = ('section', 'key')

    def apply(self, params, context):
        key = context.resolve(params['key'])
        rate = context.rates.rate(params['section'], key)
        months = int(context.facts.get('months') or 0)
        return Outcome(
            rate * months,
            f'${rate}/month x {months} month(s)',
        )


class CappedTuition(Effect):
    """Pay tuition still owing, up to this stream's cap.

    Allocating against `remaining_tuition` is what stops two streams funding the
    same dollar, and stops anyone being funded above what they actually owe.
    """

    kind = 'capped_tuition'
    required_params = ('section', 'key')

    def apply(self, params, context):
        if context.remaining_tuition <= 0:
            return Outcome(ZERO, 'Tuition already fully funded')

        key = context.resolve(params['key'])
        cap = context.rates.rate(params['section'], key)
        granted = min(context.remaining_tuition, cap)
        context.remaining_tuition -= granted
        return Outcome(granted, f'Capped at ${cap}; ${granted} of the bill remained unfunded')


class PercentageRelief(Effect):
    """A share of a large bill, capped, and inclusive of what earlier rules paid.

    'Inclusive of' means the relief is the difference above amounts already
    awarded in `inclusive_of` categories, not a payment on top of them.
    """

    kind = 'percentage_relief'
    required_params = ('base_field', 'percent_section', 'percent_key',
                       'cap_section', 'cap_key')

    def apply(self, params, context):
        base = _decimal(context.answers.get(params['base_field']))
        if base <= 0 or context.remaining_tuition <= 0:
            return Outcome(ZERO, 'No unfunded balance to relieve')

        threshold_section = params.get('threshold_section')
        if threshold_section:
            threshold = context.rates.rate(threshold_section, params['threshold_key'])
            if threshold > 0 and base <= threshold:
                return Outcome(ZERO, f'${base} does not exceed the ${threshold} threshold')

        percent = context.rates.rate(params['percent_section'], params['percent_key'])
        cap = context.rates.rate(params['cap_section'], params['cap_key'])
        inclusive_total = min(base * percent / Decimal(100), cap)

        already = sum(
            (context.awarded_so_far.get(code, ZERO) for code in params.get('inclusive_of', ())),
            ZERO,
        )
        relief = max(ZERO, inclusive_total - already)
        relief = min(relief, context.remaining_tuition)
        context.remaining_tuition -= relief
        return Outcome(
            relief,
            f'{percent}% of ${base} capped at ${cap}, less ${already} already awarded',
        )


class Tiered(Effect):
    """Pick an award by which threshold a value reaches.

    Tiers are checked highest first, so a value meeting several gets the best one.
    Nothing is awarded when no tier is met — the previous implementation fell
    through to the cheapest tier, which silently underpaid.
    """

    kind = 'tiered'
    required_params = ('value_field', 'tiers')

    def validate(self, params):
        super().validate(params)
        for tier in params.get('tiers', ()):
            for key in ('at_least', 'section', 'key'):
                if key not in tier:
                    raise EffectError(f"tier is missing {key!r}")

    def apply(self, params, context):
        value = _decimal(context.answers.get(params['value_field']))
        tiers = sorted(params['tiers'], key=lambda t: Decimal(str(t['at_least'])), reverse=True)
        for tier in tiers:
            if value >= Decimal(str(tier['at_least'])):
                amount = context.rates.rate(tier['section'], tier['key'])
                return Outcome(amount, f'{value} reaches the {tier["at_least"]} tier')
        return Outcome(ZERO, f'{value} does not reach any tier')


class CappedRequest(Effect):
    """Pay what was asked for, up to a cap. Hardship and emergency awards."""

    kind = 'capped_request'
    required_params = ('request_field', 'section', 'key')

    def apply(self, params, context):
        requested = _decimal(context.answers.get(params['request_field']))
        if requested <= 0:
            return Outcome(ZERO, 'No amount requested')
        # Resolves templates like every other effect, so a cap can vary by an
        # answer — travel is capped differently depending on its purpose.
        key = context.resolve(params['key'])
        cap = context.rates.rate(params['section'], key)
        granted = min(requested, cap)
        return Outcome(granted, f'Requested ${requested}, capped at ${cap}')


def _decimal(value) -> Decimal:
    if value in (None, ''):
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace('$', '').replace(',', '').strip())
    except (ArithmeticError, ValueError):
        return ZERO


def get_effect(kind: str) -> Effect:
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise EffectError(
            f'unknown effect kind {kind!r}; available: {", ".join(sorted(_REGISTRY))}'
        )


def available_kinds() -> tuple[str, ...]:
    """Every way this system can produce money. Enumerable by design."""
    return tuple(sorted(_REGISTRY))


def validate_effect(effect: dict) -> None:
    if not isinstance(effect, dict) or 'kind' not in effect:
        raise EffectError("effect must be an object with a 'kind'")
    get_effect(effect['kind']).validate(effect)
