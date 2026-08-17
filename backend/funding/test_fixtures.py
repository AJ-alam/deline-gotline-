"""Answers that satisfy the schemas, in one place.

Every test that posts an application used to carry its own copy of the answer
dictionary. When the admission form gained the fields the office actually needs
— address, SIN, banking, programme dates — each copy had to be found and
corrected separately, and a copy that was missed failed with a 400 that looked
like a bug in the code under test.

These are built from the schema itself, so a field added tomorrow is filled in
automatically and no fixture goes stale.
"""

from funding.schemas import FieldType, get_schema

# A number that satisfies the Luhn check without being issuable.
#
# The published example, 046 454 286, passes Luhn but begins with 0 — which no
# issued SIN does, since the first digit is the province of registration. Our
# validator refuses it for that reason, correctly. This one is all nines behind
# a valid leading digit: it checksums, and it belongs to nobody.
TEST_SIN = '199999996'

_FILL = {
    FieldType.TEXT: 'Test value',
    FieldType.LONG_TEXT: 'Test detail',
    FieldType.EMAIL: 'person@example.com',
    FieldType.PHONE: '8675550143',
    FieldType.DATE: '2026-09-01',
    FieldType.MONEY: '6000',
    FieldType.INTEGER: '2',
    FieldType.PERCENT: '80',
    FieldType.BOOLEAN: 'false',
    # A declaration only has one satisfying answer; 'false' is refused by design.
    FieldType.CONFIRM: 'true',
    FieldType.FILE: 'provided',
    FieldType.FILES: ['document:1', 'document:2'],
    FieldType.SIGNATURE: 'Test Person',
    FieldType.SIN: TEST_SIN,
}


def _fill(field):
    """One satisfying answer for one field, whatever its type."""
    if field.type is FieldType.CHOICE:
        return field.choices[0].value
    # A table is filled from its own columns rather than from a canned row, so
    # a column added tomorrow is answered here too — the same reason nothing in
    # this module hard-codes a field list.
    if field.type is FieldType.TABLE:
        return [{column.key: _fill(column) for column in field.columns}]
    return _FILL[field.type]


def answers_for(slug: str, include_optional: bool = False, **overrides) -> dict:
    """Valid answers for one application type.

    Only required fields by default, so a test that overrides one is not also
    silently asserting something about the twenty it did not mention.
    """
    schema = get_schema(slug)
    answers = {}
    for field in schema.fields:
        # Never sent: the server works these out, and a fixture that supplied
        # one would be asserting that the server accepts what it must discard.
        if field.computed:
            continue
        if not (field.required or include_optional):
            continue
        answers[field.key] = _fill(field)
    answers.update(overrides)
    return answers


def admission_answers(**overrides) -> dict:
    """A complete admission application.

    Semester dates are set to a real span rather than the generic filler: the
    living allowance is priced per month between them, so a start equal to the
    end would award nothing and make a pricing test pass for the wrong reason.
    """
    defaults = dict(
        semester='fall',
        semester_start='2026-09-01',
        semester_end='2026-12-31',
        program_start='2026-09-01',
        program_end='2028-06-30',
        course_load='full_time',
        tuition_requested='6000',
    )
    # The caller's value wins. Passing both as keywords would collide.
    defaults.update(overrides)
    return answers_for('admission', **defaults)


def continuing_answers(**overrides) -> dict:
    """A complete continuing-funding renewal.

    Deliberately carries no semester dates, tuition or registrar email: the
    renewal does not ask for them. They arrive from the enrolment verification,
    which is the whole reason this fixture differs from `admission_answers`.
    """
    defaults = dict(
        full_name='Majid Khan',
        course_load='full_time',
        semester='fall',
        dependent_count='0',
        receives_sfa='false',
    )
    defaults.update(overrides)
    return answers_for('continuing_funding', **defaults)


def verification_answers(**overrides) -> dict:
    """What a registrar returns on the enrolment verification."""
    defaults = dict(
        is_enrolled='true',
        course_load='full_time',
        semester_start='2026-09-01',
        semester_end='2026-12-31',
        confirmed_tuition='6000',
        completed_on='2026-09-05',
    )
    defaults.update(overrides)
    return answers_for('enrollment_verification', **defaults)


def confirm_enrolment(application, **overrides):
    """Put an application past the enrolment gate.

    Admission and continuing funding cannot be forwarded or approved until the
    institution has confirmed the enrolment, because tuition is funded against
    the registrar's figure rather than the student's estimate. Tests that are
    about what happens *after* review need to get past that, and doing it
    through the real service rather than by setting a flag means they exercise
    the same path a registrar does.
    """
    from funding.services import verification

    existing = getattr(application, 'enrollment_verification', None)
    if existing is None or existing.status != 'completed':
        issued = verification.issue(
            application,
            (application.answers or {}).get('registrar_email') or 'registrar@example.com',
        )
        verification.complete(issued, verification_answers(**overrides))
    application.refresh_from_db()
    return application
