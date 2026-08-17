"""The whole journey, over HTTP, as the office and a student actually live it.

The other audits each walk one form. This one walks one *student* from sign-up
to payment, through the three things that had never been driven end to end:

  1. Sign-up decides which streams somebody qualifies for, and those tags are
     saved on the account rather than re-derived later from two booleans.
  2. An application is approved cleanly; a second goes round the
     more-information loop twice — once for an answer, once for a document —
     with both sides seeing what the other did.
  3. The funding breakdown reflects every stream a student qualifies for, and
     the office can rewrite it, add rows to it, correct the application behind
     it, and either forward it to the director or decide it themselves.

Run it against a freshly seeded database:

    python manage.py migrate
    python manage.py seed_demo
    python manage.py seed_rules --publish
    python manage.py runserver 127.0.0.1:8000
    python scripts/journey_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from decimal import Decimal

import django
import requests

# Everything here is driven over HTTP. Django is set up for one thing only: to
# read the registrar's link out of the outbound email queue, because that is
# where a real registrar gets it and there is deliberately no endpoint that
# hands a live token to staff.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from notifications.models import OutboundEmail  # noqa: E402

# Every message here can carry `Délı̨nę`, and a Windows console defaults to
# cp1252, which cannot encode it — the same thing that silently failed 143
# queued emails. Say what encoding this writes in rather than inheriting one.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PASSWORD = 'DemoPass123!'
STAMP = str(int(time.time()))

# A one-pixel PNG. Small enough to post repeatedly, real enough to pass the
# type allowlist.
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

checks = 0
failures: list[str] = []


def check(description, condition, detail=''):
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)
    return bool(condition)


def section(title):
    print(f'\n{title}\n{"─" * len(title)}')


class Session:
    """One signed-in person."""

    def __init__(self, base, label=''):
        self.base, self.label = base.rstrip('/'), label
        self.http = requests.Session()

    def login(self, email, password=PASSWORD):
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': password})
        token = response.json().get('access') if response.status_code == 200 else None
        if token:
            self.http.headers['Authorization'] = f'Bearer {token}'
        return bool(token)

    def get(self, path, **kw):
        return self.http.get(f'{self.base}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{self.base}{path}', **kw)

    def patch(self, path, **kw):
        return self.http.patch(f'{self.base}{path}', **kw)


# ── The screening answers, as the sign-up form posts them ────────────────────

ELIGIBLE_BOTH = {
    'indian_act_registered': 'yes',
    'deline_beneficiary': 'yes',
    'receives_sfa': 'no',
    'lives_in_nwt': 'yes',
    'accredited_institution': 'yes',
    'programme_twelve_weeks': 'yes',
}


def screening(**overrides):
    return {**ELIGIBLE_BOTH, **overrides}


def register(base, label, **screening_overrides):
    """Create an account through the public sign-up, and sign in as it."""
    email = f'{label}.{STAMP}@example.com'
    response = requests.post(f'{base}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': label.title(), 'last_name': 'Journey',
        'eligibility': screening(**screening_overrides),
    })
    if response.status_code != 201:
        return None, response
    person = Session(base, label)
    person.login(email)
    return person, response


# ── Answers ──────────────────────────────────────────────────────────────────

# The answers that decide the money, or that a later step reads back. Every
# other required field is filled from the schema, so a question added to the
# admission form tomorrow is answered here without this file being touched —
# the first draft of this audit wrote all twenty-odd out by hand and was
# refused by the server for four fields that no longer exist and three
# documents it had never heard of.
ADMISSION = {
    'course_load': 'full_time',
    'semester': 'fall',
    'semester_start': '2026-09-01',
    'semester_end': '2026-12-31',
    'program_start': '2026-09-01',
    'program_end': '2030-06-30',
    'tuition_requested': '9000',
    'receives_sfa': 'false',
    'has_dependents': 'false',
    'institution_name': 'Aurora College',
    'registrar_email': f'registrar.{STAMP}@example.com',
    'account_holder': 'Journey Student',
    'transit_number': '12345',
    'institution_number': '001',
    'account_number': '9876543210',
}

_SCHEMA_CACHE: dict = {}


def schema_for(base, slug):
    if slug not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[slug] = requests.get(f'{base}/api/schemas/{slug}/').json()
    return _SCHEMA_CACHE[slug]


def admission_answers(base, **overrides):
    return fill_from_schema(schema_for(base, 'admission'), **{**ADMISSION, **overrides})


_BASE = ''


def attach_document(name='evidence.png'):
    """Upload one file and return the reference an answer stores.

    Anonymous: the document endpoint accepts an upload from somebody with no
    account, because the graduation award is claimable that way and requires
    proof of completion.
    """
    response = requests.post(f'{_BASE}/api/documents/',
                             files={'file': (name, PNG, 'image/png')})
    if response.status_code not in (200, 201):
        return 'document:0'
    body = response.json()
    return body.get('reference') or f"document:{body.get('id')}"


def fill_from_schema(schema, **overrides):
    """Every required answer a schema asks for, filled plausibly.

    Built from the schema rather than written out, so a form that gains a
    question is still submittable here and the audit does not quietly stop
    covering it.
    """
    filler = {
        'text': 'Recorded for the audit', 'long_text': 'Recorded for the audit.',
        'email': f'journey.{STAMP}@example.com', 'phone': '8675550143',
        'date': '2026-09-01', 'money': '900', 'integer': '1', 'percent': '85',
        'boolean': 'false', 'confirm': 'true', 'signature': 'Journey Student',
        'sin': '199999996',
    }
    answers = {}
    for field in schema['fields']:
        if field['computed'] or not field['required']:
            continue
        key, kind = field['key'], field['type']
        if kind == 'choice':
            answers[key] = field['choices'][0]['value']
        elif kind in ('file', 'files'):
            # A real upload, not the word 'provided'. A required document
            # question is satisfied by a `document:N` reference and by nothing
            # else, so a filler string made every form that asks for one
            # unsubmittable — which is how six forms came to require documents
            # before anybody noticed the upload path was broken.
            reference = attach_document()
            answers[key] = [reference] if kind == 'files' else reference
        elif kind == 'table':
            answers[key] = [{
                column['key']: (column['choices'][0]['value']
                                if column['type'] == 'choice'
                                else filler.get(column['type'], 'Recorded'))
                for column in field['columns']
            }]
        else:
            answers[key] = filler.get(kind, 'Recorded for the audit')
    answers.update(overrides)
    return answers


def awarded_on(person) -> Decimal:
    """What this person's dashboard says has been awarded, right now.

    Read as a baseline and compared as a delta. The totals are cumulative over
    every application somebody holds, so a check written against an absolute
    figure passes or fails on what earlier sections of this audit happened to
    leave behind.
    """
    return Decimal(person.get('/api/dashboard/').json()['money']['awarded'])


def upload(person, path='/api/documents/', name='transcript.png'):
    return person.http.post(
        f'{person.base}{path}',
        files={'file': (name, PNG, 'image/png')},
    )


def confirm_enrolment(base, app_id, tuition='9000'):
    """Answer the registrar's form, the way the institution does.

    Built from the enrolment schema rather than written out: this audit's first
    draft posted `official_title` and `signed_on`, which that form has never
    asked for, and omitted three fields it requires. Tuition is funded against
    the registrar's figure, so an application whose verification never comes
    back cannot be forwarded or approved by anybody.
    """
    token = enrolment_token(app_id)
    if not token:
        return None, None
    answers = fill_from_schema(schema_for(base, 'enrollment_verification'), **{
        'is_enrolled': 'true',
        'course_load': 'full_time',
        'semester_start': '2026-09-01',
        'semester_end': '2026-12-31',
        'confirmed_tuition': tuition,
        'registrar_name': 'R. Registrar',
        'registrar_title': 'Registrar',
        'institution_name': 'Aurora College',
        'completed_on': '2026-08-17',
    })
    return token, requests.post(f'{base}/api/enrolment/{token}/',
                                json={'answers': answers})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    base = parser.parse_args().base.rstrip('/')
    global _BASE
    _BASE = base

    admin, director, worker, finance = (Session(base, n) for n in
                                        ('admin', 'director', 'worker', 'finance'))
    section('Signing in as the office')
    signed_in = all([
        admin.login('admin@dgg.test'), director.login('director@dgg.test'),
        worker.login('worker@dgg.test'), finance.login('finance@dgg.test'),
    ])
    if not check('admin, director, support worker and finance can sign in', signed_in,
                 'run: python manage.py seed_demo'):
        return 1

    both, dggr_only, on_sfa = audit_signup(base)
    if both is None:
        return 1

    app_one = audit_clean_approval(base, both, admin, director)
    audit_information_loop(base, both, admin)
    audit_breakdown(base, both, dggr_only, on_sfa, admin)
    audit_money_is_only_money_when_decided(base, both, admin)
    audit_office_edit(base, both, admin)
    audit_forward_versus_decide(base, both, admin, director)
    audit_every_type(base, both, admin, worker)

    section('Result')
    print(f'  {checks - len(failures)} of {checks} checks passed')
    if failures:
        print('\n  Failed:')
        for failure in failures:
            print(f'    · {failure}')
        return 1
    print(f'  (application {app_one} walked the clean path)')
    return 0


# ── 1. Sign-up decides the streams, and they are saved ───────────────────────

def audit_signup(base):
    section('Sign-up — the streams a person qualifies for, saved as tags')

    both, response = register(base, 'both')
    if not check('somebody registered and a beneficiary can register',
                 both is not None,
                 '' if both else f'{response.status_code} {response.text[:300]}'):
        return None, None, None

    body = response.json()
    check('the account comes back carrying its funding tags',
          body.get('eligible_streams') == ['psssp', 'dggr'],
          str(body.get('eligible_streams')))
    check('and the date the screening was assessed',
          bool(body.get('eligibility_assessed_at')), str(body.get('eligibility_assessed_at')))

    mine = both.get('/api/me/')
    check('the student can read their own tags back',
          mine.status_code == 200 and mine.json().get('eligible_streams') == ['psssp', 'dggr'],
          f'{mine.status_code} {mine.text[:200]}')

    # The tags are the office's decision about a person, not a preference.
    both.patch('/api/me/', json={'eligible_streams': ['psssp', 'ucepp', 'dggr']})
    check('and cannot widen them by editing their own profile',
          both.get('/api/me/').json().get('eligible_streams') == ['psssp', 'dggr'],
          str(both.get('/api/me/').json().get('eligible_streams')))

    dggr_only, response = register(base, 'dggronly', indian_act_registered='no')
    check('a beneficiary who is not registered is tagged DGGR alone',
          dggr_only is not None and response.json().get('eligible_streams') == ['dggr'],
          response.text[:200])

    # An SFA recipient keeps the DGGR bursary and loses the C-DFN streams. This
    # is where the UCEPP case used to be tested; the screening no longer asks
    # the one question that reaches that stream, at the owner's request.
    on_sfa, response = register(base, 'onsfa', receives_sfa='yes')
    check('a student on SFA is tagged DGGR alone',
          on_sfa is not None and response.json().get('eligible_streams') == ['dggr'],
          response.text[:200])

    _, refused = register(base, 'refused',
                          indian_act_registered='no', deline_beneficiary='no')
    check('somebody who qualifies for nothing cannot register at all',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    check('and is told why rather than just refused',
          'Indian Act' in refused.text, refused.text[:300])

    return both, dggr_only, on_sfa


# ── 2. The first application: reviewed in full, then approved ────────────────

def audit_clean_approval(base, student, admin, director):
    section('Application one — read in full by the office, then approved')

    sent = student.post('/api/applications/',
                        json={'type': 'admission', 'answers': admission_answers(base)})
    if not check('the student files an admission application',
                 sent.status_code == 201,
                 f'{sent.status_code} {sent.text[:400]}'):
        return None
    app_id = sent.json()['id']
    print(f'        application {app_id}')

    check('the stream was decided by the office, not sent by the browser',
          sent.json()['stream'] == 'psssp', sent.json().get('stream'))

    # ── The office opens it and can read every answer ──
    seen = admin.get(f'/api/applications/{app_id}/')
    if check('an administrator can open it', seen.status_code == 200):
        detail = seen.json()
        schema = admin.get('/api/schemas/admission/').json()
        asked = [f['key'] for f in schema['fields']
                 if f['required'] and not f['computed'] and not f['private']]
        unreadable = [key for key in asked if key not in (detail.get('answers') or {})]
        check('and every required answer the form asked for is on the screen',
              not unreadable, f'missing: {unreadable}')
        check('the Social Insurance Number is shown masked, never in full',
              (detail.get('identifiers') or {}).get('sin', '').endswith('996')
              and '199999996' not in seen.text,
              str(detail.get('identifiers')))
        check('and never lands in the answers the screen prints',
              'sin' not in (detail.get('answers') or {}))
        check('the bank details reached finance without reaching the answers',
              (detail.get('banking') or {}).get('on_file') is True
              and 'account_number' not in (detail.get('answers') or {}),
              str(detail.get('banking')))
        check('the applicant’s own history is on the record',
              any(e['action'] == 'submitted' for e in detail.get('events', [])))

    # ── The institution confirms, because tuition is funded against its figure ──
    blocked = admin.post(f'/api/applications/{app_id}/transition/',
                         json={'action': 'reviewed'})
    check('the reviewer records that they have read it', blocked.status_code == 200,
          f'{blocked.status_code} {blocked.text[:200]}')

    too_early = admin.post(f'/api/applications/{app_id}/transition/',
                           json={'action': 'approved'})
    check('it cannot be approved before the institution confirms the enrolment',
          too_early.status_code == 409, f'{too_early.status_code} {too_early.text[:200]}')
    check('and the refusal names what is blocking it',
          'enrolment' in too_early.text.lower(), too_early.text[:200])

    token, answered = confirm_enrolment(base, app_id)
    check('the registrar was sent a verification link at submission', bool(token))
    check('the institution completes it without an account',
          answered is not None and answered.status_code == 200,
          f'{answered.status_code} {answered.text[:250]}' if answered else 'no token')

    # ── Priced, then decided ──
    preview = admin.get(f'/api/applications/{app_id}/decision-preview/')
    if check('the office can see what it would award before recording anything',
             preview.status_code == 200, preview.text[:200]):
        trace = preview.json()
        check('and every rule considered is in the trace, fired or not',
              len(trace.get('rules', [])) > 1, str(len(trace.get('rules', []))))
        check('with a reason against each one',
              all(rule.get('reason') for rule in trace.get('rules', [])))

    priced = admin.post(f'/api/applications/{app_id}/price/')
    check('the award is recorded', priced.status_code == 201,
          f'{priced.status_code} {priced.text[:300]}')

    approved = admin.post(f'/api/applications/{app_id}/transition/',
                          json={'action': 'approved'})
    check('an administrator approves it without forwarding it first',
          approved.status_code == 200, f'{approved.status_code} {approved.text[:300]}')
    check('and the application says so', approved.status_code == 200
          and approved.json()['status'] == 'approved',
          approved.json().get('status') if approved.status_code == 200 else '')

    told = director.get('/api/notifications/')
    check('the director is told it was decided without them',
          told.status_code == 200
          and any('approved' in n['title'].lower() or 'Approved' in n['title']
                  for n in told.json().get('results', told.json())
                  if isinstance(n, dict)),
          told.text[:300])

    student_notices = student.get('/api/notifications/')
    check('and the student is told the decision',
          student_notices.status_code == 200 and 'approved' in student_notices.text.lower(),
          student_notices.text[:200])

    return app_id


def enrolment_token(app_id):
    """The token the registrar was emailed, read out of the outbox.

    There is no endpoint that hands a token to staff, deliberately — it is the
    registrar's only credential. The audit reads it the way the registrar
    would: out of the message that was queued for them.

    Read out of the queued email rather than off the row, so this also proves
    the message the institution receives carries a link that works — a token
    that exists in the database and never reaches anybody funds nothing.
    """
    queued = (OutboundEmail.objects
              .filter(body_html__contains='/enrolment/')
              .order_by('-id'))
    for message in queued[:20]:
        found = re.search(r'/enrolment/([A-Za-z0-9_\-]+)', message.body_html)
        if not found:
            continue
        token = found.group(1)
        from funding.models import EnrollmentVerification
        if EnrollmentVerification.objects.filter(
                token=token, application_id=app_id).exists():
            return token
    return None


# ── 3. The more-information loop, twice ──────────────────────────────────────

def audit_information_loop(base, student, admin):
    section('Application two — the office asks twice, the student answers twice')

    sent = student.post('/api/applications/', json={
        'type': 'admission',
        'answers': admission_answers(base, institution_name='Northern Lakes College'),
    })
    if not check('the student files a second application', sent.status_code == 201,
                 f'{sent.status_code} {sent.text[:300]}'):
        return
    app_id = sent.json()['id']
    print(f'        application {app_id}')
    check('a filed application is not editable while nobody has asked for anything',
          sent.json()['can_revise'] is False)

    # ── Round one: an answer ──
    note = 'Your programme start date does not match the letter of admission.'
    asked = admin.post(f'/api/applications/{app_id}/transition/',
                       json={'action': 'info_requested', 'note': note})
    check('the office asks for more, in its own words', asked.status_code == 200,
          f'{asked.status_code} {asked.text[:200]}')

    seen = student.get(f'/api/applications/{app_id}/')
    if check('the student can open it', seen.status_code == 200):
        body = seen.json()
        check('the application is labelled as needing an update',
              body['status'] == 'info_requested', body['status'])
        check('and the student is shown exactly what was asked',
              (body.get('information_requested') or {}).get('note') == note,
              repr((body.get('information_requested') or {}).get('note')))
        check('and who asked for it',
              bool((body.get('information_requested') or {}).get('asked_by')))
        check('and it is now editable', body['can_revise'] is True)

    notices = student.get('/api/notifications/')
    rows = notices.json().get('results', notices.json())
    check('a notice is waiting in the student’s portal, not only in their email',
          any(str(app_id) in str(n.get('link', '')) for n in rows if isinstance(n, dict)),
          notices.text[:300])

    revised = student.post(f'/api/applications/{app_id}/revise/', json={
        'answers': admission_answers(base,
                                     institution_name='Northern Lakes College',
                                     program_start='2026-09-08'),
        'note': 'Corrected the start date to match the letter.',
    })
    check('the student corrects the answer and sends it back',
          revised.status_code == 200, f'{revised.status_code} {revised.text[:300]}')
    check('and it goes back into the queue rather than sitting in limbo',
          revised.status_code == 200 and revised.json()['status'] == 'under_review',
          revised.json().get('status') if revised.status_code == 200 else '')
    check('the corrected answer is what is now on file',
          revised.status_code == 200
          and revised.json()['answers']['program_start'] == '2026-09-08',
          str(revised.json().get('answers', {}).get('program_start'))
          if revised.status_code == 200 else '')

    office_notices = admin.get('/api/notifications/')
    check('the office is told the student has answered',
          'answered your request' in office_notices.text.lower()
          or 'updated their' in office_notices.text.lower(),
          office_notices.text[:300])

    # ── Round two: a document ──
    second = 'The transcript you attached is unreadable. Please upload it again.'
    asked_again = admin.post(f'/api/applications/{app_id}/transition/',
                             json={'action': 'info_requested', 'note': second})
    check('the office asks a second time, this time about a document',
          asked_again.status_code == 200, f'{asked_again.status_code} {asked_again.text[:200]}')

    reopened = student.get(f'/api/applications/{app_id}/').json()
    check('the application is labelled as needing an update again',
          reopened['status'] == 'info_requested', reopened['status'])
    check('and the second request is the one shown, not the first',
          (reopened.get('information_requested') or {}).get('note') == second,
          repr((reopened.get('information_requested') or {}).get('note')))

    uploaded = student.http.post(
        f'{base}/api/documents/',
        data={'application': app_id, 'field_key': 'doc_transcript'},
        files={'file': ('transcript.png', PNG, 'image/png')},
    )
    if not check('the student uploads a replacement document',
                 uploaded.status_code in (200, 201),
                 f'{uploaded.status_code} {uploaded.text[:300]}'):
        return
    reference = uploaded.json().get('reference') or f"document:{uploaded.json().get('id')}"

    resent = student.post(f'/api/applications/{app_id}/revise/', json={
        'answers': admission_answers(base,
                                     institution_name='Northern Lakes College',
                                     program_start='2026-09-08',
                                     doc_transcript=reference),
        'note': 'Re-scanned the transcript.',
    })
    check('and sends the application back with it attached',
          resent.status_code == 200, f'{resent.status_code} {resent.text[:300]}')
    check('the office sees it under review once more',
          resent.status_code == 200 and resent.json()['status'] == 'under_review',
          resent.json().get('status') if resent.status_code == 200 else '')

    if resent.status_code == 200:
        attached = resent.json().get('documents') or []
        check('the replacement is listed against the question it answers',
              any(d.get('field_key') == 'doc_transcript' for d in attached),
              str(attached))
        if attached:
            opened = admin.get(f"/api/documents/{attached[0]['id']}/")
            check('and the office can actually open it',
                  opened.status_code == 200, f'{opened.status_code} {opened.text[:120]}')

    history = admin.get(f'/api/applications/{app_id}/').json().get('events', [])
    actions = [event['action'] for event in history]
    check('the whole exchange is on the record, in order',
          actions.count('info_requested') == 2 and actions.count('info_provided') == 2,
          str(actions))


# ── 4. The funding breakdown ─────────────────────────────────────────────────

def audit_breakdown(base, both, dggr_only, on_sfa, admin):
    section('The funding breakdown — every stream the student qualifies for')

    def priced_lines(student, label, tuition='9000'):
        sent = student.post('/api/applications/', json={
            'type': 'admission',
            'answers': admission_answers(base, tuition_requested=tuition),
        })
        if sent.status_code != 201:
            check(f'{label}: the application is filed', False,
                  f'{sent.status_code} {sent.text[:300]}')
            return None, []
        app_id = sent.json()['id']

        confirm_enrolment(base, app_id, tuition=tuition)

        preview = admin.get(f'/api/applications/{app_id}/decision-preview/')
        if preview.status_code != 200:
            check(f'{label}: it can be priced', False, preview.text[:200])
            return app_id, []
        return app_id, [rule for rule in preview.json()['rules'] if rule['applied']]

    # A student who qualifies for one stream is funded from one.
    _, dggr_lines = priced_lines(dggr_only, 'DGGR only')
    codes = {line['code'] for line in dggr_lines}
    check('a student eligible for DGGR alone is funded from DGGR alone',
          codes and all(code.startswith('dggr') for code in codes), str(sorted(codes)))
    # `codes` must be non-empty for this to mean anything. Written as a bare
    # `not any(...)` it passed on an unpriced application, which is exactly the
    # shape of a test that reports green because nothing happened.
    check('and gets nothing from PSSSP',
          codes and not any(code.startswith('psssp') for code in codes),
          str(sorted(codes)))

    # A student who qualifies for both gets both. §7: "students may receive both
    # C-DFN PSSSP Bursaries and DGGR Bursaries, if they are eligible for both."
    app_id, mixed = priced_lines(both, 'both streams')
    codes = {line['code'] for line in mixed}
    check('a student eligible for both is funded from both',
          any(c.startswith('psssp') for c in codes) and any(c.startswith('dggr') for c in codes),
          str(sorted(codes)))

    tuition_paid = sum(Decimal(line['amount']) for line in mixed
                       if line['category'] == 'tuition')
    check('and no two streams fund the same tuition dollar',
          tuition_paid > 0 and tuition_paid <= Decimal('9000'),
          f'{tuition_paid} against a $9,000 bill')

    # SFA withdraws the C-DFN streams for this term without touching the
    # account's tags. UCEPP is not exercised here: nothing in the screening
    # reaches it — see accounts/services/eligibility.py.
    _, sfa_lines = priced_lines(on_sfa, 'on SFA')
    codes = {line['code'] for line in sfa_lines}
    check('a student on SFA is funded from DGGR alone',
          codes and all(code.startswith('dggr') for code in codes), str(sorted(codes)))
    check('and gets nothing from PSSSP or UCEPP',
          codes and not any(code.startswith(('psssp', 'ucepp')) for code in codes),
          str(sorted(codes)))

    if app_id is None:
        return

    # ── The office rewrites the breakdown and adds a row ──
    admin.post(f'/api/applications/{app_id}/price/')
    before = admin.get(f'/api/applications/{app_id}/').json()
    line_count = len((before.get('decision') or {}).get('lines', []))

    categories = admin.get(f'/api/applications/{app_id}/award-categories/')
    check('the categories a line may be filed under come from the server',
          categories.status_code == 200 and len(categories.json()) > 1,
          categories.text[:200])

    edited = admin.post(f'/api/applications/{app_id}/award/', json={
        'lines': [
            {'category': 'tuition', 'description': 'Tuition as billed', 'amount': '5000.00'},
            {'category': 'living', 'description': 'Living allowance', 'amount': '4800.00'},
            # The row the rules have no rate for. This is what the editor is for.
            {'category': 'books', 'description': 'Mandatory studio kit', 'amount': '325.00'},
        ],
        'note': 'Studio kit agreed with the institution.',
    })
    if check('an administrator can set the breakdown by hand',
             edited.status_code == 201, f'{edited.status_code} {edited.text[:300]}'):
        decision = edited.json()
        check('the added row is there', len(decision['lines']) == 3, str(len(decision['lines'])))
        check('and it added a row rather than replacing the lot with one',
              len(decision['lines']) > 1 and line_count > 0,
              f'was {line_count}, now {len(decision["lines"])}')
        check('the total is what the lines add up to',
              Decimal(decision['total']) == Decimal('10125.00'), decision['total'])

    after = admin.get(f'/api/applications/{app_id}/').json()
    # Against the decision, not `awarded_total`: this application has not been
    # approved, so the amount awarded is correctly nothing. The hand-set figure
    # is what the current decision now says.
    check('the current decision is the hand-set one, not the priced one',
          Decimal((after.get('decision') or {})['total']) == Decimal('10125.00'),
          str((after.get('decision') or {}).get('total')))
    check('and an undecided application still reports no award',
          Decimal(after['awarded_total']) == 0, after['awarded_total'])

    admin.post(f'/api/applications/{app_id}/transition/', json={'action': 'reviewed'})
    approved = admin.post(f'/api/applications/{app_id}/transition/',
                          json={'action': 'approved'})
    if check('once approved, the hand-set total is what is awarded',
             approved.status_code == 200, f'{approved.status_code} {approved.text[:200]}'):
        check('and the application reports it',
              Decimal(approved.json()['awarded_total']) == Decimal('10125.00'),
              approved.json()['awarded_total'])

    history = admin.get(f'/api/applications/{app_id}/decisions/')
    check('the earlier pricing is kept, superseded rather than overwritten',
          history.status_code == 200 and len(history.json()) >= 2,
          str(len(history.json())) if history.status_code == 200 else history.text[:200])
    if history.status_code == 200:
        current = [d for d in history.json() if d['is_current']]
        check('and exactly one decision is in force',
              len(current) == 1, str(len(current)))

    worker_try = Session(base, 'worker')
    worker_try.login('worker@dgg.test')
    refused = worker_try.post(f'/api/applications/{app_id}/award/',
                              json={'lines': [{'category': 'tuition',
                                               'description': 'x', 'amount': '99999'}]})
    check('a support worker cannot set an award by hand',
          refused.status_code == 403, f'{refused.status_code} {refused.text[:200]}')


# ── A pricing is not a promise ───────────────────────────────────────────────

def audit_money_is_only_money_when_decided(base, student, admin):
    """Reported by the owner against his own test run.

    The office reviewed an application and recorded an award on it. The
    institution had not confirmed the enrolment and nobody had approved
    anything, and the student's portal showed the amount as though it had been
    granted. The application was then declined, and the portal went on showing
    it.

    Two faults, one cause: every total was scoped to the current *decision* and
    none of them asked what had happened to the *application*.
    """
    section('A pricing is not a promise')

    sent = student.post('/api/applications/',
                        json={'type': 'admission', 'answers': admission_answers(base)})
    if not check('the student files an application', sent.status_code == 201,
                 f'{sent.status_code} {sent.text[:250]}'):
        return
    app_id = sent.json()['id']

    admin.post(f'/api/applications/{app_id}/transition/', json={'action': 'reviewed'})

    # Baselines. Everything below is asserted as a movement from here.
    student_before, office_before = awarded_on(student), awarded_on(admin)

    # ── Before the institution has answered ──
    refused = admin.post(f'/api/applications/{app_id}/price/')
    check('an award cannot be recorded before the institution confirms',
          refused.status_code == 409, f'{refused.status_code} {refused.text[:200]}')
    check('and the refusal names what is blocking it',
          refused.json().get('blocked_by') == 'enrolment_verification',
          refused.text[:200])
    check('while the office can still see a working',
          admin.get(f'/api/applications/{app_id}/decision-preview/').status_code == 200)

    # ── Confirmed, priced, still nobody has decided ──
    confirm_enrolment(base, app_id)
    priced = admin.post(f'/api/applications/{app_id}/price/')
    if not check('once confirmed, the award records', priced.status_code == 201,
                 f'{priced.status_code} {priced.text[:250]}'):
        return
    total = Decimal(priced.json()['total'])
    check('and it is a real figure', total > 0, str(total))

    seen = student.get(f'/api/applications/{app_id}/').json()
    check('the student is NOT told they have been awarded it yet',
          Decimal(seen['awarded_total']) == 0, seen['awarded_total'])
    check('and their dashboard does not count it',
          awarded_on(student) == student_before,
          f'{student_before} -> {awarded_on(student)}')
    check('the office does not count it either, so its total matches the payment file',
          awarded_on(admin) == office_before,
          f'{office_before} -> {awarded_on(admin)}')

    # ── Approved: now it is money ──
    approved = admin.post(f'/api/applications/{app_id}/transition/',
                          json={'action': 'approved'})
    check('the office approves it', approved.status_code == 200,
          f'{approved.status_code} {approved.text[:200]}')
    seen = student.get(f'/api/applications/{app_id}/').json()
    check('now the student is shown the amount',
          Decimal(seen['awarded_total']) == total, seen['awarded_total'])
    check('and the dashboard rises by exactly that amount',
          awarded_on(student) == student_before + total,
          f'{student_before} + {total} != {awarded_on(student)}')

    # ── Declined: it stops being money again ──
    second = student.post('/api/applications/',
                          json={'type': 'admission', 'answers': admission_answers(base)})
    if not check('a second application is filed', second.status_code == 201,
                 f'{second.status_code} {second.text[:250]}'):
        return
    other = second.json()['id']
    admin.post(f'/api/applications/{other}/transition/', json={'action': 'reviewed'})
    confirm_enrolment(base, other)
    admin.post(f'/api/applications/{other}/price/')
    declined = admin.post(f'/api/applications/{other}/transition/',
                          json={'action': 'declined', 'note': 'Not an approved programme.'})
    check('the office declines it', declined.status_code == 200,
          f'{declined.status_code} {declined.text[:200]}')

    refused_view = student.get(f'/api/applications/{other}/').json()
    check('a declined application reports no award',
          Decimal(refused_view['awarded_total']) == 0, refused_view['awarded_total'])
    check('but the pricing is kept, so an appeal can argue with it',
          (refused_view.get('decision') or {}).get('total') is not None,
          str(refused_view.get('decision')))
    check("and the declined amount never entered the student's total",
          awarded_on(student) == student_before + total,
          f'expected {student_before + total}, got {awarded_on(student)}')


# ── 5. The office correcting an application on the student's behalf ──────────

def audit_office_edit(base, student, admin):
    section('The office edits an application for the student, who is told')

    sent = student.post('/api/applications/', json={
        'type': 'admission', 'answers': admission_answers(base, city='Deline'),
    })
    if not check('the student files an application', sent.status_code == 201,
                 f'{sent.status_code} {sent.text[:300]}'):
        return
    app_id = sent.json()['id']

    before = student.get('/api/notifications/')
    before_count = len(before.json().get('results', before.json()))

    amended = admin.post(f'/api/applications/{app_id}/amend/', json={
        'answers': admission_answers(base, city='Délı̨nę',
                                     institution_name='Aurora College'),
        'note': 'Corrected the spelling of the community, taken over the phone.',
    })
    if check('an administrator can correct it on the applicant’s behalf',
             amended.status_code == 200, f'{amended.status_code} {amended.text[:300]}'):
        body = amended.json()
        check('the correction is what is now on file',
              body['answers']['city'] == 'Délı̨nę', body['answers'].get('city'))
        check('and the application has not moved out of the queue it was in',
              body['status'] == 'submitted', body['status'])
        check('the edit is on the record as an amendment, not as a review step',
              any(e['action'] == 'amended' for e in body['events']),
              str([e['action'] for e in body['events']]))

    after = student.get('/api/notifications/')
    rows = after.json().get('results', after.json())
    check('the student is told their application was changed for them',
          len(rows) > before_count, f'{before_count} → {len(rows)}')

    worker_try = Session(base, 'worker')
    worker_try.login('worker@dgg.test')
    refused = worker_try.post(f'/api/applications/{app_id}/amend/',
                              json={'answers': admission_answers(base)})
    check('a support worker cannot rewrite a filed application',
          refused.status_code == 403, f'{refused.status_code} {refused.text[:200]}')

    student_try = student.post(f'/api/applications/{app_id}/revise/',
                               json={'answers': admission_answers(base)})
    check('and the student cannot edit it while nobody has asked them to',
          student_try.status_code == 409, f'{student_try.status_code} {student_try.text[:200]}')


# ── 6. Forwarded to the director, or decided by the office ───────────────────

def audit_forward_versus_decide(base, student, admin, director):
    section('Forwarded for a decision, or decided by the office')

    def reviewed_application():
        sent = student.post('/api/applications/', json={
            'type': 'hardship_bursary',
            'answers': fill_from_schema(
                schema_for(base, 'hardship_bursary'),
                amount_requested='900'),
        })
        if sent.status_code != 201:
            return None, sent
        app_id = sent.json()['id']
        admin.post(f'/api/applications/{app_id}/transition/', json={'action': 'reviewed'})
        return app_id, sent

    # ── Forwarded ──
    app_id, sent = reviewed_application()
    if check('a hardship bursary is filed and reviewed', app_id is not None,
             f'{sent.status_code} {sent.text[:300]}'):
        forwarded = admin.post(f'/api/applications/{app_id}/transition/',
                               json={'action': 'forwarded'})
        check('the office forwards it for a decision', forwarded.status_code == 200,
              f'{forwarded.status_code} {forwarded.text[:200]}')
        check('and it is waiting on the director',
              forwarded.status_code == 200
              and forwarded.json()['status'] == 'awaiting_decision',
              forwarded.json().get('status') if forwarded.status_code == 200 else '')

        queued = director.get('/api/notifications/')
        check('the director is told there is something waiting for them',
              'waiting for a decision' in queued.text.lower(), queued.text[:300])

        decided = director.post(f'/api/applications/{app_id}/transition/',
                                json={'action': 'approved'})
        check('the director approves it', decided.status_code == 200,
              f'{decided.status_code} {decided.text[:300]}')

        capped = admin.post(f'/api/applications/{app_id}/price/')
        if capped.status_code == 201:
            check('and it is paid at the policy cap, not at what was asked for',
                  Decimal(capped.json()['total']) == Decimal('500.00'),
                  f"asked $900, awarded {capped.json()['total']}")

    # ── Decided by the office instead ──
    app_id, sent = reviewed_application()
    if check('a second one is filed and reviewed', app_id is not None,
             f'{sent.status_code} {sent.text[:300]}'):
        straight = admin.post(f'/api/applications/{app_id}/transition/',
                              json={'action': 'approved'})
        check('the administrator approves it without forwarding it',
              straight.status_code == 200, f'{straight.status_code} {straight.text[:300]}')
        if straight.status_code == 200:
            actions = [e['action'] for e in straight.json()['events']]
            check('and nothing was forwarded on the way',
                  'forwarded' not in actions, str(actions))

        told = director.get('/api/notifications/')
        check('the director is told after the fact, because they answer for it',
              'without being forwarded' in told.text.lower(), told.text[:400])

    # ── A support worker may not decide either way ──
    app_id, _ = reviewed_application()
    if app_id:
        worker_try = Session(base, 'worker')
        worker_try.login('worker@dgg.test')
        refused = worker_try.post(f'/api/applications/{app_id}/transition/',
                                  json={'action': 'approved'})
        check('a support worker cannot approve anything',
              refused.status_code == 403, f'{refused.status_code} {refused.text[:200]}')


# ── 7. The same path for every application type ──────────────────────────────

# Filed without an account, so they are not posted as a signed-in student.
GUEST_TYPES = {'graduation_bursary', 'practicum'}

# What each type needs beyond the schema's own required fields for the rules to
# produce something. Everything else is filled from the schema.
EXTRAS = {
    'travel': {'travel_purpose': 'start_of_study', 'amount_requested': '2500'},
    'emergency_relief': {'amount_requested': '2000'},
    'hardship_bursary': {'amount_requested': '900'},
    'academic_scholarship': {'gpa_achieved': '85'},
    'graduation_bursary': {'credential': 'masters_degree'},
}


def audit_every_type(base, student, admin, worker):
    section('Every application type takes the same path')

    schemas = admin.get('/api/schemas/').json()
    check('the portal publishes a schema for every type it offers',
          len(schemas) >= 10, str(len(schemas)))

    for schema in schemas:
        slug = schema['slug']
        if slug == 'enrollment_verification':
            continue                    # the registrar's form, not an application
        answers = fill_from_schema(schema, **EXTRAS.get(slug, {}))

        if slug in GUEST_TYPES:
            sent = requests.post(f'{base}/api/guest-applications/',
                                 json={'type': slug, 'answers': answers})
            check(f'{slug}: can be claimed without an account',
                  sent.status_code == 201, f'{sent.status_code} {sent.text[:250]}')
            continue

        sent = student.post('/api/applications/', json={'type': slug, 'answers': answers})
        if not check(f'{slug}: the student can file one', sent.status_code == 201,
                     f'{sent.status_code} {sent.text[:250]}'):
            continue
        app_id = sent.json()['id']

        reviewed = worker.post(f'/api/applications/{app_id}/transition/',
                               json={'action': 'reviewed'})
        check(f'{slug}: a support worker can review it', reviewed.status_code == 200,
              f'{reviewed.status_code} {reviewed.text[:200]}')

        preview = admin.get(f'/api/applications/{app_id}/decision-preview/')
        check(f'{slug}: it can be priced without an unconfigured rate',
              preview.status_code == 200 and not preview.json().get('missing_rates'),
              str(preview.json().get('missing_rates'))
              if preview.status_code == 200 else preview.text[:200])

        # Admission and continuing funding wait on the registrar; everything
        # else can be decided straight away.
        if slug in ('admission', 'continuing_funding'):
            confirm_enrolment(base, app_id)

        decided = admin.post(f'/api/applications/{app_id}/transition/',
                             json={'action': 'approved'})
        check(f'{slug}: the office can decide it', decided.status_code == 200,
              f'{decided.status_code} {decided.text[:250]}')


if __name__ == '__main__':
    sys.exit(main())
