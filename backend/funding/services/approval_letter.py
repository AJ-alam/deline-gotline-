"""The letters the office sends when funding is approved.

The office supplied three templates, one per programme:

    DGG-CDFN     the Canada Dèlı̨nę First Nation Student Bursary (PSSSP)
    DGG-UCEPP    University/College Entrance Preparation Program
    DGGR-SFSP    the Dene Gha Gok'ǝ Réhkw'I top-up

**A letter belongs to a programme, not to an application.** One approval
routinely draws on two of them: DGGR tops up rather than replaces, so a student
funded under PSSSP with a DGGR top-up is owed the CDFN letter *and* the DGGR
letter — which is what the DGGR letter's own wording says it is for, "students
who are already in receipt of primary funding". Keying the letter on
`Application.stream` would have sent one letter naming a total that two
programmes paid.

Which programme funded a line is read from the rule that produced it, in the
rule set that priced it — `psssp_living` names psssp, `dggr_tuition_top_up`
names dggr. That is only possible because those six rules each name exactly one
stream; the bursary and travel rules name none, which is why nothing here
attributes *money in general* to a stream and why the dashboard's stream split
is counts only. A line nothing can attribute — a hand-set award, whose rule code
is `manual_N` — goes on the application's primary stream, because that is the
programme it was filed under.

Every figure comes from the decision in force. Nothing here recomputes an
amount: an approval letter that disagreed with the award it describes would be
the dashboard/`awarded_total` fault again, in a document the office signs.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from funding.models import (
    Application, ApplicationStatus, Award, AwardDecision, FundingStream,
    PolicySetting,
)

ZERO = Decimal('0.00')


class LetterUnavailable(Exception):
    """No letter can be produced, and why."""


# ── What each programme's letter says ───────────────────────────────────────
#
# The wording is the office's, transcribed from the supplied templates. It lives
# here rather than in a component because the portal copy and the emailed copy
# have to be the same letter: two transcriptions are two documents that can
# disagree about what somebody was awarded.

PROGRAMMES = {
    FundingStream.PSSSP: {
        'code': 'DGG-CDFN',
        'title': ('Approval of Délı̨nę Got’ı̨nę Government (DGG) – Canada Dèlı̨nę '
                  'First Nation Student Bursary for the'),
        'identifier': 'treaty',
        # The title ends "for the", so the term completes it.
        'term_in_title': True,
        'shows_date': False,
        'opening': (
            'The Dèlı̨nę Got́ı̨nę Government (DGG) Department of Education who '
            'oversees the DGG – Canada Dèlı̨nę First Nation Student Bursary have '
            'received and reviewed your recent application and would like to '
            'congratulate you on your approval.'
        ),
        'rows': (
            ('tuition', 'Program Costs (Tuition, books, fees, etc.)*'),
            ('living', 'Monthly Allowance'),
        ),
        'total_label': 'Total Allotted',
        # The figure is `psssp_tuition.max_per_semester`, read rather than
        # typed: it is a rate the office edits on the policy screen, and a
        # second copy of it in a letter is a second copy that can disagree.
        'footnote': (
            'Students may not receive the entire allotted amount and are only '
            'eligible for up to {cap} per semester upon submission of term cost '
            'breakdown, tuition fees and receipts'
        ),
        'footnote_rate': ('psssp_tuition', 'max_per_semester'),
        'paragraphs': (
            'You must inform the Education Department of any changes during your '
            'academic year (examples include but are not limited to withdrawing '
            'from a course or program, dropping to part-time studies, or receiving '
            'funds from other source). Failure to do so will result in suspension '
            'from the bursary program.',
            'Each semester requires submission of forms and documents to continue '
            'to be funded. Please contact the Student Support Worker or visit '
            'www.deline.ca for application forms and for more information.',
            'We wish you the best of luck in your upcoming/current semester and '
            'are happy to offer support as needed! Don’t hesitate to reach out at '
            'any time!',
        ),
    },
    FundingStream.UCEPP: {
        'code': 'DGG-UCEPP',
        'title': ('Approval of Deline Gotine Government – University/College '
                  'Entrance Preparation Program (UCEPP) for the'),
        'identifier': 'treaty',
        'term_in_title': True,
        'shows_date': False,
        'opening': (
            'The Dèlı̨nę Got́ı̨nę Government Department of Education who oversee the '
            'UCEPP Policy have received and reviewed your recent application and '
            'would like to congratulate you on your approval.'
        ),
        'rows': (
            ('tuition', 'Program Costs (Tuition, books, fees, etc.)'),
            ('living', 'Monthly Allowance'),
        ),
        # The office's template carries no total row on this letter.
        'total_label': '',
        'footnote': '',
        'footnote_rate': None,
        # Printed inside the amount cell, as on the template: "up to $2,000.00
        # upon university/college invoicing or submission of receipts".
        'tuition_qualifier': ('up to {cap} upon university/college invoicing or '
                              'submission of receipts'),
        'tuition_qualifier_rate': ('ucepp_tuition', 'max_per_semester'),
        'paragraphs': (
            'You must inform Education Department of any changes during your '
            'academic year (examples include but are not limited to withdrawing '
            'from a course or program, dropping to part-time studies, or receiving '
            'funds from other source) for your eligibility for UCEPP funds. '
            'Failure to do so will result in suspension from the funding program.',
            'You will need to re-apply for funding for additional semesters of '
            'study, To do so, contact the Post-Secondary Student Support Officer '
            'and fill out the required paperwork to meet all current policy '
            'requirements or visit www.deline.ca for forms.',
            'We wish you the best of luck in your upcoming/current semester and '
            'are happy to offer support as needed! Don’t hesitate to reach out at '
            'any time!',
        ),
    },
    FundingStream.DGGR: {
        'code': 'DGGR-SFSP',
        'title': ('Approval of Dene Gha Gok’ǝ Réhkw’I (DGGR) - Student Financial '
                  'Support Top-Up Funds'),
        'identifier': 'beneficiary',
        # This title is a complete sentence — "…Top-Up Funds" — so the term is
        # not appended to it. Doing so anyway read as "Top-Up Funds Fall
        # 2026-2027". The semester is in the breakdown's own column, which is
        # where this template puts it.
        'term_in_title': False,
        # Alone among the three, this template carries a date.
        'shows_date': True,
        'opening': (
            'The Dèlı̨nę Got́ı̨nę Government Department of Education who oversee the '
            'DGGR - Student Financial Support Program Policy have received and '
            'reviewed your recent application and would like to congratulate you '
            'on your approval for Top-up funding.'
        ),
        'rows': (
            ('tuition', 'Semester Stipend'),
            ('living', 'Monthly Allowance'),
        ),
        'total_label': 'Total',
        'footnote': '',
        'footnote_rate': None,
        'paragraphs': (
            'This program is available to registered Délı̨nę beneficiary students '
            'enrolled under the land claims agreement and provides supplementary '
            'top-up funds to assist students who are already in receipt of primary '
            'funding. Students may access primary funders such as GNWT Student '
            'Financial Assistance or through the Post-Secondary Student Support '
            'Program but not both.',
            'Students must inform the Education Department of any changes to their '
            'enrollment or funding during the academic year (examples include but '
            'are not limited to withdrawing from a course or program, dropping to '
            'part-time studies, or receiving funds from another land claim). '
            'Failure to do so will result in suspension from the top-up program.',
            'Funding is approved per semester; students must re-apply for future '
            'semesters. To do so, please contact the Post-Secondary Student '
            'Support Officer or visit www.deline.ca to fill out the required forms.',
            'We wish you the best of luck in your upcoming/current semester and '
            'are happy to offer support as needed! Don’t hesitate to reach out at '
            'any time!',
        ),
    },
}

# What makes an award a semester's funding rather than a one-off. Every one of
# the three templates is built around these two rows.
SEMESTER_CATEGORIES = frozenset({Award.Category.TUITION, Award.Category.LIVING})

# The order the office's programmes are described in: the primary funding
# first, then the top-up that supplements it. A student receiving both should
# read them that way round.
PROGRAMME_ORDER = (FundingStream.PSSSP, FundingStream.UCEPP, FundingStream.DGGR)


def _money(amount: Decimal) -> str:
    return f'${amount:,.2f}'


def _rate(section: str, key: str) -> str:
    """A policy rate, formatted, or an empty string when it is unset.

    A missing rate must never print as $0.00 — that is a letter telling a
    student the cap on their funding is nothing. The sentence carrying it is
    dropped instead, and `missing_rates` names the gap.
    """
    setting = PolicySetting.objects.filter(
        section=section, key=key, is_active=True).first()
    return _money(setting.value) if setting else ''


def _streams_by_rule(decision: AwardDecision) -> dict[str, str]:
    """Which programme each rule in the priced rule set belongs to.

    Read from the rule set that produced this decision, not from the one in
    force now: a decision stays replayable against the rules that governed it,
    and a letter reprinted next year must still say what it said.
    """
    mapping = {}
    for rule in decision.rule_set.rules.all():
        streams = rule.applies_to_streams or []
        if len(streams) == 1:
            mapping[rule.code] = streams[0]
    return mapping


def _allowance_note(line: Award) -> str:
    """"$1,700.00/month × 4 months", where the line knows.

    Read from `Award.detail`, which the rule wrote as figures. Lines priced
    before that existed, and hand-set awards, carry nothing — and then the cell
    shows the amount alone rather than inventing a rate.
    """
    detail = line.detail or {}
    rate, months = detail.get('monthly_rate'), detail.get('months')
    if not rate or not months:
        return ''
    return f'{_money(Decimal(str(rate)))}/month × {months} month{"" if months == 1 else "s"}'


def _semester_label(value: str) -> str:
    """"Fall", not "fall".

    Taken from the schema's own choice label rather than title-cased. The stored
    value is the identity and the label is how it is written down; deriving one
    from the other by string surgery is how a display string starts deciding
    things. A value the schema does not offer is printed as it stands.
    """
    from funding.schemas.admission import SEMESTER

    for choice in SEMESTER:
        if choice.value == value:
            return choice.label
    return value


def _term(application: Application) -> str:
    parts = [_semester_label(application.semester), application.academic_year]
    return ' '.join(part for part in parts if part)


def _identifier(student, kind: str) -> dict:
    """The number the template asks for, punctuated as the template punctuates it.

    The value is blank where the account has none. Printed empty rather than
    hidden, because the office writes it on by hand — a letter with no line for
    it is a letter that cannot be completed.
    """
    if kind == 'beneficiary':
        return {'label': 'Beneficiary #:',
                'value': getattr(student, 'beneficiary_number', '') or ''}
    return {'label': 'Treaty #:', 'value': getattr(student, 'treaty_number', '') or ''}


def _address_lines(application: Application, student) -> list[str]:
    """Where the letter is posted.

    The office's templates carry a blank address block under the date, because
    these go out on paper as well as by email — a letter with nowhere to write
    an address cannot go in a window envelope. Filled from the application's
    own answers first and the account second: the address on the form is the
    one the applicant gave for this application.

    Empty lines are dropped rather than printed blank, and an applicant with no
    address on file gets no block at all rather than three empty rules.
    """
    answers = application.answers or {}

    def pick(key):
        value = (answers.get(key) or '').strip()
        if value:
            return value
        return (getattr(student, key, '') or '').strip() if student else ''

    street = pick('street_address')
    city, province, postal = pick('city'), pick('province'), pick('postal_code')
    town = ', '.join(part for part in (city, province) if part)
    if postal:
        town = f'{town}  {postal}'.strip()

    return [line for line in (_recipient(application), street, town) if line]


def _recipient(application: Application) -> str:
    answers = application.answers or {}
    named = (answers.get('full_name') or '').strip()
    if not named:
        named = f"{answers.get('first_name', '')} {answers.get('last_name', '')}".strip()
    if not named and application.student:
        named = application.student.full_name
    return named


def signatory() -> dict:
    """Who signs. Settings, so a deployment corrects a name without a release.

    The templates carry one Director's name typed into the document. A person
    who leaves the post should not require a code change to stop signing the
    office's letters.
    """
    return {
        'name': getattr(settings, 'DIRECTOR_NAME', 'Wajiha Shah'),
        'title': getattr(settings, 'DIRECTOR_TITLE', 'Director of Education'),
        'organisation': 'Délı̨nę Got’ı̨nę Government',
        'email': getattr(settings, 'DIRECTOR_EMAIL', 'director.education@gov.deline.ca'),
    }


def office() -> dict:
    return {
        'address': getattr(settings, 'SUPPORT_ADDRESS', 'P.O. Box 156, Délı̨nę, NT X0E 0G0'),
        'phone': getattr(settings, 'SUPPORT_PHONE', '(867) 589.3515'),
        'website': 'www.deline.ca',
    }


def letters_for(application: Application) -> list[dict]:
    """Every approval letter this application earns, one per programme.

    Raises `LetterUnavailable` where there is nothing to send: a letter is a
    congratulation on an approval, so an application nobody has approved has
    none, and neither has an approved one that has not been priced.
    """
    if application.status not in (ApplicationStatus.APPROVED,
                                  ApplicationStatus.SENT_TO_FINANCE):
        raise LetterUnavailable('This application has not been approved.')

    decision = application.decisions.filter(is_current=True).first()
    if decision is None:
        raise LetterUnavailable('This application has not been priced.')

    lines = list(Award.objects.current().filter(application=application))
    if not lines:
        raise LetterUnavailable('The pricing in force awards nothing.')
    if not any(line.category in SEMESTER_CATEGORIES for line in lines):
        raise LetterUnavailable(
            'The office has supplied approval letters for semester funding only. '
            'This award is a one-off.')

    by_rule = _streams_by_rule(decision)
    grouped: dict[str, list[Award]] = {}
    for line in lines:
        # A line nothing can attribute belongs to the programme the application
        # was filed under. Dropping it would produce letters whose figures add
        # up to less than the award they describe.
        stream = by_rule.get(line.rule_code, application.stream)
        grouped.setdefault(stream, []).append(line)

    student = application.student
    term = _term(application)
    letters = []
    for stream in PROGRAMME_ORDER:
        programme = PROGRAMMES[stream]
        stream_lines = grouped.get(stream, [])
        # Only where the programme actually funded a semester. All three
        # templates describe semester funding — program costs and a monthly
        # allowance, "for the [term]" — so an application whose award is a
        # travel claim or a graduation bursary has none of what they are about,
        # and the office has supplied no letter for those. Producing one anyway
        # would send a student a "Semester Stipend" table listing their
        # graduation cheque.
        if not any(line.category in SEMESTER_CATEGORIES for line in stream_lines):
            continue
        letters.append(_build(application, decision, programme, stream,
                              stream_lines, student, term))
    return letters


def _build(application, decision, programme, stream, lines, student, term) -> dict:
    """One programme's letter, as data. Rendering is somebody else's job."""
    by_category: dict[str, list[Award]] = {}
    for line in lines:
        by_category.setdefault(line.category, []).append(line)

    rows = []
    for category, label in programme['rows']:
        category_lines = by_category.pop(category, [])
        if not category_lines:
            continue
        amount = sum((line.amount for line in category_lines), ZERO)
        row = {'label': label, 'amount': _money(amount), 'note': ''}
        if category == 'living':
            notes = [note for note in (_allowance_note(l) for l in category_lines) if note]
            row['note'] = ' + '.join(notes)
        if category == 'tuition' and programme.get('tuition_qualifier_rate'):
            cap = _rate(*programme['tuition_qualifier_rate'])
            if cap:
                row['note'] = programme['tuition_qualifier'].format(cap=cap)
        rows.append(row)

    # Anything the programme's own table has no row for — a travel claim, a
    # bursary — is still money this decision awarded, and a letter whose total
    # excluded it would disagree with the award. It is listed under the office's
    # own name for the category rather than silently dropped.
    for category, category_lines in by_category.items():
        rows.append({
            'label': dict(Award.Category.choices).get(category, category),
            'amount': _money(sum((line.amount for line in category_lines), ZERO)),
            'note': '',
        })

    total = sum((line.amount for line in lines), ZERO)
    footnote = ''
    if programme['footnote'] and programme['footnote_rate']:
        cap = _rate(*programme['footnote_rate'])
        if cap:
            footnote = programme['footnote'].format(cap=cap)

    return {
        'application_id': application.pk,
        'stream': stream,
        'programme_code': programme['code'],
        'title': programme['title'],
        # Empty where the title does not invite it — see `term_in_title`.
        'term': term if programme['term_in_title'] else '',
        # Only the DGGR template carries a date. Empty elsewhere rather than
        # printed where the office's letter has no line for it.
        'date': (decision.created_at.date().isoformat()
                 if programme['shows_date'] else ''),
        'identifier': _identifier(student, programme['identifier']),
        'recipient': _recipient(application),
        # Posted as well as emailed — see `_address_lines`.
        'address_lines': _address_lines(application, student),
        'opening': programme['opening'],
        'breakdown_lead': 'The following is a breakdown of the funds that you have been approved:',
        'semester': _semester_label(application.semester) if application.semester else '',
        'rows': rows,
        'total_label': programme['total_label'],
        'total': _money(total),
        'footnote': footnote,
        'paragraphs': list(programme['paragraphs']),
        'closing': 'Kind regards,',
        'signatory': signatory(),
        'office': office(),
    }


# ── The letter as an email ──────────────────────────────────────────────────
#
# A second renderer, deliberately: mail clients are not browsers, so the emailed
# copy is a table with inline styles while the portal's is a stylesheet. What is
# *not* duplicated is the letter itself — both render the same dict from
# `letters_for`, so the copy in somebody's inbox and the copy they print from
# the portal cannot say different things about what they were awarded.

def _cell(content: str, *, bold: bool = False, align: str = 'left') -> str:
    weight = 'font-weight:bold;' if bold else ''
    return (f'<td style="border:1px solid #999;padding:6px 8px;font-size:13px;'
            f'text-align:{align};{weight}">{content}</td>')


def render_email(letter: dict) -> str:
    """One programme's letter, as HTML a mail client will render.

    No logo image: mail clients block remote images by default and inline SVG is
    unsupported in most of them, so a letterhead here would be a broken picture
    above the office's name. The wordmark is set in text instead, and the
    printable copy in the portal carries the real letterhead.
    """
    from django.utils.html import escape

    rows = []
    for index, row in enumerate(letter['rows']):
        semester = escape(letter['semester']) if index == 0 else ''
        amount = escape(row['amount'])
        if row['note']:
            amount += (f'<div style="font-size:11px;color:#555;">'
                       f'{escape(row["note"])}</div>')
        rows.append('<tr>' + _cell(semester) + _cell(escape(row['label']))
                    + _cell(amount, align='right') + '</tr>')

    if letter['total_label']:
        rows.append('<tr>' + _cell('')
                    + _cell(escape(letter['total_label']), bold=True)
                    + _cell(escape(letter['total']), bold=True, align='right')
                    + '</tr>')

    paragraphs = ''.join(
        f'<p style="margin:0 0 12px;line-height:1.5;">{escape(text)}</p>'
        for text in letter['paragraphs'])

    identifier = letter['identifier']
    footnote = (f'<p style="font-size:11px;color:#555;margin:6px 0 16px;">'
                f'*{escape(letter["footnote"])}</p>') if letter['footnote'] else ''

    signatory, office = letter['signatory'], letter['office']
    date_line = (f'<p style="margin:0 0 6px;font-size:13px;">Date: '
                 f'{escape(letter["date"])}</p>') if letter['date'] else ''

    return (
        date_line
        + f'<p style="text-align:right;margin:0 0 18px;font-size:13px;">'
        f'{escape(identifier["label"])} {escape(identifier["value"])}</p>'
        f'<p style="font-weight:bold;margin:0 0 14px;line-height:1.4;">'
        f'RE: {escape(letter["title"])} {escape(letter["term"])}</p>'
        f'<p style="margin:0 0 12px;">Dear {escape(letter["recipient"])}</p>'
        f'<p style="margin:0 0 12px;line-height:1.5;">{escape(letter["opening"])}</p>'
        f'<p style="margin:0 0 8px;">{escape(letter["breakdown_lead"])}</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;width:100%;margin:0 0 4px;">'
        '<tr>' + _cell('<strong>Semester</strong>')
        + _cell('<strong>Type of Assistance</strong>')
        + _cell('<strong>Amount</strong>', align='right') + '</tr>'
        + ''.join(rows) + '</table>'
        + footnote + paragraphs
        + f'<p style="margin:24px 0 4px;">{escape(letter["closing"])}</p>'
        f'<p style="margin:0;line-height:1.5;">{escape(signatory["name"])}<br>'
        f'{escape(signatory["title"])}<br>{escape(signatory["organisation"])}<br>'
        f'Email: {escape(signatory["email"])}</p>'
        f'<p style="margin:18px 0 0;font-size:11px;color:#555;border-top:1px solid #ddd;'
        f'padding-top:10px;">{escape(office["address"])} &nbsp;|&nbsp; Office: '
        f'{escape(office["phone"])} &nbsp;|&nbsp; {escape(office["website"])}</p>'
    )
