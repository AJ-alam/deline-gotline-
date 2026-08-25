"""One renewal, all the way through, as every role that touches it.

The unit suite tests each service in isolation and the schema tests check the
form's shape. Neither notices when a *seam* breaks: an answer a rule reads that
the form stopped collecting, a figure the reviewer can no longer see, a
registrar link that goes nowhere. Those only show up by walking the whole path
over HTTP as the people who actually walk it.

Drives: student -> registrar -> support worker -> director -> finance -> admin.

    python manage.py runserver 127.0.0.1:8000
    python scripts/lifecycle_audit.py [--base http://127.0.0.1:8000]

The registrar's token is read out of the outbound email queue rather than the
database directly, because that is where a real registrar gets it — which also
proves the email carries a link that works.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
from datetime import date
from decimal import Decimal

import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from funding.test_fixtures import admission_answers  # noqa: E402
from funding.models import Award, EnrollmentVerification  # noqa: E402
from notifications.models import OutboundEmail  # noqa: E402

PASSWORD = 'DemoPass123!'
# Where the office writes when nothing is on file — a renewal by a student
# whose earlier applications are not in the portal has no address to carry.
REGISTRAR_EMAIL = 'registrar@aurora.test'
# Built from the schema, so a field added tomorrow is filled in automatically.
ADMISSION_ANSWERS = admission_answers()
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

checks = 0
failures: list[str] = []
BASE = 'http://127.0.0.1:8000'


def section(title: str) -> None:
    print(f'\n{title}')
    print('-' * len(title))


def check(description: str, condition: bool, detail: str = '') -> bool:
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)
    return bool(condition)


class Role:
    def __init__(self, email: str):
        self.email = email
        self.http = requests.Session()
        response = self.http.post(f'{BASE}/api/auth/token/',
                                  json={'email': email, 'password': PASSWORD})
        self.signed_in = response.status_code == 200 and 'access' in response.json()
        if self.signed_in:
            self.http.headers['Authorization'] = f'Bearer {response.json()["access"]}'

    def get(self, path, **kw):
        return self.http.get(f'{BASE}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{BASE}{path}', **kw)

    def patch(self, path, **kw):
        return self.http.patch(f'{BASE}{path}', **kw)


def anonymous_post(path, **kw):
    return requests.post(f'{BASE}{path}', **kw)


def anonymous_get(path, **kw):
    return requests.get(f'{BASE}{path}', **kw)


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default=BASE)
    arguments = parser.parse_args()
    BASE = arguments.base.rstrip('/')

    section('Signing in as everyone')
    people = {name: Role(f'{name}@dgg.test')
              for name in ('student', 'student2', 'worker', 'director',
                           'finance', 'admin')}
    for name, role in people.items():
        if not check(f'{name} can sign in', role.signed_in):
            print('        Run: python manage.py seed_demo')
            return 1
    student, worker, director, finance, admin = (
        people['student'], people['worker'], people['director'],
        people['finance'], people['admin'])
    # A second student exists so that "one student cannot open another's
    # application" can actually be tried. It used to report that it could not
    # run, every time, which is not a passing check — it is an absent one.
    other_student = people['student2']

    # ── Student ──────────────────────────────────────────────────────────────
    section('Student portal — filing the renewal')

    prefill = student.get('/api/form-prefill/continuing_funding/')
    check('the form opens with what is on file', prefill.status_code == 200,
          f'{prefill.status_code} {prefill.text[:200]}')
    opening = prefill.json().get('answers', {}) if prefill.status_code == 200 else {}

    def upload(field_key):
        response = student.post(
            '/api/documents/',
            files={'file': (f'{field_key}.png', io.BytesIO(PNG), 'image/png')},
            data={'field_key': field_key})
        return response.json()['reference'] if response.status_code in (200, 201) else ''

    answers = {
        'full_name': opening.get('full_name') or 'Majid Khan',
        'beneficiary_number': opening.get('beneficiary_number') or 'DGG-2026-0041',
        'email': opening.get('email') or 'student@dgg.test',
        'institution_name': opening.get('institution_name') or 'Aurora College',
        'program': opening.get('program') or 'Environmental Science',
        'course_load': 'full_time',
        # Two dependants: the engine reads a boolean it no longer collects, so
        # this is the number the dependants rate has to be derived from.
        'dependent_count': 2,
        'semester': 'fall',
        'receives_sfa': False,
        'doc_transcript': upload('doc_transcript'),
        'doc_enrollment_confirmation': upload('doc_enrollment_confirmation'),
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
    }
    # Where the outbox stands before this renewal. The registrar section below
    # takes the first enrolment link queued after this point — later sections
    # file other applications, each raising a verification of its own, and
    # "the newest email" would confirm the wrong one.
    outbox_mark = OutboundEmail.objects.order_by('-id').values_list(
        'id', flat=True).first() or 0

    created = student.post('/api/applications/',
                           json={'type': 'continuing_funding', 'answers': answers})
    if not check('the renewal is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    application = created.json()
    app_id = application['id']
    print(f'        application {app_id}, stream {application["stream"]}')

    check('it is measured against a term, so lateness is decidable',
          application.get('submitted_after_deadline') is not None,
          repr(application.get('submitted_after_deadline')))

    mine = student.get('/api/applications/')
    ids = [row['id'] for row in (mine.json().get('results') or mine.json())]
    check('it appears in the student’s own list', app_id in ids)

    check('a student cannot preview their own award',
          student.get(f'/api/applications/{app_id}/decision-preview/').status_code == 403)
    check('a student cannot price their own award',
          student.post(f'/api/applications/{app_id}/price/').status_code == 403)
    check('a student cannot advance their own application',
          student.post(f'/api/applications/{app_id}/transition/',
                       json={'action': 'reviewed'}).status_code == 403)
    check('a student cannot see the payment run',
          student.get('/api/finance/pending/').status_code == 403)

    section('Bank details — asked for, and kept out of the answers')

    bank = {
        'account_holder': 'Majid Khan', 'transit_number': '12345',
        'institution_number': '001', 'account_number': '9876543210',
    }
    admission_schema = anonymous_get('/api/schemas/admission/').json()
    check('the admission form still asks for them',
          {'account_holder', 'transit_number', 'institution_number',
           'account_number'} <= {f['key'] for f in admission_schema['fields']})

    filed = student.post('/api/applications/', json={
        'type': 'admission',
        'answers': {**ADMISSION_ANSWERS, **bank},
    })
    if check('an admission application carrying them is filed',
             filed.status_code == 201, f'{filed.status_code} {filed.text[:300]}'):
        banked_id = filed.json()['id']
        stored = student.get(f'/api/applications/{banked_id}/')
        check('the account number is nowhere in what the API returns',
              '9876543210' not in stored.text,
              'it is in the detail payload, which every staff role can read')
        check('nor in the answers column itself',
              not any(key in stored.json()['answers'] for key in bank))
        state = stored.json().get('banking') or {}
        check('a reviewer is told an account is on file', state.get('on_file') is True,
              str(state))
        check('shown masked, never in full', state.get('account') == '••••3210',
              str(state))

    # ── Support worker ───────────────────────────────────────────────────────
    section('Support worker portal — review, and the enrolment gate')

    queue = worker.get('/api/applications/?status=submitted')
    check('the queue is filterable and answers the filter',
          queue.status_code == 200
          and all(row['status'] == 'submitted'
                  for row in (queue.json().get('results') or queue.json())),
          f'{queue.status_code} {queue.text[:200]}')

    detail = worker.get(f'/api/applications/{app_id}/')
    check('staff can read the renewal', detail.status_code == 200)
    body = detail.json() if detail.status_code == 200 else {}
    check('the renewal is known to need the institution',
          (body.get('enrolment') or {}).get('required') is True,
          str(body.get('enrolment')))

    # Submission raises the request by itself — but only when a registrar
    # address can be carried from an earlier application, and the renewal form
    # does not ask for one. On an empty database, or for a student whose
    # admission was on paper, there is nothing to carry: the request was
    # skipped in silence and the application could then never be forwarded or
    # approved by anybody. Staff ask directly in that case, which is what this
    # walks. Everything after it is the same either way.
    if not (body.get('enrolment') or {}).get('registrar_email'):
        check('an unasked enrolment says so rather than calling itself not required',
              (body.get('enrolment') or {}).get('status') == 'not_requested',
              str(body.get('enrolment')))
        asked = worker.post(f'/api/applications/{app_id}/request-enrolment/',
                            json={'registrar_email': REGISTRAR_EMAIL})
        check('staff can ask the institution themselves',
              asked.status_code == 200, f'{asked.status_code} {asked.text[:200]}')
        body = worker.get(f'/api/applications/{app_id}/').json()

    check('the enrolment request was raised and addressed',
          (body.get('enrolment') or {}).get('required') is True
          and bool((body.get('enrolment') or {}).get('registrar_email')),
          str(body.get('enrolment')))

    moved = worker.post(f'/api/applications/{app_id}/transition/',
                        json={'action': 'reviewed'})
    check('a worker can start reviewing', moved.status_code == 200,
          f'{moved.status_code} {moved.text[:200]}')

    early = worker.post(f'/api/applications/{app_id}/transition/',
                        json={'action': 'forwarded'})
    check('it cannot be forwarded before the institution confirms',
          early.status_code == 409
          and early.json().get('blocked_by') == 'enrolment_verification',
          f'{early.status_code} {early.text[:200]}')

    check('a worker cannot approve',
          worker.post(f'/api/applications/{app_id}/transition/',
                      json={'action': 'approved'}).status_code == 403)
    check('a worker cannot price',
          worker.post(f'/api/applications/{app_id}/price/').status_code == 403)

    # ── Registrar ────────────────────────────────────────────────────────────
    section('Registrar — the emailed link')

    # Pinned to *this* application's verification, not merely to the first
    # enrolment link queued since the mark. Other applications are filed further
    # down and each raises a request of its own; on a database where the
    # renewal's request is issued by staff — which is what happens when no
    # registrar address can be carried — another application's email is queued
    # first, and the registrar then confirmed somebody else's enrolment while
    # every check downstream reported the renewal unconfirmed.
    issued = EnrollmentVerification.objects.filter(application_id=app_id).first()
    check('a verification exists for this application', issued is not None)
    queued = (OutboundEmail.objects
              .filter(id__gt=outbox_mark, body_html__contains=issued.token)
              .order_by('id').first()) if issued else None
    token = ''
    if check('an email carrying the link was queued', queued is not None):
        found = re.search(r'/enrolment/([A-Za-z0-9_\-]+)', queued.body_html)
        token = found.group(1) if found else ''
        check('the link contains a usable token', bool(token))
        check('it was addressed to the registrar on file',
              '@' in (queued.to_email or ''), queued.to_email)

    if not token:
        print('        cannot continue without the registrar link')
        return 1

    opened = anonymous_get(f'/api/enrolment/{token}/')
    check('the registrar can open it without an account', opened.status_code == 200,
          f'{opened.status_code} {opened.text[:200]}')
    if opened.status_code == 200:
        context = opened.json()['application']
        check('the form names the student',
              bool(context.get('student_name')), str(context)[:200])
        check('and does not hand the institution a SIN or date of birth',
              'sin' not in str(context.get('prefill', {})).lower()
              and 'date_of_birth' not in context.get('prefill', {}))

    confirmed = anonymous_post(f'/api/enrolment/{token}/', json={'answers': {
        'student_name': answers['full_name'],
        'institution_name': 'Aurora College',
        'program': 'Environmental Science',
        'is_enrolled': True,
        'course_load': 'full_time',
        'semester': 'fall',
        'semester_start': '2026-09-01',
        'semester_end': '2026-12-31',
        # Deliberately unlike anything the student could have typed: the award
        # must be built from this number.
        'confirmed_tuition': '7431.55',
        'registrar_name': 'R. Registrar',
        'registrar_title': 'Registrar',
        'signature': 'R. Registrar',
        'completed_on': '2026-09-05',
    }})
    check('the registrar can confirm the enrolment', confirmed.status_code == 200,
          f'{confirmed.status_code} {confirmed.text[:300]}')

    # 404 as well as 409: once completed, resolve() stops recognising the token
    # at all, and every failure there answers identically so the endpoint cannot
    # be used to probe for live tokens.
    reused = anonymous_post(f'/api/enrolment/{token}/', json={'answers': {}})
    check('the link is single use', reused.status_code in (400, 404, 409),
          f'{reused.status_code} — a second submission must not be able to '
          'change an award after a decision was made on it')

    after = worker.get(f'/api/applications/{app_id}/').json()
    check('the confirmed tuition reached the application',
          str(after['answers'].get('confirmed_tuition', '')).startswith('7431'),
          repr(after['answers'].get('confirmed_tuition')))
    check('and the semester dates the living allowance is counted over',
          bool(after['answers'].get('semester_start'))
          and bool(after['answers'].get('semester_end')),
          str({k: after['answers'].get(k) for k in ('semester_start', 'semester_end')}))
    check("the registrar's full declaration is visible to staff",
          bool(after.get('enrolment_answers')),
          'a reviewer cannot check a figure they cannot see')
    check('the renewal is now marked confirmed',
          (after.get('enrolment') or {}).get('confirmed') is True,
          str(after.get('enrolment')))

    # ── Director ─────────────────────────────────────────────────────────────
    section('Director portal — pricing and the decision')

    forwarded = worker.post(f'/api/applications/{app_id}/transition/',
                            json={'action': 'forwarded'})
    check('it can be forwarded once the figure exists', forwarded.status_code == 200,
          f'{forwarded.status_code} {forwarded.text[:200]}')

    preview = director.get(f'/api/applications/{app_id}/decision-preview/')
    if check('the director can preview the award', preview.status_code == 200,
             f'{preview.status_code} {preview.text[:300]}'):
        trace = preview.json()
        applied = [rule for rule in trace.get('rules', []) if rule.get('applied')]
        check('at least one rule applies to a renewal',
              len(applied) > 0,
              'a renewal that matches no rule is awarded nothing, silently. '
              f'Rules considered: {len(trace.get("rules", []))}')
        check('nothing is priced against a missing rate',
              not trace.get('missing_rates'), str(trace.get('missing_rates')))
        for rule in applied:
            print(f'        {rule["code"]}: {rule["amount"]}  {rule["reason"][:60]}')

        total = sum(Decimal(rule['amount']) for rule in applied)
        check('the renewal is worth something', total > 0, f'total {total}')
        tuition_rules = [r for r in applied if 'tuition' in r['code'].lower()
                         or 'tuition' in r['category'].lower()]
        if tuition_rules:
            # The cap hides the bill in the amount, so the evidence is the
            # remainder: 7431.55 billed less a 7000 cap leaves 431.55. A student
            # estimate could not produce that number, because the form has
            # nowhere to type one.
            check("tuition is funded against the registrar's figure",
                  any('431.55' in rule['reason'] or '7431' in rule['amount']
                      for rule in tuition_rules),
                  str([(r['code'], r['amount'], r['reason']) for r in tuition_rules]))

    priced = director.post(f'/api/applications/{app_id}/price/')
    check('the director can record the award', priced.status_code == 201,
          f'{priced.status_code} {priced.text[:300]}')

    approved = director.post(f'/api/applications/{app_id}/transition/',
                             json={'action': 'approved'})
    check('the director can approve', approved.status_code == 200,
          f'{approved.status_code} {approved.text[:200]}')

    history = director.get(f'/api/applications/{app_id}/decisions/')
    check('the pricing is kept for an appeal to argue from',
          history.status_code == 200 and len(history.json()) >= 1,
          f'{history.status_code} {history.text[:200]}')

    check('finance cannot decide',
          finance.post(f'/api/applications/{app_id}/transition/',
                       json={'action': 'approved'}).status_code == 403)

    # ── Residency ────────────────────────────────────────────────────────────
    section('Residency — the answers disagreeing with the address')

    # Reported by the office: a student said they do not live in the Northwest
    # Territories and then gave an address in the Northwest Territories, and
    # nothing said so. `residency_flag` had two readers and no writer, so the
    # dashboard count could only ever be zero. Driven over HTTP because what
    # broke was the whole path — a flag nothing writes still serialises fine.
    stamp = int(time.time())
    residency_email = f'residency.{stamp}@example.com'
    registered = anonymous_post('/api/auth/register/', json={
        'email': residency_email, 'password': PASSWORD,
        'confirm_password': PASSWORD, 'first_name': 'Not', 'last_name': 'Resident',
        'eligibility': {
            'indian_act_registered': 'yes', 'deline_beneficiary': 'yes',
            'receives_sfa': 'no', 'lives_in_nwt': 'no',
            'accredited_institution': 'yes', 'programme_twelve_weeks': 'yes',
        }})
    if check('a student who does not live in the NWT can register',
             registered.status_code == 201,
             f'{registered.status_code} {registered.text[:200]}'):
        mover = Role(residency_email)

        nwt = {'street_address': '12 Bear Rock Road', 'city': 'Deline',
               'province': 'NT', 'postal_code': 'X0E 0G0'}
        filed_here = mover.post('/api/applications/', json={
            'type': 'admission', 'answers': {**ADMISSION_ANSWERS, **nwt}})
        if check('they can file with an address in the NWT',
                 filed_here.status_code == 201,
                 f'{filed_here.status_code} {filed_here.text[:200]}'):
            flagged_id = filed_here.json()['id']
            seen = worker.get(f'/api/applications/{flagged_id}/').json()
            check('the contradiction is flagged for the office',
                  bool(seen.get('residency_flag')),
                  'said they do not live in the NWT and gave an NWT address, '
                  'and nothing was flagged')
            check('and the flag says what the disagreement is',
                  'Northwest Territories' in (seen.get('residency_flag') or ''),
                  str(seen.get('residency_flag'))[:120])
            listed = worker.get('/api/applications/?status=submitted').json()
            row = next((r for r in listed['results'] if r['id'] == flagged_id), None)
            check('it reaches the queue the reviewer works from',
                  bool((row or {}).get('residency_flag')), str(row)[:120])
            counted = worker.get('/api/dashboard/').json()
            check('and the dashboard count is no longer stuck at zero',
                  counted['attention']['residency_mismatch'] >= 1,
                  str(counted['attention']))

        # The other half, and the more important one: a flag that fires on an
        # ordinary application is a queue nobody can clear.
        elsewhere = {'street_address': '400 Jasper Avenue', 'city': 'Edmonton',
                     'province': 'AB', 'postal_code': 'T5J 0N3'}
        filed_away = mover.post('/api/applications/', json={
            'type': 'admission', 'answers': {**ADMISSION_ANSWERS, **elsewhere}})
        if check('they can also file with an address outside the NWT',
                 filed_away.status_code == 201,
                 f'{filed_away.status_code} {filed_away.text[:200]}'):
            consistent = worker.get(
                f'/api/applications/{filed_away.json()["id"]}/').json()
            check('answers that agree are not flagged',
                  not consistent.get('residency_flag'),
                  str(consistent.get('residency_flag'))[:120])

    # The student who has been here all along says they do live in the NWT, so
    # nothing about their application should be flagged either.
    unflagged = worker.get(f'/api/applications/{app_id}/').json()
    check('a resident with an NWT address is left alone',
          not unflagged.get('residency_flag'),
          str(unflagged.get('residency_flag'))[:120])

    # ── The approval letter ──────────────────────────────────────────────────
    section('The approval letter')

    # The office signs these, so what they say has to be the award itself. The
    # unit tests build the letter; this asks the running server for it as the
    # student, which is the only thing that proves the endpoint is reachable by
    # the person it is addressed to.
    issued = student.get(f'/api/applications/{app_id}/approval-letter/')
    if check('the student can read their own approval letter',
             issued.status_code == 200, f'{issued.status_code} {issued.text[:200]}'):
        produced = issued.json()
        check('at least one letter is produced for an approved award',
              isinstance(produced, list) and produced, str(produced)[:160])

        codes = [letter['programme_code'] for letter in produced]
        check('every letter names one of the office\'s three templates',
              all(code in ('DGG-CDFN', 'DGG-UCEPP', 'DGGR-SFSP') for code in codes),
              str(codes))

        # The figures are the whole point: a letter that disagrees with the
        # award is the office putting its name to a wrong number.
        detail = student.get(f'/api/applications/{app_id}/').json()
        awarded = Decimal(str(detail['awarded_total']))
        lettered = sum(
            Decimal(letter['total'].replace('$', '').replace(',', ''))
            for letter in produced)
        check('the letters account for exactly what was awarded',
              lettered == awarded, f'letters {lettered} vs award {awarded}')

        for letter in produced:
            code = letter['programme_code']
            check(f'{code} is addressed to somebody',
                  bool(letter['recipient'].strip()), repr(letter['recipient']))
            check(f'{code} carries the office\'s signatory and address',
                  bool(letter['signatory']['name']) and bool(letter['office']['address']),
                  str(letter['signatory']))
            # Somewhere — not necessarily in the title. Two templates end
            # "for the" and take the term there; the DGGR title is already a
            # sentence and names its term in the breakdown's semester column.
            # Requiring it in the title asserted one template's layout against
            # all three.
            check(f'{code} names the term it funds',
                  bool(letter['term'].strip()) or bool(letter['semester'].strip()),
                  f"term {letter['term']!r} semester {letter['semester']!r}")
            # A letter whose rows do not add up to its own total is worse than
            # no letter: it is arithmetic the office is signing.
            rows = sum(Decimal(row['amount'].replace('$', '').replace(',', ''))
                       for row in letter['rows'])
            check(f'{code} rows add up to its total',
                  rows == Decimal(letter['total'].replace('$', '').replace(',', '')),
                  f"rows {rows} vs total {letter['total']}")
            # No rate must ever reach a student as $0.00 — see the percentage
            # that was published as an amount of money.
            check(f'{code} prints no zero-dollar cap',
                  '$0.00' not in letter['footnote'], letter['footnote'][:120])

    check('the office can read the letter it sent',
          worker.get(f'/api/applications/{app_id}/approval-letter/').status_code == 200)
    check('another student cannot read somebody else\'s letter',
          other_student.get(
              f'/api/applications/{app_id}/approval-letter/').status_code == 404)
    check('nor can a stranger',
          anonymous_get(
              f'/api/applications/{app_id}/approval-letter/').status_code == 401)

    # The PDF, which is what the office actually sends and files. Driven over
    # HTTP because the thing being checked is that a real request comes back
    # with a real document — a service that can build bytes proves nothing
    # about whether anybody can get them.
    as_pdf = student.get(f'/api/applications/{app_id}/approval-letter/pdf/')
    if check('the student can download the letter as a PDF',
             as_pdf.status_code == 200, f'{as_pdf.status_code} {as_pdf.text[:160]}'):
        check('it is served as a PDF',
              as_pdf.headers.get('Content-Type') == 'application/pdf',
              str(as_pdf.headers.get('Content-Type')))
        check('and it really is one',
              as_pdf.content[:5] == b'%PDF-', str(as_pdf.content[:20]))
        check('it is offered under a name that says what it is',
              '.pdf' in (as_pdf.headers.get('Content-Disposition') or ''),
              str(as_pdf.headers.get('Content-Disposition')))
        check('the document carries every letter this approval earned',
              as_pdf.content.count(b'/Type /Page') >= len(produced),
              f"{as_pdf.content.count(b'/Type /Page')} pages for "
              f"{len(produced)} letter(s)")

    check('the office can download it too',
          worker.get(f'/api/applications/{app_id}/approval-letter/pdf/'
                     ).status_code == 200)
    check("another student cannot download somebody else's",
          other_student.get(f'/api/applications/{app_id}/approval-letter/pdf/'
                            ).status_code == 404)
    check('nor can a stranger download it',
          anonymous_get(f'/api/applications/{app_id}/approval-letter/pdf/'
                        ).status_code == 401)

    # The letter is attached to what the student is sent, not only downloadable.
    with_pdf = [mail for mail in OutboundEmail.objects.filter(id__gt=outbox_mark)
                if (mail.attachment_name or '').endswith('.pdf')]
    if check('an approval email went out carrying the PDF', bool(with_pdf),
             'no queued message has a PDF attached'):
        check('the attachment is a real PDF',
              bytes(with_pdf[-1].attachment or b'')[:5] == b'%PDF-',
              str(bytes(with_pdf[-1].attachment or b'')[:20]))
        check('and it is typed as one',
              with_pdf[-1].attachment_type == 'application/pdf',
              str(with_pdf[-1].attachment_type))

    # ── The other order ──────────────────────────────────────────────────────
    section('The approval letter — approving before pricing')

    # Everything above prices and then approves, and so does every other audit
    # here. Nothing in `workflow.ALLOWED_ACTIONS` requires that order: the
    # office may approve first and record the award afterwards, and on that
    # path the approval email has no award to describe. The letter went out
    # with nothing in it and nothing sent one when the pricing arrived — the
    # student got no letter at all, in silence, and every test and every audit
    # passed because all of them walked the one order.
    #
    # Driven over HTTP as the office actually drives it, because the fault was
    # in *when* the two calls happen and not in either call.
    second_mark = OutboundEmail.objects.order_by('-id').values_list(
        'id', flat=True).first() or 0

    reversed_filed = student.post('/api/applications/', json={
        'type': 'admission', 'answers': dict(ADMISSION_ANSWERS)})
    if check('a second admission is filed, to be worked in the other order',
             reversed_filed.status_code == 201,
             f'{reversed_filed.status_code} {reversed_filed.text[:300]}'):
        other_id = reversed_filed.json()['id']

        # Tuition is funded against the registrar's figure, so this application
        # cannot be approved at all until the institution answers — the letter
        # is about semester funding, and semester funding is what needs this.
        other_verification = EnrollmentVerification.objects.filter(
            application_id=other_id).first()
        if other_verification is None:
            worker.post(f'/api/applications/{other_id}/request-enrolment/',
                        json={'registrar_email': REGISTRAR_EMAIL})
            other_verification = EnrollmentVerification.objects.filter(
                application_id=other_id).first()

        other_email = (OutboundEmail.objects
                       .filter(id__gt=second_mark,
                               body_html__contains=other_verification.token)
                       .order_by('id').first()) if other_verification else None
        other_token = ''
        if check('its registrar is asked to confirm', other_email is not None):
            found = re.search(r'/enrolment/([A-Za-z0-9_\-]+)', other_email.body_html)
            other_token = found.group(1) if found else ''

        if check('the registrar link is usable', bool(other_token)):
            other_confirmed = anonymous_post(f'/api/enrolment/{other_token}/', json={
                'answers': {
                    'student_name': ADMISSION_ANSWERS.get('full_name') or 'A Student',
                    'institution_name': 'Aurora College',
                    'program': 'Environmental Science',
                    'is_enrolled': True,
                    'course_load': 'full_time',
                    'semester': 'fall',
                    'semester_start': '2026-09-01',
                    'semester_end': '2026-12-31',
                    'confirmed_tuition': '6200.00',
                    'registrar_name': 'R. Registrar',
                    'registrar_title': 'Registrar',
                    'signature': 'R. Registrar',
                    'completed_on': '2026-09-05',
                }})
            check('the institution confirms it',
                  other_confirmed.status_code == 200,
                  f'{other_confirmed.status_code} {other_confirmed.text[:200]}')

            admin.post(f'/api/applications/{other_id}/transition/',
                       json={'action': 'reviewed'})

            # Approved with nothing priced. This is the moment the fault lived
            # in: the email goes out and there is no award to put in it.
            approved_first = admin.post(
                f'/api/applications/{other_id}/transition/',
                json={'action': 'approved'})
            check('it can be approved before anything is priced',
                  approved_first.status_code == 200,
                  f'{approved_first.status_code} {approved_first.text[:200]}')

            after_approval = list(
                OutboundEmail.objects.filter(id__gt=second_mark))
            check('the approval email carries no letter yet, having no award '
                  'to describe',
                  not any('Total Allotted' in mail.body_html
                          for mail in after_approval))
            # And the endpoint says why, in words the office can act on,
            # rather than answering 404 or an empty list.
            not_yet = student.get(f'/api/applications/{other_id}/approval-letter/')
            check('and the letter screen says it has not been priced',
                  not_yet.status_code == 409
                  and 'priced' in not_yet.text.lower(),
                  f'{not_yet.status_code} {not_yet.text[:160]}')

            priced_after = admin.post(f'/api/applications/{other_id}/price/')
            check('the award is recorded afterwards',
                  priced_after.status_code == 201,
                  f'{priced_after.status_code} {priced_after.text[:200]}')

            # The check the whole section exists for.
            after_pricing = list(
                OutboundEmail.objects.filter(id__gt=second_mark))
            check('the letter reaches the student once there is an award',
                  any('Total Allotted' in mail.body_html
                      for mail in after_pricing),
                  'approved and priced, and no letter was ever sent')
            check('it was sent as its own message, not silently attached to an '
                  'email already gone',
                  any('approval letter' in (mail.subject or '').lower()
                      for mail in after_pricing),
                  str([mail.subject for mail in after_pricing]))

            served = student.get(f'/api/applications/{other_id}/approval-letter/')
            if check('and the letter screen now serves it',
                     served.status_code == 200,
                     f'{served.status_code} {served.text[:200]}'):
                produced = served.json()
                detail = student.get(f'/api/applications/{other_id}/').json()
                check('worked in either order, the letters still account for '
                      'the whole award',
                      sum(Decimal(letter['total'].replace('$', '').replace(',', ''))
                          for letter in produced)
                      == Decimal(str(detail['awarded_total'])),
                      f"letters vs award {detail['awarded_total']}")

    # ── The annual report ────────────────────────────────────────────────────
    section('The annual report to the head department')

    # The office forwards this to its funder, so what matters is not that
    # figures appear but that the reader can tell what they are: gross against
    # net, computed against hand-entered, classified against not.
    report = admin.get('/api/reports/annual/')
    if check('an administrator can read the annual report',
             report.status_code == 200, f'{report.status_code} {report.text[:200]}'):
        body = report.json()
        for part in ('enrolment', 'graduate_awards', 'institutions',
                     'financial', 'highlights'):
            check(f'it carries the {part.replace("_", " ")} table',
                  part in body, str(sorted(body))[:120])

        enrolment = body['enrolment']
        row_total = (enrolment['total']['university'] + enrolment['total']['college']
                     + enrolment['total']['trades_school']
                     + enrolment['total']['unclassified'])
        check('the enrolment total is the sum of its columns',
              row_total == enrolment['total']['total'],
              f"{row_total} vs {enrolment['total']['total']}")
        # The office's own note: these are subsets, not extra columns. Adding
        # them would report more students than attended.
        check('trades and upgrading are not added on top',
              enrolment['total']['trades'] <= enrolment['total']['total']
              and enrolment['total']['upgrading'] <= enrolment['total']['total'],
              str(enrolment['total']))

        financial = body['financial']
        check('every money figure comes as gross, repaid and net',
              all({'gross', 'repaid', 'net'} <= set(cell)
                  for row in financial['rows']
                  for cell in row['categories'].values()),
              'a figure was reported without saying whether it is net')
        gross = Decimal(financial['total']['gross'])
        repaid = Decimal(financial['total']['repaid'])
        check('net is gross less what came back',
              Decimal(financial['total']['net']) == gross - repaid,
              f'{gross} - {repaid} vs {financial["total"]["net"]}')
        check('the grand total adds the entered costs to the net',
              Decimal(financial['grand_total'])
              == Decimal(financial['total']['net']) + Decimal(financial['entered_total']),
              str(financial['grand_total']))

        highlights = body['highlights']
        check('the summary quotes the tables rather than a second calculation',
              highlights['grand_total'] == financial['grand_total']
              and highlights['direct_funding_net'] == financial['total']['net'],
              str(highlights)[:140])

    # A repayment, recorded against this audit's own award so the check has
    # something to move. Asserting that net equals gross-less-repaid proves
    # nothing while both are nought — an arithmetic check on a figure that is
    # always zero is the residency count all over again.
    priced_line = (Award.objects.current()
                   .filter(application_id=app_id).order_by('-amount').first())
    if check('the approved award has a line to reconcile against',
             priced_line is not None):
        # Named for what they are rather than `before`/`after`: this script is
        # long and `after` already holds an application payload that is read
        # hundreds of lines further down. Shadowing it made an unrelated check
        # crash with a KeyError.
        money_before = admin.get('/api/reports/annual/').json()['financial']['total']
        returned = admin.post('/api/reports/repayments/', json={
            'award': priced_line.id, 'amount': '25.00',
            'reason': 'Withdrew from one course — recorded by the lifecycle audit',
            'repaid_on': date.today().isoformat()})
        if check('an administrator can record money that came back',
                 returned.status_code == 201,
                 f'{returned.status_code} {returned.text[:200]}'):
            money_after = admin.get('/api/reports/annual/').json()['financial']['total']
            check('the gross is untouched by a repayment',
                  Decimal(money_after['gross']) == Decimal(money_before['gross']),
                  f"{money_before['gross']} -> {money_after['gross']}")
            check('the repaid figure moved by what came back',
                  Decimal(money_after['repaid']) - Decimal(money_before['repaid']) == Decimal('25.00'),
                  f"{money_before['repaid']} -> {money_after['repaid']}")
            check('and the net fell by the same amount',
                  Decimal(money_before['net']) - Decimal(money_after['net']) == Decimal('25.00'),
                  f"{money_before['net']} -> {money_after['net']}")

        # The award itself is the record of what was decided, and an approval
        # letter has already told the student that figure.
        granted = priced_line.amount
        priced_line.refresh_from_db()
        check('the award it came from is not rewritten',
              priced_line.amount == granted,
              f'{granted} became {priced_line.amount}')

        too_much = admin.post('/api/reports/repayments/', json={
            'award': priced_line.id, 'amount': str(priced_line.amount + 1),
            'reason': 'more than was granted', 'repaid_on': date.today().isoformat()})
        check('more cannot come back than went out', too_much.status_code == 400,
              f'{too_much.status_code} {too_much.text[:160]}')
        no_reason = admin.post('/api/reports/repayments/', json={
            'award': priced_line.id, 'amount': '1.00', 'reason': '   ',
            'repaid_on': date.today().isoformat()})
        check('a repayment must say why', no_reason.status_code == 400,
              f'{no_reason.status_code} {no_reason.text[:160]}')

    # Who may see the year's expenditure.
    check('the Director may read it',
          director.get('/api/reports/annual/').status_code == 200)
    check('Finance may read it',
          finance.get('/api/reports/annual/').status_code == 200)
    check('a support worker may not',
          worker.get('/api/reports/annual/').status_code == 403)
    check('nor a student',
          student.get('/api/reports/annual/').status_code == 403)
    check('nor a stranger',
          anonymous_get('/api/reports/annual/').status_code == 401)
    check('a year that is not a year is refused rather than reported as this one',
          admin.get('/api/reports/annual/?year=abc').status_code == 400)

    # The document they actually forward.
    as_pdf = admin.get('/api/reports/annual/pdf/')
    if check('the report downloads as a PDF', as_pdf.status_code == 200,
             f'{as_pdf.status_code} {as_pdf.text[:160]}'):
        check('served as a PDF',
              as_pdf.headers.get('Content-Type') == 'application/pdf',
              str(as_pdf.headers.get('Content-Type')))
        check('and it really is one', as_pdf.content[:5] == b'%PDF-',
              str(as_pdf.content[:20]))
    check('a support worker cannot download it either',
          worker.get('/api/reports/annual/pdf/').status_code == 403)

    # The figure the system cannot know, entered by the Director.
    entered = admin.post('/api/reports/costs/', json={
        'fiscal_year_start': f'{date.today().year}-04-01',
        'label': 'Administration — Staff Wages/Benefits (audit)',
        'amount': '1234.00', 'note': 'Recorded by the lifecycle audit'})
    if check('an administrator can enter a cost the system cannot see',
             entered.status_code in (200, 201),
             f'{entered.status_code} {entered.text[:200]}'):
        corrected = admin.post('/api/reports/costs/', json={
            'fiscal_year_start': f'{date.today().year}-04-01',
            'label': 'Administration — Staff Wages/Benefits (audit)',
            'amount': '2345.00'})
        check('entering it again corrects the figure rather than adding a line',
              corrected.status_code in (200, 201),
              f'{corrected.status_code} {corrected.text[:200]}')
        listed = admin.get('/api/reports/costs/').json()
        matching = [c for c in listed
                    if c['label'] == 'Administration — Staff Wages/Benefits (audit)']
        check('there is one row for it, not two', len(matching) == 1, str(len(matching)))
        if matching:
            check('and it holds the corrected amount',
                  Decimal(matching[0]['amount']) == Decimal('2345.00'),
                  str(matching[0]['amount']))
    check('the Director may not enter one',
          director.post('/api/reports/costs/', json={
              'fiscal_year_start': f'{date.today().year}-04-01',
              'label': 'X', 'amount': '1'}).status_code == 403)

    # ── Finance ──────────────────────────────────────────────────────────────
    section('Finance portal — paying it')

    def in_run():
        response = finance.get('/api/finance/pending/')
        if response.status_code != 200:
            return response, [], []
        run = response.json()
        return (response,
                [r for r in run['awards'] if r['application_id'] == app_id],
                [r for r in run['blocked'] if r['application_id'] == app_id])

    pending, listed, blocked = in_run()
    if check('finance can see the payment run', pending.status_code == 200,
             f'{pending.status_code} {pending.text[:200]}'):
        check('the approved renewal is payable, or says why not',
              bool(listed) or bool(blocked),
              'it is neither ready nor blocked — it has fallen out of the run')
        if blocked:
            print(f'        blocked: {blocked[0]["reason"]}')

    # Dispatch is what records the handoff. Staff can also record it by hand
    # from the application screen, which pays nothing — so the award has to
    # survive that and still be payable afterwards.
    check('the director who approved it cannot also send it to finance',
          director.post(f'/api/applications/{app_id}/transition/',
                        json={'action': 'sent_to_finance'}).status_code == 403)
    by_hand = worker.post(f'/api/applications/{app_id}/transition/',
                          json={'action': 'sent_to_finance'})
    check('a worker can mark it sent by hand', by_hand.status_code == 200,
          f'{by_hand.status_code} {by_hand.text[:200]}')

    _, still_listed, still_blocked = in_run()
    check('marking it sent by hand does not strand the money',
          bool(still_listed) or bool(still_blocked),
          'the award is PENDING and owed, and no payment run will ever return '
          'it again — nothing reports an award in this state')

    check('a director cannot send the payment run',
          director.post('/api/finance/dispatch/').status_code == 403)

    if still_listed:
        run_out = finance.post('/api/finance/dispatch/')
        if check('finance can send the batch', run_out.status_code == 200,
                 f'{run_out.status_code} {run_out.text[:200]}'):
            check('the file is a CSV naming the student',
                  'Reference' in run_out.text
                  and answers['full_name'].split()[-1] in run_out.text,
                  run_out.text[:200])
            print(f'        {run_out.headers.get("X-Award-Count")} award(s), '
                  f'total {run_out.headers.get("X-Award-Total")}')

        _, after_pay, _ = in_run()
        check('the same money cannot be dispatched twice', not after_pay,
              'the award is still offered after being paid')

    # ── Admin ────────────────────────────────────────────────────────────────
    section('Admin portal — policy still readable')

    rates = admin.get('/api/policy/rates/')
    check('rates are readable', rates.status_code == 200,
          f'{rates.status_code} {rates.text[:200]}')
    rule_sets = admin.get('/api/policy/rule-sets/')
    check('rule sets are readable', rule_sets.status_code == 200,
          f'{rule_sets.status_code} {rule_sets.text[:200]}')

    # Reading was all this section did. Changing a rate changes what everyone is
    # paid from here on, and changing a role grants or removes the power to
    # decide funding — neither had ever been driven over HTTP.
    if rates.status_code == 200:
        groups = rates.json()
        first = next((setting for group in groups for setting in group['settings']), None)
        if check('there is a rate to edit', first is not None):
            rate_id, was = first['id'], first['value']

            def entries():
                response = admin.get(f'/api/policy/rates/{rate_id}/')
                return (len(response.json().get('history', []))
                        if response.status_code == 200 else -1)

            # Counted as a delta, not an absolute. The history is permanent and
            # this audit is meant to be run repeatedly, so 'the history has one
            # entry' would pass once and fail every time after.
            before = entries()
            check('the rate history is readable', before >= 0)

            raised = admin.patch(f'/api/policy/rates/{rate_id}/',
                                 json={'value': str(Decimal(str(was)) + 1)})
            check('an administrator can change a rate', raised.status_code == 200,
                  f'{raised.status_code} {raised.text[:200]}')
            check('and the change is recorded', entries() == before + 1,
                  f'history went from {before} to {entries()}')

            again = admin.patch(f'/api/policy/rates/{rate_id}/',
                                json={'value': str(Decimal(str(was)) + 1)})
            check('setting a rate to what it already is is not an error',
                  again.status_code in (200, 400, 409),
                  f'{again.status_code} {again.text[:200]}')
            check('and records nothing — a history of no-ops is unreadable',
                  entries() == before + 1,
                  f'history grew to {entries()}, expected {before + 1}')

            check('a support worker cannot change a rate',
                  worker.patch(f'/api/policy/rates/{rate_id}/',
                               json={'value': '1'}).status_code == 403)
            check('nor can the director who approves awards',
                  director.patch(f'/api/policy/rates/{rate_id}/',
                                 json={'value': '1'}).status_code == 403)

            # Put it back, so the audit can be run twice.
            admin.patch(f'/api/policy/rates/{rate_id}/', json={'value': str(was)})

    section('Admin portal — who may do what')

    directory = admin.get('/api/people/')
    if check('an administrator can list accounts', directory.status_code == 200,
             f'{directory.status_code} {directory.text[:200]}'):
        people_rows = directory.json()['results']
        check('and the directory does not carry addresses or banking',
              all(not ({'street_address', 'account_number', 'sin'} & set(row))
                  for row in people_rows),
              'the directory is for finding someone, not for reading their file')

        me = admin.get('/api/me/').json()
        target = next((row for row in people_rows
                       if row['role'] == 'student' and row['id'] != me.get('id')), None)
        if check('there is an account to administer', target is not None):
            promoted = admin.patch(f'/api/people/{target["id"]}/',
                                   json={'role': 'support_worker'})
            check('an administrator can change a role', promoted.status_code == 200,
                  f'{promoted.status_code} {promoted.text[:200]}')
            admin.patch(f'/api/people/{target["id"]}/', json={'role': 'student'})

            check('a support worker cannot',
                  worker.patch(f'/api/people/{target["id"]}/',
                               json={'role': 'admin'}).status_code == 403)
            check('nor a student',
                  student.patch(f'/api/people/{target["id"]}/',
                                json={'role': 'admin'}).status_code == 403)

        # The guard that matters: an office that demotes its last administrator
        # has locked itself out of its own policy, and nothing in the portal can
        # let it back in.
        if me.get('id'):
            locked_out = admin.patch(f'/api/people/{me["id"]}/',
                                     json={'role': 'student'})
            check('the last administrator cannot demote themselves',
                  locked_out.status_code == 409,
                  f'{locked_out.status_code} {locked_out.text[:200]}')
            deactivated = admin.patch(f'/api/people/{me["id"]}/',
                                      json={'is_active': False})
            check('nor deactivate themselves', deactivated.status_code == 409,
                  f'{deactivated.status_code} {deactivated.text[:200]}')

    check('a student cannot read the staff directory',
          student.get('/api/people/').status_code == 403)

    dash = {}
    for name, role in (('worker', worker), ('director', director), ('admin', admin),
                       ('student', student)):
        response = role.get('/api/dashboard/')
        dash[name] = response.status_code
    check('every portal’s dashboard loads',
          all(code == 200 for code in dash.values()), str(dash))

    # The stream split on the office's home screen, and the queue behind it.
    # A tile that reports four PSSSP applications and links to a queue showing
    # every application is the DjangoFilterBackend fault again: the filter is
    # ignored and the answer is still a 200.
    office = worker.get('/api/dashboard/').json()
    split = office.get('streams')
    if check('the office is shown how the applications split by stream',
             isinstance(split, list) and split, str(split)[:200]):
        by_stream = {row['stream']: row for row in split}
        check('every stream has a row, including the ones nothing is in',
              set(by_stream) >= {'psssp', 'ucepp', 'dggr'}, str(sorted(by_stream)))
        check('every row is named as the office names it',
              all(row.get('label') for row in split),
              str([row.get('stream') for row in split if not row.get('label')]))
        check('the split adds up to the total beside it',
              sum(row['total'] for row in split) == office['applications']['total'],
              f"{sum(row['total'] for row in split)} vs "
              f"{office['applications']['total']}")
        check('and its open counts add up too',
              sum(row['open'] for row in split) == office['applications']['open'],
              f"{sum(row['open'] for row in split)} vs "
              f"{office['applications']['open']}")
        # Counts only. An award line carries no stream and the rules gate on
        # every stream an applicant qualifies for, so no sum of money belongs
        # to one pot.
        check('the split carries counts and no money',
              all(set(row) == {'stream', 'label', 'total', 'open'} for row in split),
              str([sorted(row) for row in split]))

        for stream, row in by_stream.items():
            listed = worker.get(f'/api/applications/?stream={stream}')
            if not check(f'the queue filters to {stream}', listed.status_code == 200,
                         f'{listed.status_code} {listed.text[:200]}'):
                continue
            body = listed.json()
            check(f'and returns exactly what the {stream} tile counted',
                  body['count'] == row['total'],
                  f"queue {body['count']} vs tile {row['total']}")
            check(f'every row it returns really is {stream}',
                  all(item['stream'] == stream for item in body['results']),
                  str({item['stream'] for item in body['results']}))

        # A stream outside the choice set is carried in the split so the rows
        # still add up — and the queue answers 400 to it, which is why the
        # screen does not offer one as a link. Checked here because no seeded
        # database has such a row, so nothing else would notice the day one
        # appeared.
        refused = worker.get('/api/applications/?stream=not-a-stream')
        check('the queue refuses a stream nobody offered rather than ignoring it',
              refused.status_code == 400, f'{refused.status_code} {refused.text[:160]}')
        unfiltered = worker.get('/api/applications/').json()['count']
        check('and refusing is not the same as returning everything',
              refused.status_code != 200, str(unfiltered))

        # A reviewer narrows by more than one thing at a time. A filter that
        # works alone and is dropped in company is the same silent failure.
        both = worker.get('/api/applications/?stream=psssp&status=submitted')
        if check('stream and status narrow together', both.status_code == 200,
                 f'{both.status_code} {both.text[:160]}'):
            rows = both.json()['results']
            check('and every row satisfies both',
                  all(item['stream'] == 'psssp' and item['status'] == 'submitted'
                      for item in rows),
                  str({(item['stream'], item['status']) for item in rows}))
            check('narrowing by two returns no more than narrowing by one',
                  both.json()['count'] <= by_stream['psssp']['total'],
                  f"{both.json()['count']} vs {by_stream['psssp']['total']}")

    # Every staff role reaches the same dashboard. Checking the one role that
    # happened to be to hand is how a screen ends up right for a support worker
    # and missing for the Director who signs the decisions.
    for name, role in (('director', director), ('finance', finance), ('admin', admin)):
        body = role.get('/api/dashboard/').json()
        check(f'{name} is shown the stream split too',
              isinstance(body.get('streams'), list) and len(body['streams']) >= 3,
              str(body.get('streams'))[:160])
        check(f'and {name}\'s split adds up',
              sum(row['total'] for row in body.get('streams', []))
              == body['applications']['total'],
              str(body.get('streams'))[:160])

    check('a student is not shown the office split',
          'streams' not in student.get('/api/dashboard/').json())

    # The help page. Public on purpose — the people who most need a phone
    # number are the ones who cannot sign in, so a help page behind a login is
    # help for everybody except them.
    helped = anonymous_get('/api/help/')
    if check('the help page is readable without signing in',
             helped.status_code == 200, f'{helped.status_code} {helped.text[:200]}'):
        body = helped.json()
        check('and carries a way to reach the office',
              all(body['contact'].get(key) for key in ('email', 'phone', 'address')),
              str(body.get('contact')))
        check('and the questions it is asked most',
              len(body.get('faq', [])) >= 2, str(len(body.get('faq', []))))
        check('every question has an answer',
              all(entry['question'].strip() and entry['answer'].strip()
                  for entry in body.get('faq', [])))

    schemas = anonymous_get('/api/schemas/')
    check('the form list is still servable to a visitor', schemas.status_code == 200)
    if schemas.status_code == 200:
        renewal = next((s for s in schemas.json()
                        if s['slug'] == 'continuing_funding'), None)
        check('the renewal is offered in the portal',
              renewal is not None and renewal['apply_in_portal'] is True)
        check('and every form still declares its sections',
              all(s['sections'] for s in schemas.json()),
              str([s['slug'] for s in schemas.json() if not s['sections']]))

    # ── Cross-cutting ────────────────────────────────────────────────────────
    section('Across the portals')

    # Filed by the *other* student, here, rather than hoped for in the seeded
    # data. An appeal is the cheapest complete application there is: prose and a
    # signature, no documents, no enrolment gate.
    theirs = other_student.post('/api/applications/', json={
        'type': 'appeal',
        'answers': {
            'full_name': 'Sam Secondstudent',
            'student_number': 'A-00002',
            'institution_name': 'Aurora College',
            'semester': 'fall',
            'academic_year': '2026-2027',
            'appeal_reason': 'Filed so that isolation can be tested against it.',
            'declaration_confirmed': True,
            'signature': 'Sam Secondstudent',
            'signed_on': '2026-08-15',
        },
    })
    check('the second student can file one of their own',
          theirs.status_code == 201, f'{theirs.status_code} {theirs.text[:300]}')

    everything = worker.get('/api/applications/').json()
    everything = everything.get('results') or everything
    mine_name = next((row['student_name'] for row in everything
                      if row['id'] == app_id), None)
    # Belonging to a *different person*, not merely a different application.
    # This student has filed several, so "any id but this one" would have been
    # one of their own and passed while proving nothing.
    someone_else = next((row for row in everything
                         if row.get('student_name')
                         and row['student_name'] != mine_name), None)
    if check('there is another student’s application to try', someone_else is not None,
             'the second student filed one above; if this fails, the staff list '
             'is not showing it'):
        peeked = student.get(f'/api/applications/{someone_else["id"]}/')
        check('a student cannot open an application that is not theirs',
              peeked.status_code in (403, 404),
              f'{peeked.status_code} reading {someone_else["student_name"]}’s '
              f'application {someone_else["id"]}')
        # Both ways round. One direction passing can be an accident of which
        # record happens to be first.
        back = other_student.get(f'/api/applications/{app_id}/')
        check('nor the other way round', back.status_code in (403, 404),
              f'{back.status_code} reading application {app_id}')
        check('and a student cannot act on one that is not theirs',
              other_student.post(f'/api/applications/{app_id}/transition/',
                                 json={'action': 'approved'}).status_code
              in (403, 404))

    check('the renewal never stored a registrar address of its own',
          'registrar_email' not in after['answers'])
    check('nor a tuition figure the student typed',
          'tuition_requested' not in after['answers'])

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
