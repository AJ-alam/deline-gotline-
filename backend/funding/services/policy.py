"""Reading policy rates as of a date.

The previous implementation held the effective date and a cache in class
attributes on CalculationService. Two applications priced concurrently — normal
under Gunicorn threads and Fluid Compute — overwrote each other's date, so an
application submitted in 2024 could be priced with today's rates.

A PolicyBook is created per calculation and passed in. There is no shared state
to race, nothing to reset, and a test can construct one directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from funding.models import PolicyChange, PolicySetting


class MissingPolicyError(Exception):
    """A rate an award depends on is not configured.

    Never silently substitute zero: that produced $0.00 awards that were
    indistinguishable from a genuine decision, and payments were written for them.
    """

    def __init__(self, missing):
        self.missing = sorted(missing)
        super().__init__(
            'Missing policy settings: ' + ', '.join(self.missing)
        )


@dataclass
class PolicyBook:
    """Policy rates in force on `as_of`.

    §7.5: an application is priced with the rates that applied when it was
    submitted, so a later rate change cannot retroactively alter a decision.
    """

    as_of: date | None = None
    _cache: dict = field(default_factory=dict, repr=False)
    _missing: set = field(default_factory=set, repr=False)

    @classmethod
    def for_application(cls, application) -> PolicyBook:
        submitted = getattr(application, 'submitted_at', None)
        return cls(as_of=submitted.date() if submitted else None)

    @property
    def missing(self) -> list[str]:
        return sorted(self._missing)

    def rate(self, section: str, key: str) -> Decimal:
        """The value in force on `as_of`. Records, and returns 0, when absent."""
        cache_key = (section, key)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            setting = PolicySetting.objects.get(section=section, key=key)
        except PolicySetting.DoesNotExist:
            self._missing.add(f'{section}:{key}')
            return Decimal(0)

        if not setting.is_active:
            # A deactivated setting is a deliberate suspension, not a gap.
            self._cache[cache_key] = Decimal(0)
            return Decimal(0)

        value = setting.value
        if self.as_of is not None:
            # A change that takes effect after this application was submitted had
            # not happened yet — use the value it replaced.
            pending = (PolicyChange.objects
                       .filter(setting=setting, effective_date__gt=self.as_of)
                       .order_by('effective_date')
                       .first())
            if pending is not None:
                value = pending.previous_value

        self._cache[cache_key] = value
        return value

    def require_complete(self) -> None:
        """Raise if any rate consulted so far was absent."""
        if self._missing:
            raise MissingPolicyError(self._missing)
