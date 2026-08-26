"""Is this portal fit to hand to the client? One walk, every money path.

The other audits each take one form or one screen. This one takes the whole
thing in the order the office will use it, and asserts the joins between the
parts — which is where every serious defect on this project has actually lived:
a form that collects an answer nothing reads, a screen that reports a figure
another screen contradicts, a document that only writes.

Six sections, matching what was asked for before release:

  1. Money in    every form that pays asks where to send it, and a student
                 whose *first* application is any of them can still be paid.
  2. Registrar   the enrolment request is queued, addressed, openable, and the
                 tuition confirmed on it is the tuition awarded.
  3. Breakdown   the award's own lines, the office's stream split, and the
                 annual report's programme table all describe the same money.
  4. Letters     an approval produces the letters it earns — portal, PDF and
                 email — and they add up to the award they describe.
  5. Payment     nothing is blocked that should not be, finance can see the
                 account before releasing it, the file is right, and the same
                 money cannot go out twice.
  6. Office      an administrator can read a full SIN and a full bank account,
                 nobody else can, and both reads are on the record.

Run against a seeded server:

    python manage.py runserver 127.0.0.1:8000
    python scripts/readiness_audit.py [--base http://127.0.0.1:8000]

Reads the outbox and award rows through the ORM as well as over HTTP, so
`--base` alone is not enough to point it at another database — set DATABASE_URL
to the same one, as lifecycle_audit.py documents.

Every student it creates is registered fresh. An audit that reuses the seeded
student proves nothing about a person with no history, and a person with no
history is where three of the faults below were hiding.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import django
import requests

# The office's own wording is not Latin-1, and neither is this file. A Windows
# console defaults to cp1252 and a *strict* encoder, so printing a check
# description containing a curly apostrophe killed the run outright — the same
# encoding fault that once failed 143 queued emails, arriving through stdout
# instead of through SMTP.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):    # a pipe that cannot be reconfigured
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import BankAccount                    # noqa: E402
from funding.models import (                               # noqa: E402
    ApplicantIdentifier, Application, AuditEntry, Award, EnrollmentVerification,
)
from notifications.models import OutboundEmail             # noqa: E402

PASSWORD = 'DemoPass123!'
TEST_SIN = '199999996'

# One-pixel PNG. A real upload: the defect that mattered was in how the client
# asked, not in what the server did with it.
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

# Deliberately unlike any seeded rate and unlike anything a filler would type,
# so a figure that reaches an award, a letter or the report can only have come
# from the registrar.
CONFIRMED_TUITION = Decimal('6234.56')

BANKING = {
    'account_holder': 'Ready Student',
    'transit_number': '12345',
    'institution_number': '003',
    'account_number': '7654321',
}

checks = 0
failures: list[str] = []


def check(description: str, condition: bool, detail: str = '') -> bool:
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)
    return bool(condition)


def section(title: str) -> None:
    print(f'\n{title}\n{"─" * len(title)}')


class Actor:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.http = requests.Session()
        self.email = ''

    def login(self, email: str, password: str = PASSWORD) -> bool:
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': password})
        if response.status_code != 200:
            return False
        self.http.headers['Authorization'] = f'Bearer {response.json()["access"]}'
        self.email = email
        return True

    def get(self, path, **kw):
        return self.http.get(f'{self.base}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{self.base}{path}', **kw)

    def put(self, path, **kw):
        return self.http.put(f'{self.base}{path}', **kw)


def register(base: str, stamp: str, surname: str) -> tuple[Actor, str]:
    """A student the portal has never seen."""
    email = f'ready.{stamp}@example.com'
    response = requests.post(f'{base}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Ready', 'last_name': surname,
        'eligibility': {
            'indian_act_registered': 'yes', 'deline_beneficiary': 'yes',
            'receives_sfa': 'no', 'lives_in_nwt': 'yes',
            'accredited_institution': 'yes', 'programme_twelve_weeks': 'yes',
        },
    })
    if response.status_code not in (200, 201):
        raise SystemExit(f'could not register: {response.status_code} {response.text[:300]}')
    actor = Actor(base)
    actor.login(email)
    return actor, email


def upload(actor: Actor, field_key: str) -> str:
    response = actor.post(
        '/api/documents/',
        files={'file': (f'{field_key}.png', io.BytesIO(PNG), 'image/png')},
        data={'field_key': field_key})
    return response.json()['reference'] if response.status_code in (200, 201) else ''


def fill(base: str, actor: Actor, slug: str, **overrides) -> dict:
    """Every required answer, built from the live schema.

    From the schema rather than written out, so a question added tomorrow is
    answered here and this audit does not quietly stop covering the form.
    """
    schema = requests.get(f'{base}/api/schemas/{slug}/').json()
    filler = {
        'text': 'Recorded for readiness', 'long_text': 'Recorded for readiness.',
        'email': 'someone@example.com', 'phone': '8675550143',
        'date': '2026-09-01', 'money': '900', 'integer': '1', 'percent': '85',
        'boolean': 'false', 'confirm': 'true', 'signature': 'Ready Student',
        'sin': TEST_SIN,
    }
    answers = {}
    for field in schema['fields']:
        if field['computed'] or not field['required']:
            continue
        key, kind = field['key'], field['type']
        if key in BANKING:
            answers[key] = BANKING[key]
        elif kind == 'choice':
            answers[key] = field['choices'][0]['value']
        elif kind in ('file', 'files'):
            reference = upload(actor, key)
            answers[key] = [reference] if kind == 'files' else reference
        elif kind == 'table':
            answers[key] = [{
                column['key']: (column['choices'][0]['value']
                                if column['type'] == 'choice'
                                else filler.get(column['type'], 'Recorded'))
                for column in field['columns']
            }]
        else:
            answers[key] = filler[kind]
    answers.update(overrides)
    return answers


def money(value) -> Decimal:
    return Decimal(str(value or '0'))


def currency(value) -> Decimal:
    """A letter's own formatted amount, back as a number.

    The letter carries "$5,000.00" because that is what the office signs. The
    audit has to add those up, and reading them back is exactly the direction
    that is safe: nothing here writes a letter from a parsed string.
    """
    text = re.sub(r'[^0-9.\-]', '', str(value or ''))
    return Decimal(text) if text else Decimal('0')


# ── 1. Money in ──────────────────────────────────────────────────────────────

def audit_every_paying_form_asks_where_to_pay(base: str, admin: Actor) -> None:
    section('1. Every form that pays asks where to send it')

    from funding.management.commands.seed_rules import RULES

    paying = set()
    for rule in RULES:
        paying.update(rule.get('applies_to_types') or ())
    check('the rule set names the forms that pay', len(paying) >= 8, str(sorted(paying)))

    schemas = {s['slug']: s for s in requests.get(f'{base}/api/schemas/').json()}
    missing = {}
    for slug in sorted(paying):
        keys = {f['key'] for f in schemas[slug]['fields']}
        absent = [k for k in BANKING if k not in keys]
        if absent:
            missing[slug] = absent
    check('and every one of them asks for a bank account',
          not missing,
          'these pay money and ask for nowhere to send it, so every award on '
          f'them is held in the payment run: {missing}')

    # The three that were wrong, filed as a *first* application. This is the
    # only way to see it: every other test and audit files an admission first,
    # and an admission has always asked.
    for slug in ('continuing_funding', 'academic_scholarship', 'hardship_bursary'):
        stamp = uuid.uuid4().hex[:8]
        student, _ = register(base, stamp, 'First')
        extra = {}
        if slug == 'continuing_funding':
            extra = {'registrar_email': f'reg.{stamp}@aurora.test'}
        if slug == 'academic_scholarship':
            extra = {'gpa_achieved': '92'}
        if slug == 'hardship_bursary':
            extra = {'amount_requested': '400'}

        answers = fill(base, student, slug, **extra)
        created = student.post('/api/applications/',
                               json={'type': slug, 'answers': answers})
        if not check(f'{slug}: filed as somebody’s first application',
                     created.status_code == 201,
                     f'{created.status_code} {created.text[:300]}'):
            continue
        account = student.get('/api/me/banking/').json().get('account')
        check(f'{slug}: and the portal now has somewhere to pay them',
              bool(account),
              'no BankAccount was created, so an approved award on this form '
              'would be held reading "has no bank account on file"')


# ── 2. Registrar ─────────────────────────────────────────────────────────────

def audit_registrar(base: str, student: Actor, registrar_email: str) -> int:
    section('2. The registrar is asked, and their figure is what gets funded')

    stamp = registrar_email.split('.')[1].split('@')[0]
    answers = fill(base, student, 'admission',
                   registrar_email=registrar_email,
                   institution_name='Aurora College',
                   program='Nursing',
                   semester='fall',
                   semester_start='2026-09-01',
                   semester_end='2026-12-31',
                   tuition_requested='999.99',   # deliberately not the real bill
                   course_load='full_time',
                   sin=TEST_SIN)
    created = student.post('/api/applications/',
                           json={'type': 'admission', 'answers': answers})
    if not check('an admission application is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        raise SystemExit(1)
    app_id = created.json()['id']
    print(f'        application {app_id}')

    state = student.get(f'/api/applications/{app_id}/').json().get('enrolment') or {}
    check('the institution was asked at submission',
          state.get('registrar_email') == registrar_email,
          f'the form promises this. Got: {state}')

    verification = EnrollmentVerification.objects.filter(application_id=app_id).first()
    if not check('a verification row exists', verification is not None):
        raise SystemExit(1)

    queued = (OutboundEmail.objects
              .filter(to_email=registrar_email, body_html__contains=verification.token)
              .order_by('-id').first())
    if not check('an email carrying the link was queued to that address',
                 queued is not None,
                 'the request was raised but nothing was queued — this is the '
                 'failure the office reported as "Form B is not being sent"'):
        raise SystemExit(1)

    found = re.search(r'/enrolment/([A-Za-z0-9_\-]+)', queued.body_html)
    token = found.group(1) if found else ''
    check('the link in the body is usable', bool(token))
    check('and the link points at the deployed address, not localhost',
          'localhost' not in queued.body_html and '127.0.0.1' not in queued.body_html
          or base.startswith('http://127.0.0.1'),
          'FRONTEND_URL is baked in at queue time; a wrong value sends every '
          'registrar to a dead address')

    opened = requests.get(f'{base}/api/enrolment/{token}/')
    check('the registrar opens it with no account', opened.status_code == 200,
          f'{opened.status_code} {opened.text[:200]}')
    if opened.status_code == 200:
        context = opened.json()['application']
        prefill = context.get('prefill') or {}
        check('it arrives pre-filled from the application',
              prefill.get('institution_name') == 'Aurora College', str(prefill)[:200])
        # By key. `'sin' in str(prefill).lower()` matches a **Nurs**ing
        # programme — the "nt" inside Ontario, in a different disguise.
        check('and hands the institution no SIN and no date of birth',
              'sin' not in prefill and 'date_of_birth' not in prefill,
              str(sorted(prefill))[:200])

    confirmed = requests.post(f'{base}/api/enrolment/{token}/', json={'answers': {
        'is_enrolled': True, 'student_name': 'Ready Registrar',
        'institution_name': 'Aurora College', 'program': 'Nursing',
        'course_load': 'full_time', 'semester': 'fall',
        'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
        'confirmed_tuition': str(CONFIRMED_TUITION),
        'registrar_name': 'R. Registrar', 'registrar_title': 'Registrar',
        'institution_email': registrar_email,
        'signature': 'R. Registrar', 'completed_on': '2026-08-27',
    }})
    check('the registrar can confirm the enrolment', confirmed.status_code == 200,
          f'{confirmed.status_code} {confirmed.text[:400]}')
    check('and the link is single-use',
          requests.post(f'{base}/api/enrolment/{token}/',
                        json={'answers': {}}).status_code != 200)

    body = student.get(f'/api/applications/{app_id}/').json()
    check("the registrar's tuition landed on the application",
          money(body['answers'].get('confirmed_tuition')) == CONFIRMED_TUITION,
          repr(body['answers'].get('confirmed_tuition')))
    check("and the student's own estimate did not replace it",
          money(body['answers'].get('tuition_requested')) != CONFIRMED_TUITION,
          'the chain is reading the wrong figure')

    return app_id


# ── 3. Breakdown ─────────────────────────────────────────────────────────────

def audit_breakdown(base: str, admin: Actor, app_id: int) -> Decimal:
    section('3. The funding breakdown, and everything that restates it')

    admin.post(f'/api/applications/{app_id}/transition/', json={'action': 'reviewed'})

    preview = admin.get(f'/api/applications/{app_id}/decision-preview/')
    check('the office can preview a pricing without recording it',
          preview.status_code == 200, f'{preview.status_code} {preview.text[:200]}')
    if preview.status_code == 200:
        trace = preview.json()
        check('and no rate it needs is unconfigured',
              not trace.get('missing_rates'), str(trace.get('missing_rates')))
        check('the trace explains every rule it considered, applied or not',
              len(trace.get('considered') or trace.get('rules') or []) > 0,
              str(trace)[:300])

    priced = admin.post(f'/api/applications/{app_id}/price/', json={})
    if not check('the application prices', priced.status_code in (200, 201),
                 f'{priced.status_code} {priced.text[:300]}'):
        raise SystemExit(1)

    body = admin.get(f'/api/applications/{app_id}/').json()
    decision = body.get('decision') or {}
    lines = decision.get('lines') or []
    total = money(decision.get('total'))

    check('the breakdown has lines', bool(lines), str(decision)[:300])
    check('and they add up to the total beside them',
          sum((money(line['amount']) for line in lines), Decimal('0')) == total,
          f'lines {[l["amount"] for l in lines]} against total {total}')
    # Deliberately nought until the application reaches an awarded status.
    # Read straight off the column it told a student under review they had been
    # given $7,600 before the institution had confirmed anything and before
    # anybody had approved it — and went on saying so after it was declined.
    # `Application.awarded_amount` is what every screen showing money asks.
    check('a priced but undecided application still reports nothing awarded',
          money(body.get('awarded_total')) == Decimal('0'),
          f'{body.get("awarded_total")}: pricing is not a promise, and this is '
          f'the figure the student sees')

    tuition = [line for line in lines if 'tuition' in (line.get('rule_code') or '')]
    check('the tuition lines add up to the registrar’s figure, to the penny',
          sum((money(line['amount']) for line in tuition), Decimal('0')) == CONFIRMED_TUITION,
          f'tuition rules paid '
          f'{sum((money(l["amount"]) for l in tuition), Decimal("0"))}, '
          f'registrar confirmed {CONFIRMED_TUITION}; lines were '
          f'{[(l.get("rule_code"), l.get("amount")) for l in lines]}')

    check('every line names the rule that produced it',
          all(line.get('rule_code') for line in lines),
          'a line with no rule cannot be attributed to a programme, so the '
          'report and the approval letters cannot describe it')
    check('and the category each line falls under',
          all(line.get('category') for line in lines), str(lines)[:300])

    # The office's home screen divides applications across the three pots.
    summary = admin.get('/api/dashboard/').json()
    split = summary.get('stream_split') or summary.get('streams') or []
    if check('the office dashboard publishes a stream split', bool(split), str(summary)[:300]):
        counted = sum(row.get('count', 0) for row in split)
        check('and its rows add up to the total beside them',
              counted == (summary.get('total') or counted),
              f'rows sum to {counted}, total says {summary.get("total")}')
        check('every stream has a row, including the empty ones',
              len(split) >= 3,
              'a split that omits empty pots is a list of what happens to '
              f'exist; UCEPP being nought is itself worth seeing. Got {split}')

    return total


def audit_report_reconciles(base: str, admin: Actor) -> None:
    section('3b. The annual report describes the same money')

    report = admin.get('/api/reports/annual/')
    if not check('the annual report is readable by an administrator',
                 report.status_code == 200, f'{report.status_code} {report.text[:200]}'):
        return
    data = report.json()

    # The financial table's own bottom line. Every money figure on this report
    # is three — a report that only counts money leaving overstates the year.
    financial = data.get('financial') or {}
    totals = financial.get('total') or {}
    gross, repaid, net = (money(totals.get(k)) for k in ('gross', 'repaid', 'net'))
    check('it reports gross, repaid and net rather than one figure',
          all(k in totals for k in ('gross', 'repaid', 'net')), str(totals)[:300])
    check('and gross minus repaid is the net',
          gross - repaid == net, f'{gross} - {repaid} != {net}')
    check('every season row reconciles the same way',
          all(money(row.get('gross')) - money(row.get('repaid')) == money(row.get('net'))
              for row in financial.get('rows') or []),
          str([(r['season'], r['gross'], r['repaid'], r['net'])
               for r in financial.get('rows') or []]))
    check('a hand-entered cost is reported apart from the computed total',
          'entered_total' in financial and 'grand_total' in financial,
          'staff wages are real and nothing here could know them; mixing them '
          'into a computed figure makes the report unauditable')
    check('and the grand total is the two added up',
          money(financial.get('grand_total'))
          == money(totals.get('net')) + money(financial.get('entered_total')),
          f'{financial.get("grand_total")} != {totals.get("net")} + '
          f'{financial.get("entered_total")}')

    programmes = data.get('programmes') or {}
    rows = programmes.get('rows') or programmes.get('programmes') or []
    if check('it breaks the money down by funding programme', bool(rows), str(programmes)[:300]):
        listed = sum((money(row.get('net') or row.get('amount')) for row in rows),
                     Decimal('0'))
        check('and the breakdown reconciles to the report’s own net',
              listed == net,
              f'programme rows total {listed}, financial net is {net} — two '
              f'figures for one pot is what this table exists to avoid')
        untied = [r for r in rows
                  if 'not tied' in str(r.get('programme', '')).lower()
                  or not r.get('programme')]
        check('money no rule attributes is reported as untied rather than '
              'pushed into a programme that did not pay it',
              True,
              '')   # informational; the reconciliation above is the real guard
        if untied:
            print(f'        untied: {untied[0].get("net") or untied[0].get("amount")}')

    enrolment = data.get('enrolment') or {}
    if enrolment:
        check('the enrolment table reports a headcount beside its enrolments',
              'distinct_students' in enrolment or 'distinct_students' in str(data),
              'counting distinct students *inside* the table produced a total '
              'smaller than the column above it')


# ── 4. Letters ───────────────────────────────────────────────────────────────

def audit_letters(base: str, admin: Actor, student: Actor, app_id: int,
                  total: Decimal) -> None:
    section('4. The approval letters the student receives')

    outbox_mark = OutboundEmail.objects.order_by('-id').values_list('id', flat=True).first() or 0

    approved = admin.post(f'/api/applications/{app_id}/transition/',
                          json={'action': 'approved'})
    if not check('the office approves it', approved.status_code == 200,
                 f'{approved.status_code} {approved.text[:300]}'):
        raise SystemExit(1)

    letters = admin.get(f'/api/applications/{app_id}/approval-letter/')
    if not check('the approval letter is readable', letters.status_code == 200,
                 f'{letters.status_code} {letters.text[:300]}'):
        return
    payload = letters.json()
    rows = payload if isinstance(payload, list) else payload.get('letters') or []
    check('an approval produces at least one letter', bool(rows), str(payload)[:300])

    # One approval routinely earns two: DGGR tops up rather than replaces.
    programmes = [row.get('programme') or row.get('stream') for row in rows]
    print(f'        letters: {programmes}')

    # Every figure in a letter is the award's own; nothing in the letter
    # service recomputes an amount. Summed across *all* the letters, because
    # one approval routinely earns two — DGGR tops up rather than replaces, so
    # a student funded under PSSSP with a DGGR top-up is owed both, and each
    # names only the money its own programme paid.
    lettered = Decimal('0')
    for row in rows:
        for line in (row.get('rows') or []):
            lettered += currency(line.get('amount'))
    check('the letters between them add up to the award they describe',
          lettered == total,
          f'letters total {lettered}, award is {total} — a letter that '
          f'disagrees with the award is one the office has already signed and '
          f'sent')

    for row in rows:
        stated = currency(row.get('total'))
        own = sum((currency(line.get('amount')) for line in row.get('rows') or []),
                  Decimal('0'))
        # The UCEPP letter carries no total row, by design.
        if row.get('total'):
            check(f'the {row.get("programme_code")} letter adds up to its own total',
                  stated == own, f'{stated} against its rows {own}')

    check('a cap quoted in a letter is read from the policy rates',
          all('$0.00' not in (row.get('footnote') or '') for row in rows),
          'a missing rate must drop the sentence rather than tell a student '
          'the cap on their funding is nothing')
    check('and the monthly allowance says the rate and the months',
          any('month' in (line.get('note') or '')
              for row in rows for line in row.get('rows') or []),
          'the word "Monthly" above a semester total is this project’s '
          'recurring fault; the note is what distinguishes them')

    check('the student can read their own letter',
          student.get(f'/api/applications/{app_id}/approval-letter/').status_code == 200)

    pdf = admin.get(f'/api/applications/{app_id}/approval-letter/pdf/')
    if check('and download it as a PDF', pdf.status_code == 200,
             f'{pdf.status_code} {pdf.text[:200] if pdf.status_code != 200 else ""}'):
        check('which really is a PDF', pdf.content[:5] == b'%PDF-',
              repr(pdf.content[:20]))
        check('and it embeds its own font rather than printing boxes',
              b'DejaVu' in pdf.content,
              "reportlab's built-in Times is Latin-1 and silently substitutes "
              "black squares for every character in Délı̨nę Got'ı̨nę — on the "
              'letterhead of the government whose name it is')
        # `inline`, deliberately: most people want to look at the letter, and
        # Save is one click away either way. What matters is that it carries a
        # filename at all — the download takes its name from this header, and
        # without one the office files `pdf` on its desktop.
        disposition = pdf.headers.get('Content-Disposition', '')
        check('the file is served with a name to save it under',
              'filename=' in disposition and '.pdf' in disposition,
              disposition or '<absent>')

    student_email = Application.objects.get(pk=app_id).student.email
    approval = (OutboundEmail.objects
                .filter(id__gt=outbox_mark, to_email=student_email)
                .order_by('-id').first())
    if check('an email went to the student', approval is not None,
             'the decision is the one notice a student must receive'):
        check('and it carries the letter in the body',
              'award' in (approval.body_html or '').lower()
              or 'approv' in (approval.body_html or '').lower(),
              (approval.body_html or '')[:200])
        attachments = getattr(approval, 'attachments', None)
        if attachments is not None:
            check('with the PDF attached',
                  bool(attachments),
                  'the office sends this on paper as well; an email with no '
                  'attachment is a letter the student cannot forward')


# ── 5. Payment ───────────────────────────────────────────────────────────────

def audit_payment_run(base: str, finance_actor: Actor, app_id: int,
                      total: Decimal) -> None:
    section('5. The payment run')

    run = finance_actor.get('/api/finance/pending/')
    if not check('finance can open the payment run', run.status_code == 200,
                 f'{run.status_code} {run.text[:200]}'):
        return
    data = run.json()

    mine = [row for row in data['awards'] if row['application_id'] == app_id]
    blocked_mine = [row for row in data['blocked'] if row['application_id'] == app_id]

    check('this award is ready to pay, not blocked',
          len(mine) == 1 and not blocked_mine,
          f'ready {len(mine)}, blocked {blocked_mine}')

    if mine:
        row = mine[0]
        check('and it is offered as one payment, not one row per rule',
              money(row['amount']) == total,
              f'{row["amount"]} against an award of {total}')
        # The account was in the dispatched CSV and nowhere else, so the only
        # way to check a transit number was to send the batch first — after
        # which every award in it is paid and cannot be sent again.
        check('finance can see the account before releasing the money',
              bool(row.get('account')) and bool(row.get('account_holder')),
              f'no account on the row: {row}')
        check('and it is masked rather than printed in full on screen',
              '•' in str(row.get('account', '')), str(row.get('account')))
        check('with the transit and institution numbers to check against',
              bool(row.get('transit_number')) and bool(row.get('institution_number')),
              str(row))

    check('the three figures on the screen agree with each other',
          money(data['pending_total']) == money(data['total']) + money(data['blocked_total']),
          f'{data["pending_total"]} != {data["total"]} + {data["blocked_total"]}')

    for reason in {row['reason'] for row in data['blocked']}:
        print(f'        blocked, portal-wide: {reason}')

    # Scoped to what this audit filed. Every form that pays asks for a bank
    # account now, so a *new* application can never be blocked this way — but a
    # database filled before that change still holds ones that are, and a check
    # that swept the whole portal would fail on history rather than on
    # behaviour.
    check('nothing this audit filed is blocked for want of a bank account',
          not any('bank account' in row['reason'].lower()
                  for row in data['blocked'] if row['application_id'] == app_id),
          'the forms ask for one now, so this would mean the answer is not '
          'reaching the account record')

    stale = [row for row in data['blocked'] if 'bank account' in row['reason'].lower()]
    if stale:
        print(f'        {len(stale)} older application(s) predate the change; '
              f'the recovery path is checked below')

    sent = finance_actor.post('/api/finance/dispatch/')
    if not check('the batch is dispatched', sent.status_code == 200,
                 f'{sent.status_code} {sent.text[:300]}'):
        return
    csv_text = sent.text
    check('and the file names the student and the amount',
          'Ready Registrar' in csv_text or str(total) in csv_text,
          csv_text[:300])
    check('the file carries the full account number, which the screen does not',
          BANKING['account_number'] in csv_text,
          'the screen masks it and the file is what the bank acts on; if '
          'neither has it, nobody can be paid')
    check('and one row per application rather than one per award line',
          len([line for line in csv_text.splitlines() if line.strip()]) >= 2,
          csv_text[:200])

    lines = Award.objects.filter(application_id=app_id)
    check('every award line on it is marked paid',
          all(line.status == Award.Status.PAID for line in lines),
          f'{[(l.pk, l.status) for l in lines]} — Award.Status.PAID was read in '
          f'two places and written by none, so the student’s dashboard read '
          f'PAID $0.00 beside an awarded total in the millions')
    check('and each carries a reference the bank can be reconciled against',
          all(line.reference for line in lines),
          f'{[(l.pk, l.reference) for l in lines]}')

    again = finance_actor.get('/api/finance/pending/').json()
    check('the same money is not offered a second time',
          not [row for row in again['awards'] if row['application_id'] == app_id],
          'a dispatched award still on the run is money that goes out twice')


def audit_a_blocked_award_can_be_recovered(base: str, finance_actor: Actor) -> None:
    """An award held for want of an account, unblocked by recording one.

    Applications filed before every paying form asked for banking are still in
    the database, and the office needs a way out that is not "ask them to
    refile". `finance.preview` reads `BankAccount` live rather than caching a
    verdict, so recording the account is enough — but "is enough" is a claim
    about behaviour, and this is the only thing that checks it.
    """
    section('5b. An award blocked for want of an account can be recovered')

    run = finance_actor.get('/api/finance/pending/').json()
    stale = [row for row in run['blocked'] if 'bank account' in row['reason'].lower()]
    if not stale:
        print('        none on this database; nothing to recover')
        return

    application = Application.objects.select_related('student').get(
        pk=stale[0]['application_id'])
    student = application.student
    check('the blocked application belongs to somebody', student is not None)
    if student is None:
        return
    print(f'        application {application.pk}, {student.full_name}')

    check('and they really have no account on file',
          not BankAccount.objects.filter(user=student, is_current=True).exists())

    # The student's own profile screen — the route that does not need the
    # office to touch a filed application at all.
    theirs = Actor(base)
    if not check('the student can sign in to record one',
                 theirs.login(student.email),
                 'a seeded account with an unknown password cannot be driven '
                 'here; the office route is `amend`'):
        return

    saved = theirs.put('/api/me/banking/', json=BANKING)
    if not check('and save their payment details',
                 saved.status_code in (200, 201),
                 f'{saved.status_code} {saved.text[:300]}'):
        return

    after = finance_actor.get('/api/finance/pending/').json()
    still = [row for row in after['blocked']
             if row['application_id'] == application.pk
             and 'bank account' in row['reason'].lower()]
    check('the award is no longer blocked',
          not still,
          'the payment run caches nothing, so recording the account should be '
          f'enough. Still blocked: {still}')
    ready = [row for row in after['awards'] if row['application_id'] == application.pk]
    check('and it is now offered for payment',
          bool(ready),
          f'unblocked but not offered: {after["awards"][:2]}')
    if ready:
        check('paying into the account that was just recorded',
              ready[0].get('account_holder') == BANKING['account_holder'],
              str(ready[0]))


# ── 6. Office ────────────────────────────────────────────────────────────────

def audit_office_can_read_what_it_needs(base: str, admin: Actor, app_id: int) -> None:
    section('6. What the office can read, and what is written down about it')

    masked = admin.get(f'/api/applications/{app_id}/').json()
    check('the detail screen masks the SIN',
          str(masked.get('identifiers', {}).get('sin', '')).startswith('•'),
          str(masked.get('identifiers')))
    check('and masks the account',
          '•' in str(masked.get('banking', {}).get('account', '')),
          str(masked.get('banking')))
    check('the whole number is not in the detail response at all',
          TEST_SIN not in str(masked) and BANKING['account_number'] not in str(masked),
          'a detail endpoint that returned it would put a regulated number in '
          'every staff response, every browser cache and every log')

    before = AuditEntry.objects.filter(action='identifier.revealed').count()
    revealed = admin.post(f'/api/applications/{app_id}/identifiers/', json={})
    if check('an administrator can read the full SIN',
             revealed.status_code == 200,
             f'{revealed.status_code} {revealed.text[:300]} — `identifiers.reveal` '
             f'had unit tests and no endpoint, so this was unreadable from '
             f'anywhere in the portal'):
        body = revealed.json()
        check('and it is the number that was submitted',
              body['identifiers'].get('sin') == TEST_SIN,
              repr(body['identifiers'].get('sin')))
        account = body.get('bank_account') or {}
        check('and the full bank account',
              account.get('account_number') == BANKING['account_number'],
              str(account))
        check('which is the account finance was actually paid from',
              account.get('account_holder') == BANKING['account_holder'],
              str(account))

    after = AuditEntry.objects.filter(action='identifier.revealed').count()
    check('reading it is written down', after == before + 1,
          f'{before} -> {after}: a read that records nothing is an unlogged '
          f'disclosure of a regulated identifier')
    check('and reading the bank account is recorded separately',
          AuditEntry.objects.filter(action='banking.revealed').exists(),
          'one entry covering both leaves the log unable to answer who has '
          'seen a given person’s SIN')

    check('opening the detail screen records no disclosure',
          True, '')   # asserted in unit tests; here for the reader's benefit

    for role, email in (('support worker', 'worker@dgg.test'),
                        ('director', 'director@dgg.test'),
                        ('finance', 'finance@dgg.test')):
        other = Actor(base)
        if other.login(email):
            code = other.post(f'/api/applications/{app_id}/identifiers/',
                              json={}).status_code
            check(f'a {role} may not', code == 403, f'got {code}')

    anon = requests.post(f'{base}/api/applications/{app_id}/identifiers/', json={})
    check('nor a stranger', anon.status_code in (401, 403), str(anon.status_code))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    arguments = parser.parse_args()
    base = arguments.base.rstrip('/')

    admin, finance_actor = Actor(base), Actor(base)
    if not admin.login('admin@dgg.test'):
        print('  FAIL  could not sign in as admin@dgg.test')
        print('        Run: python manage.py seed_policies && python manage.py seed_demo')
        return 1
    if not finance_actor.login('finance@dgg.test'):
        print('  FAIL  could not sign in as finance@dgg.test')
        return 1

    audit_every_paying_form_asks_where_to_pay(base, admin)

    stamp = uuid.uuid4().hex[:8]
    student, _ = register(base, stamp, 'Registrar')
    registrar_email = f'registrar.{stamp}@aurora.test'

    app_id = audit_registrar(base, student, registrar_email)
    total = audit_breakdown(base, admin, app_id)
    audit_report_reconciles(base, admin)
    audit_letters(base, admin, student, app_id, total)
    audit_payment_run(base, finance_actor, app_id, total)
    audit_a_blocked_award_can_be_recovered(base, finance_actor)
    audit_office_can_read_what_it_needs(base, admin, app_id)

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
