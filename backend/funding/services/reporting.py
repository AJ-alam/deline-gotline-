"""The annual report the department sends its head office.

Built to the office's own mock-up: enrolment by semester split into university
and college with trades and upgrading as subsets of it, graduate awards by
residency and credential, the institutions and programmes attended, and a
financial summary that has to reconcile against a financial statement.

Three things this deliberately does not do.

**It does not guess.** University against college, and trades against
upgrading, come from the registrar's own answer on the enrolment verification.
An enrolment nobody classified is counted and reported as unclassified rather
than being sorted by matching words in a typed institution name — a report
figure decided by a display string is the fault this system was rebuilt to
remove, and this one goes to the funder.

**It does not report money as spent that came back.** Every money figure is
gross, repaid and net. An office reconciling against a financial statement
needs all three, and a report that only counts money leaving overstates the
year.

**It does not invent the costs it cannot see.** Staff wages and anything else
the office enters by hand are listed as what they are — entered figures, with
who entered them — and never mixed silently into a total the system computed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from funding.models import (
    AWARDED_STATUSES, Application, ApplicationType, Award, AwardRepayment,
    EnrollmentVerification, FundingStream, ReportedCost,
)

ZERO = Decimal('0.00')

# The report runs April to March, as its own title says.
FISCAL_START_MONTH = 4

# The order the office's own table uses.
SEASONS = ('spring', 'summer', 'fall', 'winter')
SEASON_LABELS = {'spring': 'Spring', 'summer': 'Summer',
                 'fall': 'Fall', 'winter': 'Winter'}

INSTITUTION_LABELS = {
    'university': 'University',
    'college': 'College or polytechnic',
    'trades_school': 'Trades school',
    'other': 'Other',
    '': 'Not classified',
}

PROGRAM_LABELS = {
    'post_secondary': 'Post-secondary',
    'trades': 'Trades',
    'upgrading': 'Upgrading',
    '': 'Not classified',
}

# What the office asked to see the money split by. Each is decided by the
# application type first and the award category second, because "graduate
# awards" and "monthly allowances" are different kinds of thing: one is a form,
# the other is a line on any form.
CATEGORY_ORDER = (
    ('tuition', 'Direct student funding — tuition and fees'),
    ('living', 'Monthly allowances'),
    ('graduate_awards', 'Graduate awards'),
    ('summer_awards', 'Summer student awards'),
    ('achievement_awards', 'Achievement awards'),
    ('other_support', 'Other student support'),
)


def fiscal_year_of(day: date) -> date:
    """The 1 April that begins the year containing this date."""
    return date(day.year if day.month >= FISCAL_START_MONTH else day.year - 1,
                FISCAL_START_MONTH, 1)


def fiscal_range(year_start: date) -> tuple[date, date]:
    return year_start, date(year_start.year + 1, FISCAL_START_MONTH, 1)


def _aware(day: date):
    """The start of this day, in the project's timezone.

    `submitted_at` is a datetime and comparing it against a bare date makes
    Django warn and compare in UTC — which puts the applications submitted in
    the first hours of 1 April into the previous fiscal year, in a report about
    which year money was spent in.
    """
    return timezone.make_aware(
        timezone.datetime.combine(day, timezone.datetime.min.time()))


def _money(amount) -> str:
    return f'{Decimal(amount or 0):.2f}'


def _bucket_for(application, category: str) -> str:
    """Which line of the financial summary an award belongs on.

    The application type decides first: a graduation bursary is a graduate
    award whatever category its line carries, and a practicum award is a summer
    student award. Only then does the category matter.
    """
    if application.type == ApplicationType.GRADUATION_BURSARY:
        return 'graduate_awards'
    if application.type == ApplicationType.PRACTICUM:
        return 'summer_awards'
    if application.type == ApplicationType.ACADEMIC_SCHOLARSHIP:
        return 'achievement_awards'
    if category == Award.Category.TUITION or category == Award.Category.BOOKS:
        return 'tuition'
    if category == Award.Category.LIVING:
        return 'living'
    return 'other_support'


def _classification(application, verifications: dict) -> tuple[str, str]:
    """How the registrar classified this enrolment, or blank for neither.

    Read from the verification's own answers rather than the application's:
    `CONFIRMABLE_KEYS` deliberately carries only keys the admission schema
    defines, so these two — which it does not — stay with the institution's
    declaration where the registrar put them.
    """
    answers = verifications.get(application.pk) or {}
    return (str(answers.get('institution_type') or ''),
            str(answers.get('program_type') or ''))


def _semester_of(application) -> str:
    semester = (application.semester or '').strip().lower()
    return semester if semester in SEASONS else ''


def annual_report(year_start: date | None = None, stream: str = '') -> dict:
    """Everything the office's report needs, for one fiscal year.

    `stream` narrows the whole report to one funding programme, by the
    application's *primary* stream — the same column the review queue filters
    on, so "DGGR" means the same thing on both screens. Pricing still draws on
    every stream an applicant qualifies for, which is why the programme
    breakdown below reports money separately from counts.
    """
    year_start = year_start or fiscal_year_of(date.today())
    opens, closes = fiscal_range(year_start)

    # Only applications the office actually committed to, in this year. An
    # application is counted against the year it was submitted in, which is the
    # year its semester falls in.
    selected = Application.objects.filter(
        status__in=AWARDED_STATUSES,
        submitted_at__gte=_aware(opens), submitted_at__lt=_aware(closes))
    if stream:
        selected = selected.filter(stream=stream)
    applications = list(selected.select_related('student'))
    by_id = {a.pk: a for a in applications}

    verifications = {
        row.application_id: (row.answers or {})
        for row in EnrollmentVerification.objects.filter(
            application_id__in=by_id, status=EnrollmentVerification.Status.COMPLETED)
    }

    lines = list(
        Award.objects.awarded()
        .filter(application_id__in=by_id)
        .values('application_id', 'category', 'amount', 'id', 'rule_code',
                'decision__rule_set_id')
    )
    # Repayments are gathered against **every** award of these applications,
    # not only the lines of the decision in force.
    #
    # `Award.objects.awarded()` scopes to the current decision, which is right
    # for what the office committed to. It is wrong for money that came back:
    # re-pricing an application supersedes its lines, and a repayment recorded
    # against a superseded line then disappeared from the report — the year
    # went back to reporting its gross as its net, silently, and $100 that a
    # student had returned stopped existing. Exactly why `Award.objects.paid()`
    # is deliberately unscoped: money that left the bank still left it, and
    # money that came back still came back.
    repayments = list(
        AwardRepayment.objects
        .filter(award__application_id__in=by_id)
        .values('award_id', 'award__application_id', 'award__category', 'amount')
    )

    # Built once and handed to the summary, rather than the summary building
    # its own. Recomputing made the report do all its work twice, and left it
    # possible for the sentence the office quotes to disagree with the table
    # printed directly above it.
    enrolment = _enrolment_table(applications, verifications)
    graduate_awards = _graduate_awards_table(applications)
    financial = _financial_table(applications, verifications, lines,
                                 repayments, year_start)

    students = _students_table(applications, lines, repayments)
    programmes = _programme_table(applications, lines, repayments)

    return {
        'fiscal_year': {
            'starts': opens.isoformat(),
            'ends': (date(closes.year, closes.month, 1)).isoformat(),
            'label': f'1 April {opens.year} – 31 March {closes.year}',
        },
        'enrolment': enrolment,
        'graduate_awards': graduate_awards,
        'institutions': _institutions_table(applications, verifications),
        'students': students,
        'programmes': programmes,
        'filter': {'stream': stream},
        'financial': financial,
        'highlights': _highlights(enrolment, graduate_awards, financial),
    }


def _semester_applications(applications):
    """Applications that represent a semester of study.

    The one-off awards — a graduation bursary, a practicum — are not an
    enrolment and are counted on their own table.
    """
    return [a for a in applications
            if a.type in (ApplicationType.ADMISSION,
                          ApplicationType.CONTINUING_FUNDING)]


def _enrolment_table(applications, verifications) -> dict:
    """Table 1: students by semester, by institution type.

    The office's own note: trades and upgrading are *subsets* of the university
    and college totals, not extra columns beside them. So a row's total is
    university + college + trades school + unclassified, and the trades and
    upgrading figures are counted independently of it.
    """
    rows = []
    counted = {season: defaultdict(set) for season in SEASONS}
    programmes = {season: defaultdict(set) for season in SEASONS}

    for application in _semester_applications(applications):
        season = _semester_of(application)
        if not season:
            continue
        institution, programme = _classification(application, verifications)
        who = application.student_id or f'app-{application.pk}'
        counted[season][institution or ''].add(who)
        if programme:
            programmes[season][programme].add(who)

    # The office's own table adds the seasons up — 20 + 5 + 40 + 30 = 95 — and
    # its summary calls that "95 semester enrolments". So the total row counts
    # *enrolments*, not people: a student who studies in two semesters had two
    # enrolments and appears in both. Counting distinct people instead produced
    # a total smaller than the column above it, which on a report going to a
    # funder reads as an arithmetic mistake.
    #
    # The distinct headcount is still worth having, so it is reported beside
    # the table under its own name rather than hidden inside it.
    people_seen = defaultdict(set)
    programme_people = defaultdict(set)
    for season in SEASONS:
        row = {
            'season': SEASON_LABELS[season],
            'university': len(counted[season].get('university', set())),
            'college': len(counted[season].get('college', set())),
            'trades_school': len(counted[season].get('trades_school', set())),
            'unclassified': len(counted[season].get('', set())
                                | counted[season].get('other', set())),
            'trades': len(programmes[season].get('trades', set())),
            'upgrading': len(programmes[season].get('upgrading', set())),
        }
        row['total'] = (row['university'] + row['college']
                        + row['trades_school'] + row['unclassified'])
        rows.append(row)
        for key, people in counted[season].items():
            people_seen[key or ''] |= people
        for key, people in programmes[season].items():
            programme_people[key] |= people

    total_row = {'season': 'Total'}
    for column in ('university', 'college', 'trades_school', 'unclassified',
                   'trades', 'upgrading', 'total'):
        total_row[column] = sum(row[column] for row in rows)

    distinct = len(set().union(*people_seen.values())) if people_seen else 0

    return {
        'rows': rows,
        'total': total_row,
        # Said on the report rather than left for the reader to work out why a
        # column does not behave as they expect.
        'note': ('Trades and upgrading are counted within the university and '
                 'college totals, not in addition to them. The total counts '
                 'enrolments: a student who studied in two semesters is '
                 'counted in each.'),
        # The headcount behind those enrolments, named rather than folded in.
        'distinct_students': distinct,
        'unclassified': total_row['unclassified'],
    }


# Which of the report's headings a graduation credential belongs under.
CREDENTIAL_GROUPS = {
    'high_school_diploma': 'high_school',
    'certificate': 'college',
    'diploma': 'college',
    'trades_certificate': 'trades',
    'trades_journeyperson': 'trades',
    'red_seal': 'trades',
    'pilot_licence': 'college',
    'bachelors_degree': 'university',
    'masters_degree': 'university',
    'doctorate': 'university',
    'juris_doctor': 'university',
    'md_dds': 'university',
}


def _graduate_awards_table(applications) -> dict:
    """Table 2: graduate awards by residency and credential.

    Residency is the applicant's own address on the claim — Délı̨nę or
    elsewhere. It is not the screening's `lives_in_nwt`, which is a different
    question: somebody can live in the Northwest Territories without living in
    Délı̨nę, and the office's table distinguishes exactly those two.
    """
    rows = {'resident': _empty_grad_row('Délı̨nę residents'),
            'away': _empty_grad_row('Beneficiaries outside Délı̨nę')}

    for application in applications:
        if application.type != ApplicationType.GRADUATION_BURSARY:
            continue
        answers = application.answers or {}
        city = str(answers.get('city') or '').strip().lower()
        if not city and application.student is not None:
            city = str(getattr(application.student, 'city', '') or '').strip().lower()
        key = 'resident' if city.startswith('d') and 'l' in city else 'away'

        group = CREDENTIAL_GROUPS.get(str(answers.get('credential') or ''), 'other')
        rows[key][group] = rows[key].get(group, 0) + 1
        rows[key]['total'] += 1

    total = _empty_grad_row('Total')
    for row in rows.values():
        for key in ('university', 'college', 'high_school', 'trades', 'other', 'total'):
            total[key] += row[key]

    return {'rows': [rows['resident'], rows['away']], 'total': total}


def _empty_grad_row(label: str) -> dict:
    return {'residency': label, 'university': 0, 'college': 0,
            'high_school': 0, 'trades': 0, 'other': 0, 'total': 0}


def _rule_streams(rule_set_ids) -> dict[int, dict[str, str]]:
    """Which programme each rule belongs to, per rule set.

    Read from the rule set that priced the decision rather than the one in
    force now, so a report re-run next year still splits the money the way it
    was split when it was awarded.
    """
    from funding.models import Rule

    mapping: dict[int, dict[str, str]] = {}
    for rule in Rule.objects.filter(rule_set_id__in=set(rule_set_ids)):
        streams = rule.applies_to_streams or []
        if len(streams) == 1:
            mapping.setdefault(rule.rule_set_id, {})[rule.code] = streams[0]
    return mapping


def _programme_table(applications, lines, repayments) -> dict:
    """Funding programme breakdown — what each programme funded.

    **Counts and money are attributed differently, on purpose.**

    An application belongs to one primary stream — the column its deadline is
    measured against — so counting applications and students by stream is
    straightforward. Money is not: pricing draws on every stream an applicant
    qualifies for, and DGGR tops up rather than replaces, so one application
    routinely spends from two programmes.

    So money is attributed by the *rule* that produced each line, which is
    exact for the seven tuition and living rules because each names a single
    stream. The bursary, travel and scholarship rules name none — they apply to
    everybody — and that money is reported under its own heading rather than
    being pushed into a programme it does not belong to. Guessing there would
    be this report telling a funder that DGGR paid for something it did not.
    """
    by_id = {a.pk: a for a in applications}
    rule_streams = _rule_streams([l['decision__rule_set_id'] for l in lines])

    rows: dict[str, dict] = {}

    def row(key: str, label: str) -> dict:
        return rows.setdefault(key, {
            'stream': key, 'label': label,
            'applications': 0, 'students': set(),
            'gross': ZERO, 'repaid': ZERO,
        })

    for value, label in FundingStream.choices:
        row(value, label)

    for application in applications:
        entry = row(application.stream,
                    dict(FundingStream.choices).get(application.stream,
                                                    application.stream))
        entry['applications'] += 1
        entry['students'].add(application.student_id or f'app-{application.pk}')

    shared = {'stream': 'shared', 'label': 'Not tied to one programme',
              'applications': 0, 'students': set(), 'gross': ZERO, 'repaid': ZERO}

    def money_row(line_rule_code, rule_set_id):
        stream = (rule_streams.get(rule_set_id) or {}).get(line_rule_code, '')
        return rows[stream] if stream in rows else shared

    for line in lines:
        target = money_row(line['rule_code'], line['decision__rule_set_id'])
        target['gross'] += line['amount'] or ZERO

    line_rules = {l['id']: (l['rule_code'], l['decision__rule_set_id']) for l in lines}
    for repayment in repayments:
        # A repayment may sit on a line from a superseded decision, which is not
        # in `lines`. Its application's primary stream is the honest fallback.
        code, rule_set_id = line_rules.get(repayment.get('award_id'), (None, None))
        if code is not None:
            target = money_row(code, rule_set_id)
        else:
            application = by_id[repayment['award__application_id']]
            target = rows.get(application.stream, shared)
        target['repaid'] += repayment['amount'] or ZERO

    ordered = []
    for entry in list(rows.values()) + [shared]:
        if (entry['applications'] == 0 and entry['gross'] == ZERO
                and entry is shared):
            continue
        ordered.append({
            'stream': entry['stream'],
            'label': entry['label'],
            'applications': entry['applications'],
            'students': len(entry['students']),
            'gross': _money(entry['gross']),
            'repaid': _money(entry['repaid']),
            'net': _money(entry['gross'] - entry['repaid']),
        })
    return {
        'rows': ordered,
        'note': ('Applications are counted against their primary programme. '
                 'Money is attributed to the programme whose rule paid it, so '
                 'an application funded by two programmes appears in both.'),
    }


def _students_table(applications, lines, repayments) -> dict:
    """What each student received, by their number.

    The office asked for the funding broken down by student number. Identified
    by beneficiary number rather than by name: this is a report that leaves the
    building, the number is what their head department reconciles against, and
    a name is not an identifier — two people share one often enough.

    A student with no number on file is listed as unidentified rather than
    dropped, so the rows still add up to the year.

    **A row is not a person.** Two people holding one beneficiary number
    are one row here, which is right for a table the head department
    reconciles by number and wrong for anything that wants a headcount --
    so the headcount is reported separately as `distinct_students` rather
    than left to be guessed from the row count.
    """
    by_id = {a.pk: a for a in applications}
    people: dict[str, dict] = {}

    def entry(application):
        student = application.student
        number = (getattr(student, 'beneficiary_number', '') or '').strip()
        key = number or f'unidentified-{application.student_id or application.pk}'
        return people.setdefault(key, {
            'student_number': number,
            'name': (student.full_name if student else _recipient_name(application)),
            'applications': 0,
            'gross': ZERO,
            'repaid': ZERO,
        })

    for application in applications:
        entry(application)['applications'] += 1
    for line in lines:
        entry(by_id[line['application_id']])['gross'] += line['amount'] or ZERO
    for row in repayments:
        entry(by_id[row['award__application_id']])['repaid'] += row['amount'] or ZERO

    rows = []
    for person in people.values():
        rows.append({
            'student_number': person['student_number'],
            'name': person['name'],
            'applications': person['applications'],
            'gross': _money(person['gross']),
            'repaid': _money(person['repaid']),
            'net': _money(person['gross'] - person['repaid']),
        })
    rows.sort(key=lambda r: Decimal(r['net']), reverse=True)
    return {
        'rows': rows,
        'students': len(rows),
        # The people behind those rows. Equal to the row count only when
        # every student holds their own number.
        'distinct_students': len({a.student_id or f'app-{a.pk}'
                                  for a in applications}),
        'unidentified': sum(1 for r in rows if not r['student_number']),
        # How many people were folded into a shared number. A report that
        # merged 77 students into one row and said nothing has understated
        # its own reach to a funder.
        'sharing_a_number': max(
            0, len({a.student_id or f'app-{a.pk}' for a in applications})
            - len(rows)),
    }


def _recipient_name(application) -> str:
    answers = application.answers or {}
    named = (answers.get('full_name') or '').strip()
    if named:
        return named
    return f"{answers.get('first_name', '')} {answers.get('last_name', '')}".strip()


def _institutions_table(applications, verifications) -> dict:
    """Table 3: who went where, and to study what.

    Grouped by the institution as it was written down. Two spellings of one
    college are two rows — the office knows its own institutions and can see
    that; silently merging them by fuzzy matching would be this report deciding
    two names mean one place.
    """
    grouped: dict[tuple[str, str], dict] = {}
    for application in _semester_applications(applications):
        answers = application.answers or {}
        name = str(answers.get('institution_name') or '').strip()
        if not name:
            continue
        institution, _programme = _classification(application, verifications)
        key = (institution or '', name.casefold())
        entry = grouped.setdefault(key, {
            'institution_type': institution or '',
            'institution_type_label': INSTITUTION_LABELS.get(institution or '',
                                                             'Not classified'),
            'name': name, 'programs': set(), 'students': set(),
        })
        programme = str(answers.get('program') or '').strip()
        if programme:
            entry['programs'].add(programme)
        entry['students'].add(application.student_id or f'app-{application.pk}')

    groups: dict[str, list] = defaultdict(list)
    for entry in grouped.values():
        groups[entry['institution_type']].append({
            'name': entry['name'],
            'programs': sorted(entry['programs']),
            'students': len(entry['students']),
        })

    sections = []
    for key in ('university', 'college', 'trades_school', 'other', ''):
        rows = sorted(groups.get(key, []), key=lambda r: (-r['students'], r['name']))
        if not rows:
            continue
        sections.append({
            'institution_type': key,
            'label': INSTITUTION_LABELS.get(key, 'Not classified'),
            'rows': rows,
            'students': sum(r['students'] for r in rows),
        })
    return {'sections': sections}


def _financial_table(applications, verifications, lines, repaid, year_start) -> dict:
    """Table 4: what the year cost, and what came back.

    Gross, repaid and net on every figure. A report that only counts money
    leaving cannot be reconciled against a financial statement, which is the
    reason the office asked for it.
    """
    by_season: dict[str, dict] = {
        season: {key: {'gross': ZERO, 'repaid': ZERO} for key, _ in CATEGORY_ORDER}
        for season in SEASONS
    }
    unscheduled = {key: {'gross': ZERO, 'repaid': ZERO} for key, _ in CATEGORY_ORDER}
    by_id = {a.pk: a for a in applications}

    for line in lines:
        application = by_id[line['application_id']]
        bucket = _bucket_for(application, line['category'])
        season = _semester_of(application)
        target = by_season[season][bucket] if season else unscheduled[bucket]
        target['gross'] += line['amount'] or ZERO

    # Bucketed by the award the money came back from, which may belong to a
    # decision since superseded — see `annual_report`.
    for row in repaid:
        application = by_id[row['award__application_id']]
        bucket = _bucket_for(application, row['award__category'])
        season = _semester_of(application)
        target = by_season[season][bucket] if season else unscheduled[bucket]
        target['repaid'] += row['amount'] or ZERO

    def row_for(label, buckets):
        row = {'season': label, 'categories': {}, 'gross': ZERO, 'repaid': ZERO}
        for key, _title in CATEGORY_ORDER:
            figures = buckets[key]
            row['categories'][key] = {
                'gross': _money(figures['gross']),
                'repaid': _money(figures['repaid']),
                'net': _money(figures['gross'] - figures['repaid']),
            }
            row['gross'] += figures['gross']
            row['repaid'] += figures['repaid']
        row['net'] = _money(row['gross'] - row['repaid'])
        row['gross'] = _money(row['gross'])
        row['repaid'] = _money(row['repaid'])
        return row

    rows = [row_for(SEASON_LABELS[season], by_season[season]) for season in SEASONS]
    if any(figures['gross'] for figures in unscheduled.values()):
        rows.append(row_for('No semester recorded', unscheduled))

    totals = {key: {'gross': ZERO, 'repaid': ZERO} for key, _ in CATEGORY_ORDER}
    for buckets in list(by_season.values()) + [unscheduled]:
        for key, _ in CATEGORY_ORDER:
            totals[key]['gross'] += buckets[key]['gross']
            totals[key]['repaid'] += buckets[key]['repaid']
    total_row = row_for('Total direct funding', totals)

    entered = [
        {'label': cost.label, 'amount': _money(cost.amount), 'note': cost.note,
         'recorded_by': (cost.recorded_by.full_name if cost.recorded_by else ''),
         'updated_at': cost.updated_at.date().isoformat()}
        for cost in ReportedCost.objects.filter(fiscal_year_start=year_start)
    ]
    entered_total = sum((Decimal(item['amount']) for item in entered), ZERO)
    direct_net = Decimal(total_row['net'])

    return {
        'categories': [{'key': key, 'label': label} for key, label in CATEGORY_ORDER],
        'rows': rows,
        'total': total_row,
        # Kept apart from the computed figures and labelled, because a hand-
        # entered number folded silently into a total is a total nobody can
        # check.
        'entered': entered,
        'entered_total': _money(entered_total),
        'grand_total': _money(direct_net + entered_total),
    }


def _highlights(enrolment: dict, grads: dict, financial: dict) -> dict:
    """The figures the office quotes in its summary.

    Read off the tables it was given rather than worked out again, so the
    sentence in the summary cannot disagree with the table beneath it.
    """

    # Only where something was actually spent. On an empty year this named a
    # season as having "the highest level of financial assistance ($0.00)",
    # which is a claim about nothing.
    spent = [row for row in financial['rows']
             if row['season'] != 'No semester recorded' and Decimal(row['net']) > 0]
    busiest = max(spent, key=lambda row: Decimal(row['net']), default=None)

    totals = financial['total']['categories']
    return {
        'semester_enrolments': enrolment['total']['total'],
        'graduate_awards_issued': grads['total']['total'],
        'direct_funding_net': financial['total']['net'],
        'direct_funding_gross': financial['total']['gross'],
        'repaid': financial['total']['repaid'],
        'graduate_awards_total': totals['graduate_awards']['net'],
        'summer_awards_total': totals['summer_awards']['net'],
        'achievement_awards_total': totals['achievement_awards']['net'],
        'entered_total': financial['entered_total'],
        'grand_total': financial['grand_total'],
        'busiest_season': busiest['season'] if busiest else '',
        'busiest_season_total': busiest['net'] if busiest else _money(ZERO),
    }
