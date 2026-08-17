"""What a form opens with, for a student who has applied before.

The continuing-funding renewal exists to be *confirmed* rather than filled in:
someone already receiving funding has given all of this before, and asking again
every semester is how an institution name drifts one character away from the one
the registrar's office actually answers to.

Only ever a starting point. Every value stays editable, and the server validates
what comes back exactly as it would if it had been typed — a pre-filled answer
carries no more authority than a typed one.
"""

from __future__ import annotations

from funding.models import Application

# How many earlier applications to look through. A student who changed
# institutions two applications ago should not have the older name resurface,
# but one gap in the most recent form should not empty the field either.
DEPTH = 5

# Facts about the person, held on the account rather than in any application.
#
# Two forms ask for the name in two fields rather than one — `admission`, which
# is the first form anybody files, and `travel`. Only `full_name` was mapped
# here, and a key the schema does not define is skipped in silence, so on
# exactly those two forms the name pre-filled as nothing and the student typed
# what the portal already knew. Nothing failed and nothing said so.
FROM_ACCOUNT = {
    'full_name': lambda user: user.full_name,
    'first_name': lambda user: user.first_name,
    'last_name': lambda user: user.last_name,
    'email': lambda user: user.email,
    'beneficiary_number': lambda user: user.beneficiary_number,
    'treaty_number': lambda user: user.treaty_number,
    'date_of_birth': lambda user: user.date_of_birth,
    'phone': lambda user: user.phone,
    'street_address': lambda user: user.street_address,
    'city': lambda user: user.city,
    'province': lambda user: user.province,
    'postal_code': lambda user: user.postal_code,
}

# Facts about their studies, carried from the last application that stated one.
#
# Deliberately absent: `semester` and `receives_sfa`, which are about this term
# and this term only; the documents, which must be the current semester's; and
# the declaration and signature, which are the act of applying itself. Filling
# any of those in would be answering on the student's behalf.
FROM_EARLIER_APPLICATIONS = (
    'institution_name',
    'program',
    'course_load',
    'dependent_count',
    'credential_level',
    'student_number',
    'phone',
)


def for_schema(user, schema) -> dict:
    """Answers to open `schema` with for `user`. Never guesses a key the schema
    does not define — an unknown answer is refused at validation, so a prefill
    that invented one would make the form unsubmittable."""
    if not getattr(user, 'is_authenticated', False):
        return {}

    keys = set(schema.keys)
    filled: dict = {}

    for key, read in FROM_ACCOUNT.items():
        if key not in keys:
            continue
        value = read(user)
        if value:
            filled[key] = value

    wanted = [key for key in FROM_EARLIER_APPLICATIONS if key in keys]
    if not wanted:
        return filled

    # Submitted applications only. A half-finished draft is not a statement
    # about anything, and ordering by a null submitted_at is not an order.
    earlier = (
        Application.objects
        .filter(student=user, submitted_at__isnull=False)
        .order_by('-submitted_at', '-id')
        .values_list('answers', flat=True)[:DEPTH]
    )
    for answers in earlier:
        for key in wanted:
            if key in filled:
                continue
            value = (answers or {}).get(key)
            if value not in (None, ''):
                filled[key] = value
        if all(key in filled for key in wanted):
            break

    return filled
