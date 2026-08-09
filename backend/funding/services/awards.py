"""Calculating what an application is awarded.

Every input is read from `application.answers` by its stable schema key. The
previous implementation resolved inputs by substring-matching display labels
(`get_val(['credential', 'degree', 'program type'])`), so an unrelated field
whose label merely contained 'degree' could decide a student's award, and an
answer that matched none of the magic substrings silently fell through to the
cheapest tier.

Business rules preserved from the original service:
  §4.1  Streams stack. DGGR supplements C-DFN, it does not replace it.
        Living allowances are additive; tuition is allocated against the real
        bill so no two streams fund the same dollar.
  §4.2  SFA recipients are excluded from C-DFN tuition and living.
  §4.3  DGGR extra tuition relief applies only above a threshold, is inclusive
        of the regular DGGR top-up, and is bounded by per-student and pool caps.
  §7.5  Rates are those in force when the application was submitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from funding.models import Application, ApplicationType, Award, FundingStream
from funding.services.policy import PolicyBook

ZERO = Decimal('0.00')


@dataclass(frozen=True)
class AwardLine:
    """One funded line, with the rule that produced it.

    `rule` is shown to staff. An award a reviewer cannot explain is an award they
    cannot defend to an applicant.
    """

    category: str
    stream: str
    amount: Decimal
    rule: str


@dataclass
class AwardBreakdown:
    lines: list[AwardLine] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), ZERO)

    def add(self, category, stream, amount, rule):
        self.lines.append(AwardLine(category, stream, amount, rule))

    def note(self, message):
        self.notes.append(message)


DEFAULT_SEMESTER_MONTHS = 4


def _months(answers) -> int:
    """Months of study, counting every month the student is in class.

    Sept 3 → Dec 20 is four monthly living payments (Sept, Oct, Nov, Dec), not
    three. Elapsed-month arithmetic drops the final partial month and leaves
    every standard semester one payment short.
    """
    from datetime import date

    def parse(value):
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None

    start = parse(answers.get('semester_start'))
    end = parse(answers.get('semester_end'))
    if not start or not end or end < start:
        return DEFAULT_SEMESTER_MONTHS
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _decimal(value) -> Decimal:
    if value in (None, ''):
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return ZERO


def _streams_for(application) -> set[str]:
    """Which streams this application draws on.

    Was parsed out of a free-text answer with `'PSSSP' in stream_raw`. The stream
    is now a stored field; the answer may still add a stacked stream.
    """
    streams = {application.stream}
    declared = application.answers.get('funding_stream')
    if declared:
        streams.add(str(declared).lower())
    return {s for s in streams if s in FundingStream.values}


def calculate(application: Application, policies: PolicyBook | None = None) -> AwardBreakdown:
    """Compute the award. Does not write anything."""
    policies = policies or PolicyBook.for_application(application)

    if application.type in (
        ApplicationType.ADMISSION,
        ApplicationType.CONTINUING_FUNDING,
        ApplicationType.ENROLLMENT_VERIFICATION,
    ):
        return _standard_funding(application, policies)
    if application.type == ApplicationType.GRADUATION_BURSARY:
        return _graduation_bursary(application, policies)
    if application.type == ApplicationType.ACADEMIC_SCHOLARSHIP:
        return _academic_scholarship(application, policies)
    if application.type == ApplicationType.HARDSHIP_BURSARY:
        return _hardship_bursary(application, policies)

    breakdown = AwardBreakdown()
    breakdown.note(f'No award rules defined for {application.get_type_display()}.')
    return breakdown


def _standard_funding(application, policies) -> AwardBreakdown:
    answers = application.answers
    breakdown = AwardBreakdown()

    full_time = answers.get('course_load') == 'full_time'
    load_key = 'fulltime' if full_time else 'parttime'
    has_dependents = bool(answers.get('has_dependents'))
    living_key = f"{load_key}_{'with' if has_dependents else 'no'}_dependents"

    months = _months(answers)
    streams = _streams_for(application)
    on_sfa = bool(answers.get('receives_sfa'))

    # Tuition is awarded against the confirmed bill only. Assuming the cap
    # overpays every student whose real tuition is lower.
    billed = _decimal(answers.get('confirmed_tuition') or answers.get('tuition_requested'))
    tuition_confirmed = billed > 0
    unfunded = billed if tuition_confirmed else ZERO

    def award_tuition(category, stream, cap, rule) -> Decimal:
        nonlocal unfunded
        if not tuition_confirmed:
            breakdown.add(category, stream, ZERO,
                          'Awaiting confirmed tuition — nothing awarded yet')
            return ZERO
        granted = min(unfunded, cap)
        if granted <= 0:
            breakdown.add(category, stream, ZERO,
                          'Tuition already fully funded by another stream')
            return ZERO
        unfunded -= granted
        breakdown.add(category, stream, granted, rule)
        return granted

    applied = []

    # ── C-DFN streams: excluded while the student receives SFA (§4.2) ──
    for stream, label in ((FundingStream.PSSSP, 'PSSSP'), (FundingStream.UCEPP, 'UCEPP')):
        if stream not in streams:
            continue
        if on_sfa:
            breakdown.note(f'{label} excluded — student receives SFA.')
            continue
        cap = policies.rate(f'{stream}_tuition', 'max_per_semester')
        award_tuition(f'Tuition ({label})', label, cap, f'{label} cap ${cap} per semester')
        rate = policies.rate(f'{stream}_living', living_key)
        breakdown.add(f'Living Allowance ({label})', label, rate * months,
                      f'${rate}/month × {months} months')
        applied.append(label)

    # ── DGGR tops up whatever the C-DFN caps left owing (§4.1) ──
    dggr_tuition = ZERO
    if FundingStream.DGGR in streams:
        rate = policies.rate('dggr_tuition', f'{load_key}_per_semester')
        dggr_tuition = award_tuition(
            'Tuition Top-Up (DGGR)', 'DGGR', rate,
            f"Tops up unfunded tuition, max ${rate} ({'full' if full_time else 'part'}-time)",
        )
        living_rate = policies.rate('dggr_living', living_key)
        breakdown.add('Living Allowance (DGGR)', 'DGGR', living_rate * months,
                      f'${living_rate}/month × {months} months')
        applied.append('DGGR')

        _extra_tuition_relief(
            breakdown, policies, billed, unfunded, dggr_tuition, tuition_confirmed,
        )

    if applied:
        books = policies.rate('system_config', 'book_allowance')
        if books:
            breakdown.add('Books & Supplies', applied[0], books, 'Book allowance')
    else:
        breakdown.note('No funding stream applied to this application.')

    return breakdown


def _extra_tuition_relief(breakdown, policies, billed, unfunded, dggr_tuition, confirmed):
    """§4.3 — relief on tuition above a threshold, inclusive of the DGGR top-up."""
    if not confirmed or unfunded <= 0:
        return
    threshold = policies.rate('dggr_extra_tuition', 'threshold_per_semester')
    if threshold <= 0 or billed <= threshold:
        return

    percent = policies.rate('dggr_extra_tuition', 'max_percent_covered') / Decimal(100)
    cap = policies.rate('dggr_extra_tuition', 'max_per_semester')
    inclusive_total = min(billed * percent, cap)

    # "Inclusive of" means the relief is the difference above the regular top-up,
    # not an additional payment on top of it.
    relief = max(ZERO, inclusive_total - dggr_tuition)
    relief = min(relief, unfunded)
    if relief > 0:
        breakdown.add(
            'Extra Tuition Relief', 'DGGR', relief,
            f'{percent * 100:.0f}% of ${billed}, capped at ${cap}, '
            f'inclusive of the DGGR top-up',
        )


def _graduation_bursary(application, policies) -> AwardBreakdown:
    """Award tier follows the credential earned.

    Previously the tier was chosen by substring-matching free text against eleven
    magic strings, defaulting to the cheapest — so 'BSc' paid the certificate rate.
    `credential` is now a validated choice, so an unrecognised value cannot occur.
    """
    breakdown = AwardBreakdown()
    credential = application.answers.get('credential')
    if not credential:
        breakdown.note('No credential recorded — award cannot be determined.')
        return breakdown

    amount = policies.rate('graduation_bursary', credential)
    breakdown.add('Graduation Bursary', 'DGGR', amount,
                  f'{credential.replace("_", " ").title()} rate')
    return breakdown


def _academic_scholarship(application, policies) -> AwardBreakdown:
    breakdown = AwardBreakdown()
    gpa = _decimal(application.answers.get('gpa_achieved'))
    high = policies.rate('academic_scholarship', 'high_threshold_percent')
    mid = policies.rate('academic_scholarship', 'mid_threshold_percent')

    if high and gpa >= high:
        amount = policies.rate('academic_scholarship', 'high_achievement_award')
        breakdown.add('Academic Scholarship', 'DGGR', amount, f'GPA {gpa} ≥ {high}%')
    elif mid and gpa >= mid:
        amount = policies.rate('academic_scholarship', 'mid_achievement_award')
        breakdown.add('Academic Scholarship', 'DGGR', amount, f'GPA {gpa} ≥ {mid}%')
    else:
        breakdown.note(f'GPA {gpa} is below the scholarship threshold of {mid}%.')
    return breakdown


def _hardship_bursary(application, policies) -> AwardBreakdown:
    breakdown = AwardBreakdown()
    requested = _decimal(application.answers.get('amount_requested'))
    cap = policies.rate('hardship_bursary', 'max_per_student')
    granted = min(requested, cap) if requested else ZERO
    if granted > 0:
        breakdown.add('Hardship Bursary', 'DGGR', granted,
                      f'Requested ${requested}, capped at ${cap}')
    else:
        breakdown.note('No amount requested.')
    return breakdown


CATEGORY_MAP = {
    'Tuition': Award.Category.TUITION,
    'Living': Award.Category.LIVING,
    'Books': Award.Category.BOOKS,
    'Travel': Award.Category.TRAVEL,
    'Bursary': Award.Category.BURSARY,
    'Scholarship': Award.Category.SCHOLARSHIP,
}


def _category_for(label: str) -> str:
    for token, category in CATEGORY_MAP.items():
        if token.lower() in label.lower():
            return category
    return Award.Category.BURSARY


def apply_award(application: Application, policies: PolicyBook | None = None) -> AwardBreakdown:
    """Calculate and persist. Refuses to write when policy is incomplete.

    An award derived from settings that do not exist would read as a real $0.00
    decision, and payment rows would be created for it.
    """
    policies = policies or PolicyBook.for_application(application)
    breakdown = calculate(application, policies)
    policies.require_complete()

    application.awards.filter(status=Award.Status.PENDING).delete()
    for line in breakdown.lines:
        if line.amount > 0:
            Award.objects.create(
                application=application,
                category=_category_for(line.category),
                amount=line.amount,
            )

    application.awarded_total = breakdown.total
    application.save(update_fields=['awarded_total', 'updated_at'])
    return breakdown
