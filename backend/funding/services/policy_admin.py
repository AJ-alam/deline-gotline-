"""Changing funding rates.

Rates are the most consequential configuration in the system: every award is
computed from them. Two things follow, and both are enforced here rather than
left to whoever writes the next view.

A change is never a silent overwrite. Each edit records what the value was, what
it became, who changed it and the date it takes effect, so an amount paid two
years ago can still be explained.

A change never reaches backwards. An application is priced with the rates in
force when it was submitted, so editing a rate today cannot alter a decision
already made — which is what makes an award defensible on appeal.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from funding.models import AuditEntry, PolicyChange, PolicySetting, RuleSet

logger = logging.getLogger(__name__)


def unit_for(key: str) -> str:
    """What a rate is measured in, from the key that names it.

    Every rate was seeded as '$' and the screen formatted all of them as money,
    so an 80% achievement threshold was published to administrators as
    '$80.00' — on the one screen where they change what students are paid. The
    key already says which kind it is; nothing else needs to be decided.
    """
    return '%' if 'percent' in key else '$'


class PolicyEditError(Exception):
    """The change was refused."""


def _as_amount(raw) -> Decimal:
    try:
        value = Decimal(str(raw).replace('$', '').replace(',', '').strip())
    except (InvalidOperation, ArithmeticError, AttributeError, TypeError):
        raise PolicyEditError('The value must be an amount.')
    if value < 0:
        raise PolicyEditError('A rate cannot be negative.')
    return value.quantize(Decimal('0.01'))


@transaction.atomic
def change_rate(setting: PolicySetting, new_value, actor=None,
                effective_from: date | None = None) -> PolicyChange:
    """Change one rate, recording what it was and when the change applies.

    `effective_from` defaults to today. A future date lets an office schedule a
    rate change in advance without it taking effect early; PolicyBook reads the
    previous value for anything submitted before that date.
    """
    amount = _as_amount(new_value)
    effective_from = effective_from or timezone.now().date()

    locked = PolicySetting.objects.select_for_update().get(pk=setting.pk)
    previous = locked.value
    if previous == amount:
        raise PolicyEditError('That is already the value.')

    locked.value = amount
    locked.save(update_fields=['value', 'updated_at'])

    change = PolicyChange.objects.create(
        setting=locked,
        previous_value=previous,
        new_value=amount,
        effective_date=effective_from,
        changed_by=actor,
    )
    AuditEntry.objects.create(
        actor=actor,
        actor_role=getattr(actor, 'role', ''),
        action='policy.rate_changed',
        detail=(
            f'{locked.section}:{locked.key} {previous} → {amount}, '
            f'effective {effective_from}'
        ),
    )
    logger.info(
        'Rate %s:%s changed %s → %s effective %s by %s',
        locked.section, locked.key, previous, amount, effective_from,
        getattr(actor, 'email', 'system'),
    )
    return change


@transaction.atomic
def set_active(setting: PolicySetting, is_active: bool, actor=None) -> PolicySetting:
    """Suspend or restore a rate.

    A deactivated rate reads as zero rather than as missing configuration, which
    is a deliberate suspension of that award rather than a broken setup.
    """
    locked = PolicySetting.objects.select_for_update().get(pk=setting.pk)
    if locked.is_active == is_active:
        return locked

    locked.is_active = is_active
    locked.save(update_fields=['is_active', 'updated_at'])
    AuditEntry.objects.create(
        actor=actor,
        actor_role=getattr(actor, 'role', ''),
        action='policy.rate_suspended' if not is_active else 'policy.rate_restored',
        detail=f'{locked.section}:{locked.key}',
    )
    return locked


def grouped_settings():
    """Every rate, grouped by the section an administrator thinks in."""
    grouped: dict[str, list[PolicySetting]] = {}
    for setting in PolicySetting.objects.order_by('section', 'key'):
        grouped.setdefault(setting.section, []).append(setting)
    return grouped


def history_for(setting: PolicySetting):
    return setting.changes.select_related('changed_by').order_by('-effective_date', '-changed_at')


@transaction.atomic
def publish_rule_set(rule_set: RuleSet, actor=None, effective_from: date | None = None) -> RuleSet:
    """Put a draft rule set into force, closing the one it replaces.

    Exactly one set is in force at a time; the previous one keeps the period it
    governed so decisions made under it can still be replayed.
    """
    if rule_set.status == RuleSet.Status.PUBLISHED:
        raise PolicyEditError('That rule set is already published.')
    if rule_set.status == RuleSet.Status.SUPERSEDED:
        raise PolicyEditError('A superseded rule set cannot be republished.')

    effective_from = effective_from or timezone.now().date()

    (RuleSet.objects
     .filter(name=rule_set.name, status=RuleSet.Status.PUBLISHED, effective_to__isnull=True)
     .exclude(pk=rule_set.pk)
     .update(status=RuleSet.Status.SUPERSEDED, effective_to=effective_from))

    rule_set.status = RuleSet.Status.PUBLISHED
    rule_set.effective_from = effective_from
    rule_set.published_at = timezone.now()
    rule_set.save(update_fields=['status', 'effective_from', 'published_at'])

    AuditEntry.objects.create(
        actor=actor,
        actor_role=getattr(actor, 'role', ''),
        action='policy.rule_set_published',
        detail=f'{rule_set.name} v{rule_set.version}, effective {effective_from}',
    )
    return rule_set
