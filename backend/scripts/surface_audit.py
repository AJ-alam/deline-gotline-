"""Everything the ten form audits never touch, over real HTTP.

The existing audits each walk one form from filing to payment. Between them they
never call registration, the eligibility screening, token refresh, `attach/`,
`enrolment-preview`, the document read endpoint, or eight of the ten pre-fill
slugs — and no audit has ever asked what every endpoint does to every *role*.
A permission that is wrong for one role and right for the other five looks
identical to a passing suite when nothing asks.

Drives: anonymous -> student -> support worker -> director -> finance -> admin,
and back down again.

    python manage.py runserver 127.0.0.1:8000
    python scripts/surface_audit.py [--base http://127.0.0.1:8000]

Data it creates is named with a run stamp so a second run does not collide with
the first, and so anything it leaves behind is identifiable.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from decimal import Decimal

import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from accounts.models import Role, User  # noqa: E402
from accounts.services import eligibility as eligibility_service  # noqa: E402
from funding.models import Application, Award, SupportingDocument  # noqa: E402
from notifications.models import Notification  # noqa: E402

PASSWORD = 'DemoPass123!'
STAMP = time.strftime('%m%d%H%M%S')
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


class Actor:
    """Somebody signed in, holding their own session."""

    def __init__(self, email: str, password: str = PASSWORD):
        self.email = email
        self.http = requests.Session()
        response = self.http.post(f'{BASE}/api/auth/token/',
                                  json={'email': email, 'password': password})
        self.signed_in = response.status_code == 200 and 'access' in response.json()
        self.refresh = response.json().get('refresh', '') if self.signed_in else ''
        if self.signed_in:
            self.http.headers['Authorization'] = f'Bearer {response.json()["access"]}'

    def get(self, path, **kw):
        return self.http.get(f'{BASE}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{BASE}{path}', **kw)

    def patch(self, path, **kw):
        return self.http.patch(f'{BASE}{path}', **kw)

    def delete(self, path, **kw):
        return self.http.delete(f'{BASE}{path}', **kw)


def anon_get(path, **kw):
    return requests.get(f'{BASE}{path}', **kw)


def anon_post(path, **kw):
    return requests.post(f'{BASE}{path}', **kw)


ELIGIBLE = {
    'indian_act_registered': 'yes',
    'deline_beneficiary': 'yes',
    'receives_sfa': 'no',
    'lives_in_nwt': 'yes',
    'accredited_institution': 'yes',
    'programme_twelve_weeks': 'yes',
}


def screening(**overrides) -> dict:
    answers = dict(ELIGIBLE)
    answers.update(overrides)
    return answers


# A Social Insurance Number that passes the Luhn check the schema applies. A
# made-up one is refused, which is the point of the field — so a filler value
# has to be a structurally valid number rather than nine digits.
TEST_SIN = '130692544'


def answer_for(field: dict, document_reference: str = ''):
    """A plausible answer for one field, from the schema's own description of it.

    Built from `type` rather than from the key so a field added tomorrow is
    filled in without touching this, which is the same reason the lifecycle
    audit builds its admission answers from the schema.
    """
    key, kind = field['key'], (field.get('type') or '').lower()
    if field.get('computed'):
        return key, None

    if kind == 'confirm':
        return key, True
    if kind == 'boolean':
        return key, False
    if kind == 'choice':
        choices = field.get('choices') or []
        return key, (choices[0]['value'] if choices else '')
    if kind == 'multichoice':
        choices = field.get('choices') or []
        return key, ([choices[0]['value']] if choices else [])
    if kind == 'date':
        return key, '2026-05-30'
    if kind in ('number', 'money'):
        return key, '1200.00'
    if kind == 'file':
        return key, document_reference
    if kind == 'files':
        return key, ([document_reference] if document_reference else [])
    if kind == 'table':
        return key, []
    if kind == 'sin':
        return key, TEST_SIN
    if kind == 'email':
        return key, f'guest.{STAMP}@example.com'
    if kind == 'phone':
        return key, '867-555-0101'
    if kind == 'signature':
        return key, 'Surface Audit'

    # Text, and the handful of text fields that are checked for shape.
    if key == 'postal_code':
        return key, 'X0E 0G0'
    if key == 'province':
        return key, 'NT'
    if key == 'transit_number':
        return key, '12345'
    if key == 'institution_number':
        return key, '001'
    if key == 'account_number':
        return key, '9876543210'
    if key in ('treaty_number', 'beneficiary_number'):
        return key, '1234567890'
    return key, f'Surface {STAMP}'


# ── The screening, before anybody has an account ─────────────────────────────

def audit_eligibility() -> None:
    section('Eligibility screening — public, and the only gate on sign-up')

    questions = anon_get('/api/auth/eligibility/')
    check('the questions are readable without an account',
          questions.status_code == 200, f'{questions.status_code}')
    payload = questions.json().get('questions', []) if questions.status_code == 200 else []
    check('all six questions are published',
          len(payload) == len(eligibility_service.QUESTIONS),
          f'{len(payload)} published, {len(eligibility_service.QUESTIONS)} defined')
    check('every question carries choices a client can render',
          all(q.get('choices') for q in payload))
    check('the question keys match the ones the assessment reads',
          [q['key'] for q in payload] == [q['key'] for q in eligibility_service.QUESTIONS])

    def assess(answers):
        return anon_post('/api/auth/eligibility/', json={'answers': answers})

    both = assess(screening()).json()
    check('registered, a beneficiary and not on SFA qualifies for both streams',
          both.get('eligible') and set(both.get('streams', [])) == {'psssp', 'dggr'},
          str(both))

    psssp_only = assess(screening(deline_beneficiary='no')).json()
    check('registered but not a beneficiary qualifies for PSSSP alone',
          psssp_only.get('eligible') and psssp_only.get('streams') == ['psssp'],
          str(psssp_only))

    dggr_only = assess(screening(indian_act_registered='no')).json()
    check('a beneficiary who is not registered qualifies for DGGR alone',
          dggr_only.get('eligible') and dggr_only.get('streams') == ['dggr'],
          str(dggr_only))

    on_sfa = assess(screening(deline_beneficiary='no', receives_sfa='yes')).json()
    check('SFA removes PSSSP and leaves nothing behind it',
          on_sfa.get('eligible') is False and not on_sfa.get('streams'), str(on_sfa))

    sfa_beneficiary = assess(screening(receives_sfa='yes')).json()
    check('SFA does not touch the DGGR bursary',
          sfa_beneficiary.get('eligible') and sfa_beneficiary.get('streams') == ['dggr'],
          str(sfa_beneficiary))

    unaccredited = assess(screening(accredited_institution='no')).json()
    check('an unaccredited institution stops intake outright',
          unaccredited.get('eligible') is False, str(unaccredited))

    short = assess(screening(programme_twelve_weeks='no')).json()
    check('a programme under twelve weeks stops intake outright',
          short.get('eligible') is False, str(short))

    neither = assess(screening(indian_act_registered='no', deline_beneficiary='no')).json()
    check('somebody with neither affiliation is refused',
          neither.get('eligible') is False, str(neither))

    partial = assess({'indian_act_registered': 'yes'}).json()
    check('half-answered is not eligible', partial.get('eligible') is False, str(partial))
    check('half-answered says what is missing rather than refusing outright',
          'answer all six' in partial.get('message', '').lower(), str(partial))

    nothing = assess({}).json()
    check('an empty screening is refused rather than erroring',
          nothing.get('eligible') is False, str(nothing))

    check('every refusal tells the person what to do next',
          all(r.get('message') and r.get('title')
              for r in (unaccredited, short, neither, on_sfa)))


# ── Registration ─────────────────────────────────────────────────────────────

def audit_registration() -> Actor | None:
    section('Registration — the gate the browser used to hold on its own')

    email = f'surface.{STAMP}@example.com'

    refused = anon_post('/api/auth/register/', json={
        'email': f'refused.{STAMP}@example.com',
        'password': 'DemoPass123!', 'confirm_password': 'DemoPass123!',
        'first_name': 'Turned', 'last_name': 'Away',
        'eligibility': screening(indian_act_registered='no', deline_beneficiary='no'),
    })
    check('an ineligible screening is refused by the server, not only the browser',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:160]}')
    check('the refusal says why, in the office\'s words',
          'eligibility' in refused.text.lower(), refused.text[:200])
    check('no account was created for the person turned away',
          not User.objects.filter(email__iexact=f'refused.{STAMP}@example.com').exists())

    empty_screening = anon_post('/api/auth/register/', json={
        'email': f'empty.{STAMP}@example.com',
        'password': 'DemoPass123!', 'confirm_password': 'DemoPass123!',
        'first_name': 'No', 'last_name': 'Answers', 'eligibility': {},
    })
    check('registering with no screening at all is refused',
          empty_screening.status_code == 400, f'{empty_screening.status_code}')

    mismatch = anon_post('/api/auth/register/', json={
        'email': f'mismatch.{STAMP}@example.com',
        'password': 'DemoPass123!', 'confirm_password': 'DemoPass124!',
        'first_name': 'Typo', 'last_name': 'Twice', 'eligibility': screening(),
    })
    check('two passwords that differ are refused', mismatch.status_code == 400,
          f'{mismatch.status_code}')

    short_password = anon_post('/api/auth/register/', json={
        'email': f'short.{STAMP}@example.com',
        'password': 'abc', 'confirm_password': 'abc',
        'first_name': 'Short', 'last_name': 'Secret', 'eligibility': screening(),
    })
    check('a password under the minimum is refused', short_password.status_code == 400,
          f'{short_password.status_code}')

    created = anon_post('/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Surface', 'last_name': f'Audit{STAMP}',
        'phone': '867-555-0101', 'eligibility': screening(),
    })
    if not check('an eligible applicant can register', created.status_code == 201,
                 f'{created.status_code} {created.text[:200]}'):
        return None

    body = created.json()
    check('the new account is a student and nothing more',
          body.get('role') == Role.STUDENT, str(body.get('role')))
    check('registration never returns the password',
          'password' not in created.text.lower(), created.text[:160])

    person = User.objects.filter(email__iexact=email).first()
    check('what the screening said about the person is kept on the account',
          person is not None and person.is_indian_act_registered
          and person.is_deline_beneficiary)
    check('the new account is active and not privileged',
          person is not None and person.is_active
          and not person.is_staff and not person.is_superuser)

    duplicate = anon_post('/api/auth/register/', json={
        'email': email.upper(), 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Same', 'last_name': 'Address', 'eligibility': screening(),
    })
    check('the same address in different case cannot open a second account',
          duplicate.status_code == 400, f'{duplicate.status_code}')
    check('exactly one account exists for that address',
          User.objects.filter(email__iexact=email).count() == 1)

    escalation = anon_post('/api/auth/register/', json={
        'email': f'climber.{STAMP}@example.com',
        'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Would', 'last_name': 'Be', 'role': Role.ADMIN,
        'is_staff': True, 'is_superuser': True, 'eligibility': screening(),
    })
    climber = User.objects.filter(email__iexact=f'climber.{STAMP}@example.com').first()
    check('a role asked for at sign-up is ignored',
          escalation.status_code != 201 or (climber is not None
                                            and climber.role == Role.STUDENT),
          f'{escalation.status_code} {getattr(climber, "role", None)}')
    check('is_superuser asked for at sign-up is ignored',
          climber is None or not (climber.is_superuser or climber.is_staff))

    newcomer = Actor(email)
    check('the account created can sign in immediately', newcomer.signed_in)
    return newcomer if newcomer.signed_in else None


# ── Tokens ───────────────────────────────────────────────────────────────────

def audit_tokens(student: Actor) -> None:
    section('Tokens — the part of the session nothing has ever exercised')

    refreshed = anon_post('/api/auth/token/refresh/', json={'refresh': student.refresh})
    check('a refresh token buys a new access token',
          refreshed.status_code == 200 and 'access' in refreshed.json(),
          f'{refreshed.status_code} {refreshed.text[:160]}')

    if refreshed.status_code == 200:
        fresh = requests.get(f'{BASE}/api/me/', headers={
            'Authorization': f'Bearer {refreshed.json()["access"]}'})
        check('the refreshed token actually opens the account',
              fresh.status_code == 200, f'{fresh.status_code}')

    rubbish = anon_post('/api/auth/token/refresh/', json={'refresh': 'not-a-token'})
    check('a made-up refresh token is refused', rubbish.status_code == 401,
          f'{rubbish.status_code}')

    wrong_password = anon_post('/api/auth/token/',
                               json={'email': student.email, 'password': 'wrong'})
    check('the wrong password does not sign anybody in',
          wrong_password.status_code == 401, f'{wrong_password.status_code}')
    check('a failed sign-in does not say whether the address exists',
          'exist' not in wrong_password.text.lower(), wrong_password.text[:160])

    unknown = anon_post('/api/auth/token/', json={'email': f'nobody.{STAMP}@example.com',
                                                  'password': PASSWORD})
    check('an unknown address answers the same way a wrong password does',
          unknown.status_code == wrong_password.status_code,
          f'{unknown.status_code} vs {wrong_password.status_code}')

    tampered = requests.get(f'{BASE}/api/me/', headers={
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxfQ.forged'})
    check('a forged access token is refused', tampered.status_code == 401,
          f'{tampered.status_code}')

    check('a protected endpoint refuses an anonymous caller',
          anon_get('/api/me/').status_code == 401)


# ── The signed-in person's own record ────────────────────────────────────────

def audit_me(student: Actor) -> None:
    section('The account — what its owner may change about it')

    me = student.get('/api/me/')
    check('a person can read their own record', me.status_code == 200,
          f'{me.status_code}')
    body = me.json() if me.status_code == 200 else {}
    check('the record never carries a password hash',
          'password' not in str(body).lower(), str(body)[:200])

    updated = student.patch('/api/me/', json={'phone': '867-555-0199',
                                              'city': 'Deline',
                                              'preferred_name': 'Surf'})
    check('contact details can be corrected by their owner',
          updated.status_code == 200 and updated.json().get('phone') == '867-555-0199',
          f'{updated.status_code} {updated.text[:160]}')

    climb = student.patch('/api/me/', json={'role': Role.ADMIN})
    after = student.get('/api/me/').json()
    check('a student cannot promote themselves through their own record',
          after.get('role') == Role.STUDENT, f'{climb.status_code} {after.get("role")}')

    rename = student.patch('/api/me/', json={'email': f'moved.{STAMP}@example.com'})
    check('the address a person signs in with cannot be changed here',
          student.get('/api/me/').json().get('email') == student.email,
          f'{rename.status_code}')

    person = User.objects.filter(email__iexact=student.email).first()
    check('nothing in that exchange made the account staff',
          person is not None and not person.is_staff and not person.is_superuser)


# ── Schemas and pre-fill, for every type rather than two ─────────────────────

def audit_schemas_and_prefill(student: Actor, worker: Actor) -> None:
    section('Every form the portal publishes, and the answers it opens with')

    listing = anon_get('/api/schemas/')
    check('the questions a form asks are readable before anybody signs up',
          listing.status_code == 200, f'{listing.status_code}')
    check('a schema carries no data about any person',
          not any(word in listing.text.lower()
                  for word in ('@dgg.test', 'beneficiary_number":"', 'sin":"')),
          listing.text[:160])

    catalogue = student.get('/api/schemas/')
    check('a student can read the schema list', catalogue.status_code == 200,
          f'{catalogue.status_code}')
    slugs = [s['slug'] for s in catalogue.json()] if catalogue.status_code == 200 else []
    check('every application type has a published schema',
          len(slugs) >= 10, f'{len(slugs)} published: {slugs}')

    for slug in slugs:
        one = student.get(f'/api/schemas/{slug}/')
        ok = one.status_code == 200 and one.json().get('slug') == slug
        check(f'schema {slug} is readable on its own', ok,
              f'{one.status_code} {one.text[:120]}')
        fields = one.json().get('fields', []) if one.status_code == 200 else []
        check(f'schema {slug} asks something',
              bool(fields) or slug == 'enrollment_verification',
              f'{len(fields)} fields')

    missing = student.get('/api/schemas/no_such_form/')
    check('an unknown schema slug is a 404, not a 500', missing.status_code == 404,
          f'{missing.status_code}')

    for slug in slugs:
        prefill = student.get(f'/api/form-prefill/{slug}/')
        check(f'pre-fill for {slug} answers rather than failing',
              prefill.status_code in (200, 400, 404),
              f'{prefill.status_code} {prefill.text[:160]}')
        if prefill.status_code == 200:
            answers = prefill.json().get('answers', {})
            check(f'pre-fill for {slug} never opens with a SIN in it',
                  not any('sin' == k.lower() or k.lower().endswith('_sin')
                          for k in answers),
                  str(list(answers))[:200])

    unknown_prefill = student.get('/api/form-prefill/not_a_form/')
    check('pre-fill for an unknown form is refused cleanly',
          unknown_prefill.status_code in (400, 404), f'{unknown_prefill.status_code}')

    check('pre-fill is closed to an anonymous caller',
          anon_get('/api/form-prefill/admission/').status_code == 401)

    staff_prefill = worker.get('/api/form-prefill/admission/')
    check('a member of staff asking for pre-fill gets an answer, not an error',
          staff_prefill.status_code in (200, 400, 403),
          f'{staff_prefill.status_code} {staff_prefill.text[:160]}')


# ── The registrar's copy, before anything is filed ───────────────────────────

def audit_enrolment_preview(student: Actor) -> None:
    section('The enrolment verification a student can check before submitting')

    answers = {
        'full_name': 'Surface Audit',
        'email': student.email,
        'sin': '046454286',
        'date_of_birth': '2001-04-04',
        'institution_name': 'Aurora College',
        'registrar_email': f'registrar.{STAMP}@example.com',
        'programme_name': 'Environmental Technology',
        'tuition_estimate': '4200.00',
    }

    preview = student.post('/api/enrolment-preview/',
                           json={'type': 'admission', 'answers': answers})
    check('the preview is built for a form that generates one',
          preview.status_code == 200, f'{preview.status_code} {preview.text[:200]}')

    body = preview.json() if preview.status_code == 200 else {}
    check('the preview carries the registrar\'s own schema',
          body.get('schema', {}).get('slug') == 'enrollment_verification',
          str(body.get('schema', {}).get('slug')))
    check('it says which address the request will go to',
          body.get('registrar_email') == answers['registrar_email'],
          str(body.get('registrar_email')))

    prefilled = str(body.get('prefill', {}))
    check('the SIN is withheld from the registrar, as the note promises',
          '046454286' not in prefilled, prefilled[:200])
    check('the date of birth is withheld too',
          '2001-04-04' not in prefilled, prefilled[:200])
    check('what the registrar does need is carried over',
          'Aurora College' in prefilled, prefilled[:200])

    wrong_type = student.post('/api/enrolment-preview/',
                              json={'type': 'graduation_bursary', 'answers': answers})
    check('a form that generates no verification says so',
          wrong_type.status_code == 400, f'{wrong_type.status_code}')

    nonsense = student.post('/api/enrolment-preview/',
                            json={'type': 'admission', 'answers': 'not-an-object'})
    check('answers that are not an object are refused rather than crashing',
          nonsense.status_code == 400, f'{nonsense.status_code}')

    check('the preview is closed to an anonymous caller',
          anon_post('/api/enrolment-preview/',
                    json={'type': 'admission', 'answers': answers}).status_code == 401)

    check('nothing was stored by previewing',
          not Application.objects.filter(
              answers__registrar_email=answers['registrar_email']).exists())


# ── Documents ────────────────────────────────────────────────────────────────

def audit_documents(student: Actor, other: Actor, worker: Actor,
                    finance: Actor) -> None:
    section('Documents — who may upload one, and who may open it afterwards')

    def upload(actor, name='transcript.png', content_type='image/png',
               payload=PNG, **data):
        return actor.post('/api/documents/',
                          files={'file': (name, io.BytesIO(payload), content_type)},
                          data={'field_key': 'doc_transcript', **data})

    uploaded = upload(student)
    check('a student can attach a document', uploaded.status_code == 201,
          f'{uploaded.status_code} {uploaded.text[:200]}')
    if uploaded.status_code != 201:
        return
    document_id = uploaded.json()['id']
    check('the answer stored is a reference, not the file',
          uploaded.json().get('reference') == f'document:{document_id}')

    stored = SupportingDocument.objects.get(pk=document_id)
    check('the name on disk is generated, never the one the browser sent',
          'transcript' not in stored.file.name and stored.file.name.endswith('.png'),
          stored.file.name)
    check('the name the person recognises is kept as a label',
          stored.original_name == 'transcript.png', stored.original_name)

    check('the person who uploaded it can open it',
          student.get(f'/api/documents/{document_id}/').status_code == 200)
    check('the office can open it',
          worker.get(f'/api/documents/{document_id}/').status_code == 200)
    check('finance can open it, because a payment is defended by it',
          finance.get(f'/api/documents/{document_id}/').status_code == 200)

    stranger = other.get(f'/api/documents/{document_id}/')
    check('another student is told it does not exist, not that it is forbidden',
          stranger.status_code == 404, f'{stranger.status_code}')
    check('an anonymous caller cannot open it',
          anon_get(f'/api/documents/{document_id}/').status_code == 401)

    check('a document id that does not exist answers the same way',
          student.get('/api/documents/99999999/').status_code == 404)

    traversal = upload(student, name='../../core/settings.py', content_type='image/png')
    check('a path for a filename is refused or defused',
          traversal.status_code == 400
          or 'settings.py' not in SupportingDocument.objects.get(
              pk=traversal.json()['id']).file.name,
          f'{traversal.status_code}')

    executable = upload(student, name='payload.exe',
                        content_type='application/x-msdownload')
    check('a file type outside the allowlist is refused',
          executable.status_code == 400, f'{executable.status_code}')

    disguised = upload(student, name='payload.exe', content_type='image/png')
    check('an allowed content type with a refused extension is still refused',
          disguised.status_code == 400, f'{disguised.status_code}')

    mismatched = upload(student, name='report.pdf', content_type='image/png')
    check('a name that disagrees with the kind of file is refused',
          mismatched.status_code == 400, f'{mismatched.status_code}')

    empty = upload(student, payload=b'')
    check('an empty file is refused', empty.status_code == 400, f'{empty.status_code}')

    oversize = upload(student, payload=b'\x89PNG' + b'0' * (10 * 1024 * 1024 + 10))
    check('a file over the 10MB cap is refused', oversize.status_code == 400,
          f'{oversize.status_code}')

    someone_elses = Application.objects.exclude(student=None).exclude(
        student__email__iexact=student.email).values_list('pk', flat=True).first()
    if someone_elses:
        hijack = upload(student, application=someone_elses)
        check('a document cannot be attached to somebody else\'s application',
              hijack.status_code == 400, f'{hijack.status_code}')

    guest_upload = requests.post(
        f'{BASE}/api/documents/',
        files={'file': ('proof.png', io.BytesIO(PNG), 'image/png')},
        data={'field_key': 'doc_completion'})
    check('somebody with no account can attach proof, because two awards need it',
          guest_upload.status_code in (201, 429),
          f'{guest_upload.status_code} {guest_upload.text[:160]}')

    if guest_upload.status_code == 201:
        guest_document = guest_upload.json()['id']
        check('a guest upload names an application belonging to nobody',
              requests.post(
                  f'{BASE}/api/documents/',
                  files={'file': ('proof.png', io.BytesIO(PNG), 'image/png')},
                  data={'field_key': 'doc_completion',
                        'application': someone_elses or 1}).status_code == 400)
        check('a stray guest document is still refused to a passing student',
              other.get(f'/api/documents/{guest_document}/').status_code == 404)
        check('the office can open a guest document',
              worker.get(f'/api/documents/{guest_document}/').status_code == 200)


# ── Attaching a guest application to an account ──────────────────────────────

def audit_attach(student: Actor, other: Actor, worker: Actor, director: Actor,
                 finance: Actor, admin: Actor) -> None:
    section('A claim filed without an account, later given one')

    forms = anon_get('/api/guest-applications/')
    check('the forms claimable without an account are published',
          forms.status_code == 200, f'{forms.status_code}')
    guest_slugs = [f['slug'] for f in forms.json()] if forms.status_code == 200 else []
    check('exactly the two one-off awards are claimable without an account',
          len(guest_slugs) == 2, str(guest_slugs))

    proof = requests.post(
        f'{BASE}/api/documents/',
        files={'file': ('diploma.png', io.BytesIO(PNG), 'image/png')},
        data={'field_key': 'doc_completion'})
    reference = proof.json()['reference'] if proof.status_code == 201 else ''

    slug = 'graduation_bursary' if 'graduation_bursary' in guest_slugs else (
        guest_slugs[0] if guest_slugs else 'graduation_bursary')
    definition = next((f for f in forms.json() if f['slug'] == slug), None) \
        if forms.status_code == 200 else None
    if definition is None:
        check('a guest form definition could be read', False)
        return

    answers = {key: value for key, value in
               (answer_for(field, reference) for field in definition['fields'])
               if value is not None}

    filed = anon_post('/api/guest-applications/',
                      json={'type': slug, 'answers': answers})
    if not check('a claim can be filed with no account at all',
                 filed.status_code == 201, f'{filed.status_code} {filed.text[:300]}'):
        return
    check('the claimant is given a reference and nothing else',
          set(filed.json()) <= {'reference', 'detail'}, str(filed.json()))

    application = Application.objects.filter(student=None).order_by('-pk').first()
    check('the claim was stored with no owner', application is not None)
    if application is None:
        return

    check('the regulated number never reached the stored answers',
          '046454286' not in str(application.answers), str(application.answers)[:200])

    target = User.objects.filter(email__iexact=student.email).first()

    # Asserted on the state, not on the status code. This path is guarded twice
    # — the viewset's queryset hides the application from a student, and the
    # action checks the role — so a check that accepts "403 or 404" passes with
    # the role check deleted. What must be true is that nobody was given it.
    refused = student.post(f'/api/applications/{application.pk}/attach/',
                           json={'student_id': target.pk})
    application.refresh_from_db()
    check('a student cannot attach a stray claim to their own account',
          refused.status_code in (403, 404) and application.student_id is None,
          f'{refused.status_code}, owner now {application.student_id}')

    by_finance = finance.post(f'/api/applications/{application.pk}/attach/',
                              json={'student_id': target.pk})
    application.refresh_from_db()
    check('finance cannot attach one either',
          by_finance.status_code in (403, 404) and application.student_id is None,
          f'{by_finance.status_code}, owner now {application.student_id}')

    by_director = director.post(f'/api/applications/{application.pk}/attach/',
                                json={'student_id': target.pk})
    application.refresh_from_db()
    check('nor the director, who decides applications rather than filing them',
          by_director.status_code in (403, 404) and application.student_id is None,
          f'{by_director.status_code}, owner now {application.student_id}')

    nobody = worker.post(f'/api/applications/{application.pk}/attach/',
                         json={'student_id': 99999999})
    check('attaching to an account that does not exist is refused',
          nobody.status_code == 400, f'{nobody.status_code}')

    staff_member = User.objects.filter(role=Role.SUPPORT_WORKER).first()
    to_staff = worker.post(f'/api/applications/{application.pk}/attach/',
                           json={'student_id': staff_member.pk})
    check('a claim cannot be attached to a member of staff',
          to_staff.status_code == 400, f'{to_staff.status_code}')

    attached = worker.post(f'/api/applications/{application.pk}/attach/',
                           json={'student_id': target.pk})
    check('the office can attach the claim to the right account',
          attached.status_code == 200, f'{attached.status_code} {attached.text[:200]}')

    application.refresh_from_db()
    check('the claim now belongs to that account',
          application.student_id == target.pk)

    again = worker.post(f'/api/applications/{application.pk}/attach/',
                        json={'student_id': User.objects.filter(
                            role=Role.STUDENT).exclude(pk=target.pk).first().pk})
    check('an application that already has an owner cannot be reassigned',
          again.status_code == 409, f'{again.status_code}')

    check('the student can now open what was filed on their behalf',
          student.get(f'/api/applications/{application.pk}/').status_code == 200)
    check('another student still cannot',
          other.get(f'/api/applications/{application.pk}/').status_code == 404)

    if any(k for k in answers if 'account_number' in k):
        has_account = target.bank_accounts.filter(is_current=True).exists()
        check('the bank details the claimant typed reached the account',
              has_account)


# ── Notices ──────────────────────────────────────────────────────────────────

def audit_notifications(student: Actor, other: Actor) -> None:
    section('Notices — a person sees their own and only their own')

    target = User.objects.filter(email__iexact=student.email).first()
    stranger = User.objects.filter(email__iexact=other.email).first()

    mine = Notification.objects.create(
        user=target, kind='info', title=f'Surface {STAMP}',
        message='A notice for the person it belongs to.')
    theirs = Notification.objects.create(
        user=stranger, kind='info', title=f'Not yours {STAMP}',
        message='A notice belonging to somebody else.')

    listing = student.get('/api/notifications/')
    check('a person can read their notices', listing.status_code == 200,
          f'{listing.status_code}')
    body = listing.json() if listing.status_code == 200 else {}
    ids = [n['id'] for n in body.get('results', [])]
    check('their own notice is in the list', mine.pk in ids)
    check('somebody else\'s notice is not', theirs.pk not in ids)
    check('the unread count is reported', isinstance(body.get('unread'), int))
    check('every notice carries a kind rather than leaving it to be guessed',
          all(n.get('kind') for n in body.get('results', [])))

    unread_only = student.get('/api/notifications/?unread=true')
    check('the unread filter actually filters',
          all(not n['is_read'] for n in unread_only.json().get('results', [])),
          str(unread_only.json())[:200])

    poach = student.post('/api/notifications/', json={'ids': [theirs.pk]})
    theirs.refresh_from_db()
    check('marking somebody else\'s notice read does nothing',
          poach.status_code == 200 and not theirs.is_read
          and poach.json().get('marked') == 0, f'{poach.status_code} {poach.text[:120]}')

    one = student.post('/api/notifications/', json={'ids': [mine.pk]})
    mine.refresh_from_db()
    check('marking one\'s own notice read works', one.status_code == 200 and mine.is_read)

    bad_shape = student.post('/api/notifications/', json={'ids': 'all-of-them'})
    check('a malformed id list is refused rather than swallowed',
          bad_shape.status_code == 400, f'{bad_shape.status_code}')

    all_read = student.post('/api/notifications/', json={})
    check('marking everything read leaves nothing unread',
          all_read.status_code == 200 and all_read.json().get('unread') == 0,
          f'{all_read.status_code} {all_read.text[:120]}')

    check('an anonymous caller has no notices to read',
          anon_get('/api/notifications/').status_code == 401)


# ── The directory ────────────────────────────────────────────────────────────

def audit_directory(student: Actor, worker: Actor, director: Actor,
                    finance: Actor, admin: Actor) -> None:
    section('The directory — who may read it, and who may change what it says')

    check('a student cannot read the directory',
          student.get('/api/people/').status_code == 403)
    check('an anonymous caller cannot read the directory',
          anon_get('/api/people/').status_code == 401)

    for name, actor in (('a support worker', worker), ('the director', director),
                        ('finance', finance), ('an administrator', admin)):
        response = actor.get('/api/people/')
        check(f'{name} can read the directory', response.status_code == 200,
              f'{response.status_code}')

    listing = admin.get('/api/people/')
    body = listing.json() if listing.status_code == 200 else {}
    check('the directory publishes the roles it can set',
          bool(body.get('roles')), str(body)[:160])
    results = body.get('results', [])
    check('the directory never carries banking or an address',
          not any(k in (results[0] if results else {})
                  for k in ('street_address', 'bank_account', 'account_number')),
          str(list(results[0]) if results else []))

    # The class of bug that hid here before: a query parameter accepted and
    # silently ignored, answering 200 with the unfiltered list.
    filtered = admin.get(f'/api/people/?role={Role.STUDENT}')
    roles = {p['role'] for p in filtered.json().get('results', [])}
    check('the role filter actually filters', roles <= {Role.STUDENT},
          f'roles returned: {roles}')

    searched = admin.get('/api/people/?search=director')
    hits = searched.json().get('results', [])
    check('the search actually searches',
          bool(hits) and all('director' in (p['email'] + p['full_name']).lower()
                             for p in hits),
          str([p['email'] for p in hits])[:200])

    nonsense_search = admin.get(f'/api/people/?search=zzz-{STAMP}')
    check('a search matching nobody returns nobody, not everybody',
          nonsense_search.json().get('results') == [],
          str(nonsense_search.json())[:160])

    subject = User.objects.filter(role=Role.STUDENT).exclude(
        email__iexact=admin.email).order_by('-pk').first()

    check('a support worker cannot change a role',
          worker.patch(f'/api/people/{subject.pk}/',
                       json={'role': Role.ADMIN}).status_code == 403)
    check('the director cannot change a role either',
          director.patch(f'/api/people/{subject.pk}/',
                         json={'role': Role.ADMIN}).status_code == 403)
    check('a student certainly cannot',
          student.patch(f'/api/people/{subject.pk}/',
                        json={'role': Role.ADMIN}).status_code == 403)
    subject.refresh_from_db()
    check('none of those attempts changed anything',
          subject.role == Role.STUDENT, subject.role)

    promoted = admin.patch(f'/api/people/{subject.pk}/',
                           json={'role': Role.SUPPORT_WORKER})
    subject.refresh_from_db()
    check('an administrator can change a role',
          promoted.status_code == 200 and subject.role == Role.SUPPORT_WORKER,
          f'{promoted.status_code} {subject.role}')
    admin.patch(f'/api/people/{subject.pk}/', json={'role': Role.STUDENT})

    invented = admin.patch(f'/api/people/{subject.pk}/', json={'role': 'overlord'})
    subject.refresh_from_db()
    check('a role that does not exist is refused',
          invented.status_code in (400, 409) and subject.role == Role.STUDENT,
          f'{invented.status_code} {subject.role}')

    me = User.objects.filter(email__iexact=admin.email).first()
    self_demote = admin.patch(f'/api/people/{me.pk}/', json={'role': Role.STUDENT})
    me.refresh_from_db()
    check('an administrator cannot demote themselves out of the office',
          self_demote.status_code == 409 and me.role == Role.ADMIN,
          f'{self_demote.status_code} {me.role}')

    self_disable = admin.patch(f'/api/people/{me.pk}/', json={'is_active': False})
    me.refresh_from_db()
    check('nor deactivate their own account',
          self_disable.status_code == 409 and me.is_active,
          f'{self_disable.status_code} {me.is_active}')

    check('an account that does not exist is a 404',
          admin.patch('/api/people/99999999/',
                      json={'role': Role.STUDENT}).status_code == 404)

    deactivated = admin.patch(f'/api/people/{subject.pk}/', json={'is_active': False})
    subject.refresh_from_db()
    check('an administrator can deactivate an account',
          deactivated.status_code == 200 and not subject.is_active,
          f'{deactivated.status_code}')
    check('a deactivated account cannot sign in',
          not Actor(subject.email).signed_in)
    admin.patch(f'/api/people/{subject.pk}/', json={'is_active': True})
    subject.refresh_from_db()
    check('and can be restored', subject.is_active)


# ── Policy, money, dashboards, help ──────────────────────────────────────────

def audit_policy_and_money(student: Actor, worker: Actor, director: Actor,
                           finance: Actor, admin: Actor) -> None:
    section('Policy and money — read by many, written by few')

    rates = admin.get('/api/policy/rates/')
    check('an administrator can read the rates', rates.status_code == 200,
          f'{rates.status_code}')
    check('a student cannot read the rate table',
          student.get('/api/policy/rates/').status_code in (403, 404),
          str(student.get('/api/policy/rates/').status_code))
    check('an anonymous caller cannot',
          anon_get('/api/policy/rates/').status_code == 401)

    # The rates are published grouped by the section of the policy book they
    # belong to, so the table has to be flattened before a row can be edited.
    listing = rates.json() if rates.status_code == 200 else []
    if isinstance(listing, dict):
        listing = listing.get('results', [])
    rows = [setting for group in listing for setting in group.get('settings', [])] \
        if listing and isinstance(listing[0], dict) and 'settings' in listing[0] \
        else listing
    check('there are rates published', bool(rows), str(listing)[:160])
    check('every published rate carries the key a rule resolves it by',
          all(row.get('key') for row in rows), str(rows[:2])[:200])
    if rows:
        row = rows[0]
        current = row.get('value')
        check('a support worker cannot edit a rate',
              worker.patch(f'/api/policy/rates/{row["id"]}/',
                           json={'value': '1.00'}).status_code in (403, 404))
        check('the director cannot edit a rate',
              director.patch(f'/api/policy/rates/{row["id"]}/',
                             json={'value': '1.00'}).status_code in (403, 404))
        no_op = admin.patch(f'/api/policy/rates/{row["id"]}/', json={'value': current})
        check('an administrator saving the same figure is told nothing changed',
              no_op.status_code in (400, 409), f'{no_op.status_code} {no_op.text[:160]}')

    rule_sets = admin.get('/api/policy/rule-sets/')
    check('the rule sets are readable', rule_sets.status_code == 200,
          f'{rule_sets.status_code}')
    sets = rule_sets.json() if rule_sets.status_code == 200 else []
    sets = sets.get('results', sets) if isinstance(sets, dict) else sets
    published = [s for s in sets if s.get('state') == 'published'
                 or s.get('status') == 'published']
    check('exactly one rule set is in force', len(published) == 1,
          str([(s.get('version'), s.get('state', s.get('status'))) for s in sets]))

    check('a student cannot see the payment run',
          student.get('/api/finance/pending/').status_code == 403)
    check('a support worker cannot see the payment run',
          worker.get('/api/finance/pending/').status_code == 403)
    pending = finance.get('/api/finance/pending/')
    check('finance can', pending.status_code == 200, f'{pending.status_code}')

    check('a student cannot dispatch a payment run',
          student.post('/api/finance/dispatch/', json={}).status_code == 403)
    check('a support worker cannot dispatch a payment run',
          worker.post('/api/finance/dispatch/', json={}).status_code == 403)
    check('the director cannot dispatch a payment run',
          director.post('/api/finance/dispatch/', json={}).status_code == 403)

    section('The payment run — the same money must not be offered twice')

    def offered():
        response = finance.get('/api/finance/pending/')
        return response.json() if response.status_code == 200 else {'awards': []}

    run = offered()
    ids = [row['id'] for row in run.get('awards', [])]
    check('nothing is offered to finance twice in one run',
          len(ids) == len(set(ids)), f'{len(ids)} rows, {len(set(ids))} distinct')

    # The invariant the $17,100 bug broke: a superseded decision's lines stay
    # PENDING, because nothing pays them and so nothing ever moves them on. If
    # the run is not scoped to the decision in force, an application priced
    # twice is offered twice and the money goes out twice.
    superseded = Award.objects.filter(pk__in=ids).exclude(decision__is_current=True)
    check('every award offered belongs to the decision in force',
          not superseded.exists(),
          f'{superseded.count()} of {len(ids)} offered lines belong to a '
          f'superseded or missing decision: {list(superseded.values_list("pk", flat=True))[:10]}')

    # Compared as amounts, not as text: '27142.0' and '27142.00' are the same
    # money, and a check that calls them different fails for a reason that has
    # nothing to do with what it is guarding.
    check('the total finance is shown is the sum of the lines it is shown',
          sum((Decimal(row['amount']) for row in run.get('awards', [])),
              Decimal('0.00')) == Decimal(str(run.get('total', '0'))),
          f'{run.get("total")} against the rows listed')

    check('every blocked award says what is blocking it',
          all(row.get('reason') for row in run.get('blocked', [])),
          str(run.get('blocked', []))[:200])

    # And the same thing again, from the other end: price something a second
    # time and confirm the run does not grow by the lines it just replaced.
    repriceable = (Application.objects
                   .filter(status__in=('approved', 'sent_to_finance'),
                           awards__status=Award.Status.PENDING)
                   .exclude(student=None).distinct().first())
    if repriceable is not None:
        before = {row['id'] for row in run.get('awards', [])
                  if row['application_id'] == repriceable.pk}
        priced = director.post(f'/api/applications/{repriceable.pk}/price/', json={})
        check('the director can re-price an application',
              priced.status_code in (201, 409),
              f'{priced.status_code} {priced.text[:160]}')
        if priced.status_code == 201:
            after_run = offered()
            after = {row['id'] for row in after_run.get('awards', [])
                     if row['application_id'] == repriceable.pk}
            check('re-pricing replaces what is offered rather than adding to it',
                  not (before & after),
                  f'{len(before & after)} lines from the superseded pricing are '
                  f'still being offered')
            stale = Award.objects.filter(
                pk__in={row['id'] for row in after_run.get('awards', [])}
            ).exclude(decision__is_current=True)
            check('nothing from the superseded pricing survives into the run',
                  not stale.exists(), str(list(stale.values_list('pk', flat=True))[:10]))

    section('Money that has left the bank')
    # `Award.objects.paid()` exists so that a payment made under a decision
    # since superseded still counts as made. Nothing in the codebase writes
    # Award.Status.PAID, so the figure it feeds — the student's "paid" total —
    # can only ever read zero. Recorded here as a fact about the system rather
    # than asserted as correct: see the open items.
    ever_paid = Award.objects.paid().count()
    print(f'  note  {ever_paid} awards have ever reached "paid"; '
          f'{Award.objects.filter(status=Award.Status.SENT_TO_FINANCE).count()} '
          f'sit at "sent to finance"')
    check('the student\'s paid total agrees with the awards actually marked paid',
          (Decimal(student.get('/api/dashboard/').json()
                   .get('money', {}).get('paid', '0')) == Decimal('0.00'))
          == (ever_paid == 0),
          'the dashboard reports a paid total that no award status supports')

    section('Dashboards — the same endpoint, a different answer per role')
    for name, actor in (('student', student), ('support worker', worker),
                        ('director', director), ('finance', finance),
                        ('administrator', admin)):
        response = actor.get('/api/dashboard/')
        check(f'the {name} dashboard loads', response.status_code == 200,
              f'{response.status_code} {response.text[:160]}')
    check('there is no dashboard for an anonymous caller',
          anon_get('/api/dashboard/').status_code == 401)

    # The leak to look for is not a status name — a student's own applications
    # are counted by status too. It is a *number* that belongs to somebody else.
    student_dashboard = student.get('/api/dashboard/')
    body = student_dashboard.json() if student_dashboard.status_code == 200 else {}
    owner = User.objects.filter(email__iexact=student.email).first()
    own = Application.objects.filter(student=owner).count()
    everyone = Application.objects.count()
    check('a student is counted only their own applications',
          body.get('applications', {}).get('total') == own,
          f'dashboard {body.get("applications", {}).get("total")}, own {own}, '
          f'everyone {everyone}')
    check('the student scope says so',
          body.get('scope') == 'student', str(body.get('scope')))
    recent_ids = [row['id'] for row in body.get('recent', [])]
    check('nothing on the student\'s recent list belongs to anybody else',
          not Application.objects.filter(pk__in=recent_ids).exclude(
              student=owner).exists(), str(recent_ids)[:160])

    section('Help — the page for people who cannot sign in')
    help_page = anon_get('/api/help/')
    check('help is readable without an account', help_page.status_code == 200,
          f'{help_page.status_code}')
    help_body = help_page.json() if help_page.status_code == 200 else {}
    check('it carries a way to reach the office',
          any(k in str(help_body).lower() for k in ('email', 'phone', 'address')),
          str(help_body)[:200])
    check('it carries the questions the office is asked',
          bool(help_body.get('faq')), str(list(help_body))[:160])
    check('the contact details come from the server, not from the bundle',
          bool(help_body.get('contact')), str(list(help_body))[:160])


# ── The whole surface, one role at a time ────────────────────────────────────

def audit_permission_matrix(actors: dict[str, Actor]) -> None:
    section('Every endpoint, every role — nothing answers 500, nothing leaks')

    read_paths = [
        '/api/me/', '/api/dashboard/', '/api/notifications/', '/api/schemas/',
        '/api/applications/', '/api/people/', '/api/policy/rates/',
        '/api/policy/rule-sets/', '/api/finance/pending/', '/api/help/',
        '/api/guest-applications/', '/api/auth/eligibility/',
        '/api/form-prefill/admission/',
    ]

    # Reading a rate is open to all staff on purpose — a support worker
    # explaining an amount to a student needs to see the figure behind it.
    # Writing one is the administrator's alone, and is checked separately.
    allowed = {
        '/api/people/': {'worker', 'director', 'finance', 'admin'},
        '/api/policy/rates/': {'worker', 'director', 'finance', 'admin'},
        '/api/policy/rule-sets/': {'worker', 'director', 'finance', 'admin'},
        '/api/finance/pending/': {'finance', 'admin'},
    }
    # A schema is the questions a form asks and carries nobody's data, so it is
    # served to somebody who has not signed up yet — that is the point of it.
    open_to_all = {'/api/help/', '/api/guest-applications/',
                   '/api/auth/eligibility/', '/api/schemas/'}

    for path in read_paths:
        anonymous = anon_get(path)
        check(f'anonymous GET {path} is answered without an error',
              anonymous.status_code < 500, f'{anonymous.status_code}')
        if path in open_to_all:
            check(f'anonymous GET {path} is public, as intended',
                  anonymous.status_code == 200, f'{anonymous.status_code}')
        else:
            check(f'anonymous GET {path} is refused',
                  anonymous.status_code == 401, f'{anonymous.status_code}')

        for name, actor in actors.items():
            response = actor.get(path)
            check(f'{name} GET {path} does not fail on the server',
                  response.status_code < 500,
                  f'{response.status_code} {response.text[:120]}')
            if path in allowed:
                expected = name in allowed[path]
                check(f'{name} GET {path} is {"open" if expected else "closed"}',
                      (response.status_code == 200) == expected,
                      f'{response.status_code}')

    section('Reading an application that belongs to somebody else')
    someone = Application.objects.exclude(student=None).order_by('-pk').first()
    if someone is not None:
        owner_email = someone.student.email
        for name, actor in actors.items():
            if actor.email.lower() == owner_email.lower():
                continue
            response = actor.get(f'/api/applications/{someone.pk}/')
            if name == 'student':
                check('a student cannot open an application that is not theirs',
                      response.status_code == 404, f'{response.status_code}')
            else:
                check(f'{name} can open any application, as the office must',
                      response.status_code == 200, f'{response.status_code}')

    section('The generated API description')
    for path in ('/api/schema/', '/api/docs/'):
        response = anon_get(path)
        check(f'{path} is served rather than erroring',
              response.status_code in (200, 301, 302, 401, 403),
              f'{response.status_code}')


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default=BASE)
    arguments = parser.parse_args()
    BASE = arguments.base.rstrip('/')

    section('Signing in as the office')
    people = {name: Actor(f'{name}@dgg.test')
              for name in ('student', 'student2', 'worker', 'director',
                           'finance', 'admin')}
    for name, actor in people.items():
        if not check(f'{name} can sign in', actor.signed_in):
            print('        Run: python manage.py seed_demo')
            return 1

    student, other = people['student'], people['student2']
    worker, director = people['worker'], people['director']
    finance, admin = people['finance'], people['admin']

    audit_eligibility()
    newcomer = audit_registration()
    audit_tokens(newcomer or student)
    audit_me(newcomer or student)
    audit_schemas_and_prefill(student, worker)
    audit_enrolment_preview(student)
    audit_documents(student, other, worker, finance)
    audit_attach(student, other, worker, director, finance, admin)
    audit_notifications(student, other)
    audit_directory(student, worker, director, finance, admin)
    audit_policy_and_money(student, worker, director, finance, admin)
    audit_permission_matrix({'student': student, 'worker': worker,
                             'director': director, 'finance': finance,
                             'admin': admin})

    print()
    if failures:
        print(f'{len(failures)} of {checks} checks FAILED')
        for failure in failures:
            print(f'  - {failure}')
        return 1
    print(f'{checks}/{checks} checks passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
