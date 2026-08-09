"""Deciding whether a rule applies.

A condition is data:

    {"field": "course_load", "op": "eq", "value": "full_time"}
    {"all": [ {...}, {...} ]}
    {"any": [ {...}, {...} ]}
    {"not": {...}}

Deliberately not a general expression language. Everything expressible here can
be listed, reviewed and explained to an auditor; anything that cannot be
expressed belongs in a named effect calculator, written in Python and tested.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


class ConditionError(Exception):
    """A condition is malformed. Raised when the rule is evaluated or validated."""


COMBINATORS = ('all', 'any', 'not')

OPERATORS = (
    'eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in', 'not_in',
    'is_set', 'is_empty', 'contains',
)


def _as_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    try:
        return Decimal(str(value).replace('$', '').replace(',', '').strip())
    except (InvalidOperation, ArithmeticError, AttributeError, TypeError):
        return None


def _compare(op, actual, expected):
    # Checked first: an unknown operator used to fall through to the numeric
    # branch and quietly return False, so a typo in a rule read as 'did not
    # apply' instead of 'this rule is broken'.
    if op not in OPERATORS:
        raise ConditionError(f'unknown operator {op!r}')

    if op == 'is_set':
        return actual not in (None, '', [], {})
    if op == 'is_empty':
        return actual in (None, '', [], {})

    if op == 'eq':
        return _loose_equal(actual, expected)
    if op == 'ne':
        return not _loose_equal(actual, expected)

    if op == 'in':
        return any(_loose_equal(actual, item) for item in expected or ())
    if op == 'not_in':
        return not any(_loose_equal(actual, item) for item in expected or ())

    if op == 'contains':
        return expected is not None and str(expected).lower() in str(actual or '').lower()

    left, right = _as_number(actual), _as_number(expected)
    if left is None or right is None:
        # An unorderable comparison is false, never an error: a missing answer
        # should not abort pricing an application, it should fail to match.
        return False
    if op == 'lt':
        return left < right
    if op == 'lte':
        return left <= right
    if op == 'gt':
        return left > right
    return left >= right


def _loose_equal(actual, expected):
    if isinstance(actual, bool) or isinstance(expected, bool):
        return bool(actual) == bool(expected)
    if actual is None or expected is None:
        return actual is expected
    left, right = _as_number(actual), _as_number(expected)
    if left is not None and right is not None:
        return left == right
    return str(actual).strip().lower() == str(expected).strip().lower()


def evaluate(condition: dict | None, context: dict) -> bool:
    """Whether `condition` holds for `context`. An empty condition always holds."""
    if not condition:
        return True
    if not isinstance(condition, dict):
        raise ConditionError(f'condition must be an object, got {type(condition).__name__}')

    if 'all' in condition:
        return all(evaluate(part, context) for part in condition['all'])
    if 'any' in condition:
        return any(evaluate(part, context) for part in condition['any'])
    if 'not' in condition:
        return not evaluate(condition['not'], context)

    try:
        field = condition['field']
        op = condition['op']
    except KeyError as exc:
        raise ConditionError(f'condition is missing {exc.args[0]!r}')

    return _compare(op, context.get(field), condition.get('value'))


def validate(condition: dict | None) -> None:
    """Raise ConditionError if a condition is malformed.

    Called when a rule is saved, so a broken rule is rejected by the person
    writing it rather than discovered while pricing a student's application.
    """
    if not condition:
        return
    if not isinstance(condition, dict):
        raise ConditionError('condition must be an object')

    for combinator in ('all', 'any'):
        if combinator in condition:
            parts = condition[combinator]
            if not isinstance(parts, list) or not parts:
                raise ConditionError(f'{combinator!r} must be a non-empty list')
            for part in parts:
                validate(part)
            return

    if 'not' in condition:
        validate(condition['not'])
        return

    if 'field' not in condition:
        raise ConditionError("condition needs a 'field'")
    op = condition.get('op')
    if op not in OPERATORS:
        raise ConditionError(
            f'unknown operator {op!r}; expected one of {", ".join(OPERATORS)}'
        )
    if op in ('in', 'not_in') and not isinstance(condition.get('value'), list):
        raise ConditionError(f'operator {op!r} needs a list value')
    if op not in ('is_set', 'is_empty') and 'value' not in condition:
        raise ConditionError(f'operator {op!r} needs a value')


def referenced_fields(condition: dict | None) -> set[str]:
    """Every context field a condition reads. Used to check rules against schemas."""
    if not condition:
        return set()
    for combinator in ('all', 'any'):
        if combinator in condition:
            found = set()
            for part in condition[combinator]:
                found |= referenced_fields(part)
            return found
    if 'not' in condition:
        return referenced_fields(condition['not'])
    return {condition['field']} if 'field' in condition else set()
