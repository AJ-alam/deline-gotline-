"""Where an award is actually paid to.

The forms ask for bank details and always have. What they did with them was the
problem: the four answers were written into `Application.answers`, which the
detail endpoint returns whole, the printable form renders and the enrolment
verification copies from — so an account number reached every staff role and,
on the forms that generate one, an institution's mailbox.

Nothing read them either. `finance.preview` pays from the student's
`BankAccount` record, and the only thing that ever created one was the demo
seed. A student who filled the section in was still reported as having no
account on file, and their award was held.

So the answers are split off at validation and land here instead:

  signed in   the student's current BankAccount, which is what finance reads.
  guest       encrypted against the application, because there is no account to
              attach it to yet. `promote` moves it across when the office links
              the application to a student.
"""

from __future__ import annotations

import json
import logging

from accounts.models import BankAccount
from django.utils import timezone

from funding.models import ApplicantIdentifier
from funding.services import identifiers

logger = logging.getLogger(__name__)

# The shared block from schemas.common.banking, in the order a form asks it.
KEYS = ('account_holder', 'transit_number', 'institution_number', 'account_number')

# Enough to pay someone. Anything less is a half-filled section, which is worse
# than an empty one: it looks like an account on file and cannot be paid.
REQUIRED = ('account_holder', 'transit_number', 'institution_number', 'account_number')


def values_from(answers: dict) -> dict:
    """Just the banking answers, as strings, dropping blanks."""
    return {key: str(answers[key]).strip()
            for key in KEYS
            if answers.get(key) not in (None, '')}


def is_complete(values: dict) -> bool:
    return all(values.get(key) for key in REQUIRED)


# What the forms have always told people to enter — `schemas.common.banking`
# says "Five digits", "Three digits", "Seven to twelve digits" in its help text.
# Nothing checked it, so the help text was a suggestion.
SHAPES = {
    'transit_number': (5, 5, 'The transit number is five digits.'),
    'institution_number': (3, 3, 'The institution number is three digits.'),
    'account_number': (7, 12, 'The account number is seven to twelve digits.'),
}


def unpayable_reasons(values: dict) -> dict[str, str]:
    """Why these details could not be paid, keyed by field. Empty when they can.

    One definition, two callers with deliberately different manners. The profile
    screen refuses and shows these messages: it exists to get the account right,
    and a student staring at the form is the cheapest moment to correct a
    transposed digit. `record()` below only logs them, because a submitted
    application must never be lost to a bad account number — an award that
    cannot be paid is already reported by `finance.preview`, which is where a
    missing or wrong account belongs.
    """
    problems: dict[str, str] = {}

    for key in REQUIRED:
        if not str(values.get(key) or '').strip():
            problems[key] = 'This is needed before you can be paid.'

    for key, (low, high, message) in SHAPES.items():
        digits = str(values.get(key) or '').strip()
        if not digits or key in problems:
            continue
        if not digits.isdigit() or not (low <= len(digits) <= high):
            problems[key] = message

    return problems


def record(application, answers: dict) -> None:
    """Route the banking answers off an application being created.

    Never raises: a bad or partial account must not lose a submitted
    application. An award that cannot be paid is already reported by
    `finance.preview`, which is where a missing account belongs.
    """
    values = values_from(answers)
    if not values:
        return

    if not is_complete(values):
        logger.warning(
            'Application %s carried a partial bank account; not recorded.',
            application.pk,
        )
        return

    # Recorded anyway. A submitted application must not be lost to a transposed
    # digit, and `finance.preview` is where an account that cannot be paid is
    # reported to the people who pay it.
    doubts = unpayable_reasons(values)
    if doubts:
        logger.warning(
            'Application %s carried bank details that may not be payable: %s',
            application.pk, '; '.join(sorted(doubts.values())),
        )

    if application.student_id:
        set_current(application.student, values)
    else:
        _hold_for_later(application, values)


def set_current(student, values: dict) -> BankAccount:
    """Make these the account this student is paid to.

    The previous one is retired rather than edited: a payment already sent has
    to remain traceable to the details that were in force when it went out.
    Unchanged details are left alone, so resubmitting the same answers next
    semester does not churn the record.
    """
    current = student.bank_accounts.filter(is_current=True).first()
    if current and all(getattr(current, key) == values[key] for key in KEYS):
        return current

    if current:
        current.is_current = False
        current.retired_at = timezone.now()
        current.save(update_fields=['is_current', 'retired_at'])

    return BankAccount.objects.create(user=student, **values)


def _hold_for_later(application, values: dict) -> None:
    """A guest applied with no account behind them.

    Encrypted against the application, the same way a SIN is, rather than left
    in `answers`. A guest application cannot be paid until the office attaches
    it to a student anyway — `finance.preview` reports it as having nobody
    attached — so this only has to survive until that happens.
    """
    identifiers.store(
        application,
        ApplicantIdentifier.Kind.BANK_ACCOUNT,
        json.dumps(values, sort_keys=True),
        # What a screen shows. The end of the JSON would be punctuation.
        last_three=values['account_number'][-3:],
    )


def promote(application, student) -> BankAccount | None:
    """Give a newly attached guest application's details to its owner.

    Called when a guest application is linked to an account. Without this the
    details the applicant typed stay encrypted against an application nobody
    reads them from, and the student is reported to finance as having no
    account — having already provided one.

    An account the student has already set up wins: they entered it against
    their own identity, and a guest form filled in months earlier should not
    silently redirect their money.
    """
    if student.bank_accounts.filter(is_current=True).exists():
        return None

    stored = ApplicantIdentifier.objects.filter(
        application=application, kind=ApplicantIdentifier.Kind.BANK_ACCOUNT).first()
    if stored is None:
        return None

    try:
        values = json.loads(identifiers.decrypt(stored))
    except (identifiers.IdentifierError, ValueError):
        logger.warning('Could not read held bank details for application %s.',
                       application.pk)
        return None

    if not is_complete(values):
        return None
    return set_current(student, {key: values[key] for key in KEYS})
