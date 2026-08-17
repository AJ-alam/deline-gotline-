"""Submission cut-offs, and whether an application met one.

ApplicationDeadline existed as a table with tests and no reader. Nothing wrote
`Application.submitted_after_deadline`, so the staff dashboard's "submitted
late" count was structurally always zero — a number on a screen that could not
ever be anything else. `semester` and `academic_year` on Application were the
same: columns nothing filled in, while the real values sat inside `answers`.

This is the reader. It lifts the semester out of the answers, finds the
deadline that governs it, and stamps the result on the application at the
moment it is submitted — so lateness is decided once, against the deadline in
force then, and does not silently change later when the office edits a date.
"""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

from funding.models import ApplicationDeadline

# What a deadline is keyed by, alongside the stream.
FALL = 'fall'


def parse_date(value) -> date | None:
    """A date from whatever the answers hold. Never raises."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def academic_year_of(day: date | None) -> str:
    """The academic year a date falls in, as '2026-2027'.

    August onward belongs to the year that is starting; earlier months belong
    to the one already running. A single cut month is the whole rule, so a
    January application lands in the same year as the previous September.
    """
    if day is None:
        return ''
    start = day.year if day.month >= 8 else day.year - 1
    return f'{start}-{start + 1}'


def coordinates(application) -> tuple[str, str]:
    """The (academic_year, semester) an application is for.

    Read from the answers, because that is where the applicant put them. Types
    that do not run by semester — a graduation bursary, emergency relief —
    return blanks, and nothing downstream treats those as late.
    """
    answers = application.answers or {}
    semester = str(answers.get('semester') or '').strip().lower()
    if not semester:
        return '', ''

    start = parse_date(answers.get('semester_start'))
    if start is None:
        # No start date: fall back to when it was submitted, which is the only
        # other date we have and is right for anything filed in its own term.
        submitted = application.submitted_at
        start = submitted.date() if submitted else timezone.now().date()
    return academic_year_of(start), semester


def governing(stream: str, academic_year: str, semester: str):
    """The deadline for one stream and term, or None if none is set.

    None matters: an office that has not entered a deadline has not imposed
    one, and no application may be marked late against a date nobody chose.
    """
    if not (academic_year and semester):
        return None
    return ApplicationDeadline.objects.filter(
        stream=stream, academic_year=academic_year, semester=semester,
    ).first()


# Types that are not filed against a submission deadline.
#
# An appeal is the case, and it only became one when the appeal form started
# asking for a semester: any application carrying one gets a term, and a term
# with a deadline behind it gets a lateness flag. An appeal filed in December
# about a Fall decision would have been marked "submitted late" — which is not
# a fault, it is the entire purpose of the form. Filing after something has
# gone wrong is what an appeal is.
#
# It still records its term. That is how staff find the decision it argues
# with; only the judgement about being late is withheld.
NEVER_LATE = ('appeal',)


def stamp(application) -> None:
    """Record the term and whether this submission made its deadline.

    Called once, when the application is submitted. Deciding lateness here
    rather than on read means a later edit to the deadline cannot retroactively
    make a filed application late, which is the behaviour an appeal depends on.
    """
    academic_year, semester = coordinates(application)
    deadline = governing(application.stream, academic_year, semester)

    application.academic_year = academic_year
    application.semester = semester
    application.submitted_after_deadline = bool(
        deadline and application.submitted_at
        and application.submitted_at > deadline.closes_at
        and application.type not in NEVER_LATE
    )
    application.save(update_fields=[
        'academic_year', 'semester', 'submitted_after_deadline', 'updated_at',
    ])


def upcoming(when=None, limit: int = 4) -> list[ApplicationDeadline]:
    """The next cut-offs, soonest first, one per term.

    Deduplicated by term rather than returned row by row. The office sets the
    same date for every stream, so the raw rows repeat each date three times —
    taking the first four gives two terms, and a client that did not know to
    collapse them would show one deadline three times over. The limit counts
    terms, which is what a student is being told about.
    """
    when = when or timezone.now()
    seen: set[tuple[str, str, object]] = set()
    found: list[ApplicationDeadline] = []

    for deadline in (ApplicationDeadline.objects
                     .filter(closes_at__gte=when)
                     .order_by('closes_at')):
        term = (deadline.academic_year, deadline.semester, deadline.closes_at)
        if term in seen:
            continue
        seen.add(term)
        found.append(deadline)
        if len(found) >= limit:
            break
    return found
