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

# Facts about their studies, as the student maintains them on their profile.
#
# Every key here is a column on `accounts.models.EnrolmentProfile` and a field
# key on at least one schema. The mapping is deliberately name-for-name: a
# translation layer between the two is a second place for them to disagree, and
# a profile column that no schema asks for is a box a student fills in for
# nothing.
#
# This is the only place `EnrolmentProfile` is read. See the docstring on the
# model for why that matters.
FROM_PROFILE = (
    'institution_name',
    'institution_location',
    'institution_phone',
    'registrar_email',
    'student_number',
    'program',
    'credential_level',
    'learning_style',
    'course_load',
    'program_start',
    'program_end',
    'program_year',
    'program_length_years',
    'dependent_count',
)

# The same facts, carried from the last application that stated one — for
# everybody who has applied before and never opened the profile screen.
#
# Deliberately absent, here and on the profile: `semester` and `receives_sfa`,
# which are about this term and this term only; the documents, which must be the
# current semester's; and the declaration and signature, which are the act of
# applying itself. Filling any of those in would be answering on the student's
# behalf.
FROM_EARLIER_APPLICATIONS = (
    'institution_name',
    'program',
    'course_load',
    'dependent_count',
    'credential_level',
    'student_number',
    'phone',
)


def _from_profile(user, keys: set[str]) -> dict:
    """The student's own profile, for the keys this schema actually asks.

    Reads the row rather than creating one: pre-filling a form is not a reason
    to write to the database, and `GET /api/form-prefill/{slug}/` is called on
    every form open by every applicant.
    """
    profile = getattr(user, 'enrolment_profile', None)
    if profile is None:
        return {}

    filled = {}
    for key in FROM_PROFILE:
        if key not in keys:
            continue
        value = getattr(profile, key, None)
        # 0 dependants is an answer, and `if value` would drop it — the same
        # class of fault as the frontend's `!answers[key]` treating "No" as
        # unanswered.
        if value not in (None, ''):
            filled[key] = value
    return filled


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

    # The profile before earlier applications, wherever both could answer. What
    # a student maintains on purpose beats what is inferred from a form they
    # filled in last February — that is the whole reason the screen exists, and
    # a student who corrects their institution there and still sees the old one
    # on the next form would reasonably conclude the profile does nothing.
    for key, value in _from_profile(user, keys).items():
        filled.setdefault(key, value)

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
