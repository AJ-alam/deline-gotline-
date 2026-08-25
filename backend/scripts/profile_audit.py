"""The student's profile, over real HTTP.

The unit tests assert each endpoint. This asserts the thing the profile was
built for, which no single endpoint can show: a student fills it in once, and
every form afterwards opens already holding those answers — including the one
answer whose absence used to make a renewal impossible to approve.

It walks one newly registered student:

    register -> empty profile -> fill it in -> a form opens pre-filled ->
    submit -> the enrolment request reaches the registrar's address from the
    profile -> re-answer the screening -> the funding stream follows ->
    banking -> what finance sees

and then checks that none of it is reachable by anyone else.

    python manage.py runserver 127.0.0.1:8000
    python scripts/profile_audit.py [--base http://127.0.0.1:8000]

Everything it creates is stamped with the run time, so a second run does not
collide with the first.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from accounts.models import BankAccount, EnrolmentProfile, User  # noqa: E402
from funding.models import (  # noqa: E402
    Application, AuditEntry, EnrollmentVerification,
)

PASSWORD = 'DemoPass123!'
STAMP = time.strftime('%m%d%H%M%S')

checks = 0
failures: list[str] = []
BASE = 'http://127.0.0.1:8000'

ELIGIBLE = {
    'indian_act_registered': 'yes',
    'deline_beneficiary': 'yes',
    'receives_sfa': 'no',
    'lives_in_nwt': 'yes',
    'accredited_institution': 'yes',
    'programme_twelve_weeks': 'yes',
}

PROFILE = {
    'institution_name': 'Aurora College',
    'institution_location': 'Yellowknife, NT',
    'program': 'Bachelor of Nursing',
    'credential_level': 'degree',
    'learning_style': 'in_person',
    'course_load': 'full_time',
    'student_number': f'A-{STAMP}',
    'program_start': '2026-09-01',
    'program_end': '2030-06-30',
    'program_year': 1,
    'program_length_years': 4,
    'registrar_email': f'registrar.{STAMP}@aurora.test',
    'institution_phone': '867-555-0177',
    'dependent_count': 0,
}

BANK = {
    'account_holder': 'Profile Audit',
    'transit_number': '12345',
    'institution_number': '001',
    'account_number': '9876543210',
}


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
    def __init__(self, email: str, password: str = PASSWORD):
        self.email = email
        self.http = requests.Session()
        response = self.http.post(f'{BASE}/api/auth/token/',
                                  json={'email': email, 'password': password})
        self.signed_in = response.status_code == 200 and 'access' in response.json()
        if self.signed_in:
            self.http.headers['Authorization'] = f'Bearer {response.json()["access"]}'

    def get(self, path, **kw):
        return self.http.get(f'{BASE}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{BASE}{path}', **kw)

    def put(self, path, **kw):
        return self.http.put(f'{BASE}{path}', **kw)

    def patch(self, path, **kw):
        return self.http.patch(f'{BASE}{path}', **kw)


def register(suffix: str) -> tuple[Actor | None, str]:
    email = f'profile.{suffix}.{STAMP}@example.com'
    created = requests.post(f'{BASE}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Profile', 'last_name': f'Audit{STAMP}',
        'phone': '867-555-0101', 'eligibility': dict(ELIGIBLE),
    })
    if created.status_code != 201:
        return None, email
    return Actor(email), email


def answers_for(slug: str, prefill: dict | None = None, **overrides) -> dict:
    """Answers for one form, starting from what the portal pre-fills.

    Built the way a browser fills the form in: the pre-filled answers first,
    then a plausible value for whatever is still required. An audit that
    fabricated every answer would submit values the student would never have
    typed — and would prove nothing about the pre-fill it is here to check.
    """
    schema = requests.get(f'{BASE}/api/schemas/{slug}/').json()
    answers = dict(prefill or {})

    for field in schema['fields']:
        if field.get('computed'):
            answers.pop(field['key'], None)
            continue
        key, kind = field['key'], (field.get('type') or '').lower()
        if not field.get('required') or answers.get(key) not in (None, '', []):
            continue

        if kind == 'choice':
            choices = field.get('choices') or []
            answers[key] = choices[0]['value'] if choices else ''
        elif kind == 'confirm':
            answers[key] = True
        elif kind == 'boolean':
            answers[key] = False
        elif kind == 'date':
            answers[key] = '2026-09-01'
        elif kind in ('money', 'number', 'integer', 'percent'):
            answers[key] = '1200'
        elif kind == 'email':
            answers[key] = f'student.{STAMP}@example.com'
        elif kind == 'phone':
            answers[key] = '867-555-0101'
        elif kind == 'signature':
            answers[key] = 'Profile Audit'
        elif kind == 'sin':
            answers[key] = TEST_SIN
        elif kind in ('file', 'files'):
            # Not uploaded: this audit is about the profile, and the document
            # endpoint has its own. A reference is what the answer holds.
            answers[key] = 'document:1' if kind == 'file' else ['document:1']
        elif kind == 'table':
            answers[key] = [{
                column['key']: _column_value(column)
                for column in field.get('columns', [])
            }]
        elif key == 'postal_code':
            answers[key] = 'X0E 0G0'
        elif key == 'province':
            answers[key] = 'NT'
        elif key == 'transit_number':
            answers[key] = '12345'
        elif key == 'institution_number':
            answers[key] = '001'
        elif key == 'account_number':
            answers[key] = '9876543210'
        else:
            answers[key] = 'Profile audit'

    answers.update(overrides)
    return answers


def _column_value(column: dict):
    kind = (column.get('type') or '').lower()
    if kind in ('money', 'number', 'integer'):
        return '800'
    if kind == 'boolean':
        return False
    if kind == 'date':
        return '2026-09-01'
    if kind == 'choice':
        choices = column.get('choices') or []
        return choices[0]['value'] if choices else ''
    return 'Bus fare'


TEST_SIN = '130692544'


def prefill_for(student: 'Actor', slug: str) -> dict:
    response = student.get(f'/api/form-prefill/{slug}/')
    return response.json().get('answers', {}) if response.status_code == 200 else {}



# ── The screen ───────────────────────────────────────────────────────────────


def audit_empty_profile(student: Actor) -> None:
    section('A profile nobody has filled in')

    enrolment = student.get('/api/me/enrolment/')
    check('the enrolment profile opens rather than 404ing',
          enrolment.status_code == 200, f'{enrolment.status_code} {enrolment.text[:120]}')
    check('it opens empty', enrolment.json().get('institution_name') == '',
          enrolment.text[:160])

    banking = student.get('/api/me/banking/')
    check('banking answers with a body a client can parse',
          banking.status_code == 200 and banking.headers.get('Content-Type', '')
          .startswith('application/json'),
          f'{banking.status_code} {banking.headers.get("Content-Type")}')
    check('nothing on file reads as nothing', banking.json().get('account') is None,
          banking.text[:120])

    screening = student.get('/api/me/eligibility/')
    body = screening.json() if screening.status_code == 200 else {}
    check('the screening comes back with all six questions',
          len(body.get('questions') or []) == 6, str(body)[:160])
    check('and with the answers the student gave at sign-up',
          body.get('answers', {}).get('deline_beneficiary') == 'yes', str(body)[:200])
    check('and with what those answers decided',
          body.get('streams') == ['psssp', 'dggr'], str(body.get('streams')))


def audit_saving(student: Actor, email: str) -> None:
    section('Filling it in')

    # What the screen actually posts on a first visit: every box in the
    # section, and most of them empty. Registration collects no date of birth,
    # so `date_of_birth: ''` is the common case rather than an edge one — and a
    # DateField reads an empty string as a malformed date.
    untouched = student.patch('/api/me/', json={
        'preferred_name': '', 'date_of_birth': '', 'pronouns': '', 'phone': '',
        'alternate_phone': '', 'street_address': '', 'city': '', 'province': '',
        'postal_code': '', 'beneficiary_number': '', 'treaty_number': '',
        'first_name': 'Profile', 'last_name': f'Audit{STAMP}',
    })
    check('a student with nothing on file can still save their details',
          untouched.status_code == 200,
          f'{untouched.status_code} {untouched.text[:200]}')

    nameless = student.patch('/api/me/', json={'first_name': '', 'last_name': ''})
    check('but a person must still have a name', nameless.status_code == 400,
          f'{nameless.status_code} {nameless.text[:160]}')

    details = student.patch('/api/me/', json={
        'first_name': 'Sara', 'city': 'Délı̨nę', 'province': 'NT',
        'postal_code': 'X0E 0G0', 'date_of_birth': '2001-04-12',
        'street_address': '12 Lakeview',
    })
    check('a student can correct their own details', details.status_code == 200,
          f'{details.status_code} {details.text[:160]}')
    check('the correction is stored',
          User.objects.get(email__iexact=email).city == 'Délı̨nę')

    stolen = student.patch('/api/me/', json={
        'role': 'admin', 'email': 'someone@else.test',
        'eligible_streams': ['psssp', 'ucepp', 'dggr'],
        'is_indian_act_registered': True,
    })
    person = User.objects.get(email__iexact=email)
    check('patching /me/ cannot promote the person doing it',
          stolen.status_code == 200 and person.role == 'student', person.role)
    check('nor change the address they sign in with',
          person.email.lower() == email.lower(), person.email)
    check('nor write their own funding streams',
          person.eligible_streams == ['psssp', 'dggr'], str(person.eligible_streams))

    # The same first visit, on the section with the dates and the counts in it.
    blank_section = student.put('/api/me/enrolment/',
                                json={key: '' for key in PROFILE})
    check('an enrolment section nobody has filled in can be saved',
          blank_section.status_code == 200,
          f'{blank_section.status_code} {blank_section.text[:200]}')

    saved = student.put('/api/me/enrolment/', json=dict(PROFILE))
    check('the enrolment profile saves', saved.status_code == 200,
          f'{saved.status_code} {saved.text[:200]}')

    # A second Save posts back exactly what the screen was given.
    stored = student.get('/api/me/enrolment/').json()
    stored.pop('updated_at', None)
    again = student.put('/api/me/enrolment/', json=stored)
    check('and saving it again unchanged is accepted', again.status_code == 200,
          f'{again.status_code} {again.text[:200]}')

    profile = EnrolmentProfile.objects.filter(user__email__iexact=email).first()
    check('exactly one profile row exists for this student',
          EnrolmentProfile.objects.filter(user__email__iexact=email).count() == 1)
    check('it holds what was typed',
          profile is not None and profile.institution_name == 'Aurora College',
          getattr(profile, 'institution_name', None))
    check('including a zero, which is an answer rather than a blank',
          profile is not None and profile.dependent_count == 0,
          str(getattr(profile, 'dependent_count', 'missing')))

    partial = student.put('/api/me/enrolment/', json={'program': 'Practical Nursing'})
    profile.refresh_from_db()
    check('a section saved on its own leaves the rest alone',
          partial.status_code == 200 and profile.institution_name == 'Aurora College',
          profile.institution_name)
    check('and saves what it was given', profile.program == 'Practical Nursing',
          profile.program)

    bad_choice = student.put('/api/me/enrolment/', json={'course_load': 'fulltime'})
    check('a value no form recognises is refused rather than stored',
          bad_choice.status_code == 400, f'{bad_choice.status_code} {bad_choice.text[:160]}')
    check('and the refusal names what the forms do accept',
          'full_time' in bad_choice.text, bad_choice.text[:200])

    backwards = student.put('/api/me/enrolment/',
                            json={'program_start': '2031-01-01'})
    check('a programme cannot be made to end before it starts, even in two writes',
          backwards.status_code == 400, f'{backwards.status_code} {backwards.text[:160]}')

    student.put('/api/me/enrolment/', json={'program': 'Bachelor of Nursing'})


def audit_prefill(student: Actor) -> None:
    section('What the next form opens with')

    prefill = student.get('/api/form-prefill/admission/')
    answers = prefill.json().get('answers', {}) if prefill.status_code == 200 else {}

    check('the form opens holding the institution', answers.get('institution_name')
          == 'Aurora College', str(answers)[:200])
    check('and the programme', answers.get('program') == 'Bachelor of Nursing',
          answers.get('program'))
    check('and the registrar address', answers.get('registrar_email')
          == PROFILE['registrar_email'], answers.get('registrar_email'))
    check('and the course load, as a value the schema accepts',
          answers.get('course_load') == 'full_time', answers.get('course_load'))
    check('and the identity from the account',
          answers.get('city') == 'Délı̨nę', answers.get('city'))
    check('no dependants is carried as 0 rather than dropped',
          answers.get('dependent_count') == 0, repr(answers.get('dependent_count')))

    # The per-term facts. Filling these in would be answering on the student's
    # behalf about a term they have not started.
    for key in ('semester', 'semester_start', 'semester_end', 'tuition_requested',
                'receives_sfa', 'signature'):
        check(f'{key} is left for the student to state', key not in answers,
              repr(answers.get(key)))

    schema = requests.get(f'{BASE}/api/schemas/admission/').json()
    declared = {field['key'] for field in schema['fields']}
    unknown = set(answers) - declared
    check('nothing is pre-filled that the form does not ask',
          not unknown, str(unknown))


def audit_renewal_reaches_the_registrar(student: Actor, email: str) -> None:
    """The bug the profile closes.

    A renewal does not ask for a registrar's address; it is carried from the
    student's last application. Somebody whose admission was on paper has
    nothing to carry, so the request was skipped in silence — tuition could
    never be confirmed and the application could never be approved, by anybody,
    with nothing anywhere saying why.
    """
    section('A renewal from somebody with no earlier application')

    person = User.objects.get(email__iexact=email)
    check('this student really has filed nothing yet',
          not Application.objects.filter(student=person).exists())

    answers = answers_for('continuing_funding', prefill_for(student, 'continuing_funding'),
                          semester='fall', course_load='full_time')

    filed = student.post('/api/applications/', json={
        'type': 'continuing_funding', 'answers': answers,
    })
    if not check('the renewal is accepted', filed.status_code == 201,
                 f'{filed.status_code} {filed.text[:300]}'):
        return

    application = Application.objects.get(pk=filed.json()['id'])
    verification = EnrollmentVerification.objects.filter(application=application).first()

    check('the institution was asked to confirm the enrolment',
          verification is not None,
          'no EnrollmentVerification was created — the request was skipped in silence')
    check('and asked at the address on the profile',
          verification is not None
          and verification.registrar_email == PROFILE['registrar_email'],
          getattr(verification, 'registrar_email', None))

    body = student.get(f'/api/applications/{application.pk}/').json()
    check('the screen says a confirmation is required',
          body.get('enrolment', {}).get('required') is True, str(body.get('enrolment')))
    check('and that it has been requested rather than "not required"',
          body.get('enrolment', {}).get('status') == 'requested',
          str(body.get('enrolment')))

    check('the answers the profile filled in are on the filed application',
          application.answers.get('institution_name') == 'Aurora College',
          application.answers.get('institution_name'))
    check('and this one was funded from a C-DFN stream',
          application.stream == 'psssp', application.stream)


def audit_screening_change(student: Actor, email: str) -> None:
    section('Re-answering the six questions')

    before = AuditEntry.objects.filter(action='account.screening_updated').count()

    partial = student.put('/api/me/eligibility/',
                          json={'answers': {'receives_sfa': 'yes'}})
    check('a partial answer set is refused', partial.status_code == 400,
          f'{partial.status_code} {partial.text[:160]}')
    check('and changes nothing',
          User.objects.get(email__iexact=email).eligible_streams == ['psssp', 'dggr'])

    sfa = student.put('/api/me/eligibility/', json={
        'answers': {**ELIGIBLE, 'receives_sfa': 'yes'},
        # Sent deliberately: a client must never be able to name its own streams.
        'streams': ['psssp', 'ucepp', 'dggr'],
    })
    check('re-answering is accepted', sfa.status_code == 200,
          f'{sfa.status_code} {sfa.text[:200]}')
    person = User.objects.get(email__iexact=email)
    check('SFA withdraws the C-DFN streams and leaves the bursary',
          person.eligible_streams == ['dggr'], str(person.eligible_streams))
    check('the streams the client asked for were ignored',
          'ucepp' not in person.eligible_streams, str(person.eligible_streams))
    check('the answers are stored as given',
          person.eligibility_answers.get('receives_sfa') == 'yes',
          str(person.eligibility_answers))
    check('the change is audited',
          AuditEntry.objects.filter(action='account.screening_updated').count() > before)

    # What it is for: the next application is funded from a different pot.
    # Same form as before the change, so the only thing that differs is the
    # screening — a comparison the first renewal above set up.
    prefill = prefill_for(student, 'continuing_funding')
    check('the profile still fills the next form',
          prefill.get('institution_name') == 'Aurora College',
          str(prefill)[:160])

    filed = student.post('/api/applications/', json={
        'type': 'continuing_funding',
        'answers': answers_for('continuing_funding', prefill,
                               semester='winter', course_load='full_time'),
    })
    if check('a second renewal can be filed', filed.status_code == 201,
             f'{filed.status_code} {filed.text[:300]}'):
        check('and it is funded from the bursary now, not from PSSSP',
              filed.json().get('stream') == 'dggr', filed.json().get('stream'))


def audit_ineligible(email_suffix: str) -> None:
    """Somebody who answers themselves out of every stream.

    An account with no streams cannot file anything — which is the point, and is
    also why the empty list must not be mistaken for "never screened". It was:
    `saved_streams` fell back to the two booleans whenever the tags were empty,
    which handed PSSSP back to the person who had just told us they no longer
    qualify for it.
    """
    section('Answering yourself out of every stream')

    student, email = register(email_suffix)
    if not check('a second student registered', student is not None and student.signed_in):
        return

    response = student.put('/api/me/eligibility/', json={'answers': {
        **ELIGIBLE, 'deline_beneficiary': 'no', 'receives_sfa': 'yes',
    }})
    check('the answers are recorded rather than refused', response.status_code == 200,
          f'{response.status_code} {response.text[:200]}')
    body = response.json()
    check('and the screening says plainly that nothing applies',
          body.get('outcome', {}).get('eligible') is False, str(body.get('outcome'))[:200])
    check('in the office\'s own words',
          'Student Financial Assistance' in str(body.get('outcome', {}).get('message')),
          str(body.get('outcome', {}).get('message'))[:200])

    person = User.objects.get(email__iexact=email)
    check('no stream is left on the account', person.eligible_streams == [],
          str(person.eligible_streams))
    check('the screening booleans follow the answers rather than staying at sign-up',
          person.is_deline_beneficiary is False, str(person.is_deline_beneficiary))

    blocked = student.post('/api/applications/', json={
        'type': 'continuing_funding',
        # Valid answers, deliberately: posting rubbish would be refused by
        # validation first and would prove nothing about the stream.
        'answers': answers_for('continuing_funding', prefill_for(student, 'continuing_funding'),
                               semester='fall', course_load='full_time'),
    })
    check('and an application cannot be filed under a stream nobody holds',
          blocked.status_code == 409,
          f'{blocked.status_code} {blocked.text[:300]}')
    check('with the office named as the way forward',
          'Education Department' in blocked.text, blocked.text[:200])


def audit_banking(student: Actor, email: str) -> None:
    section('Where the money goes')

    short = student.put('/api/me/banking/', json={**BANK, 'transit_number': '123'})
    check('a transit number of the wrong shape is refused',
          short.status_code == 400, f'{short.status_code} {short.text[:160]}')
    check('and the refusal lands on the box it is about',
          'transit_number' in short.text, short.text[:200])

    partial = student.put('/api/me/banking/',
                          json={k: v for k, v in BANK.items() if k != 'account_number'})
    check('half an account is refused', partial.status_code == 400,
          f'{partial.status_code} {partial.text[:160]}')

    saved = student.put('/api/me/banking/', json=dict(BANK))
    check('a complete account is accepted', saved.status_code == 200,
          f'{saved.status_code} {saved.text[:200]}')
    check('what comes back is masked', saved.json().get('account', {})
          .get('account_number') == '****3210', saved.text[:200])
    check('the digits are never returned', '9876543210' not in saved.text,
          saved.text[:200])
    check('nor by /me/', '9876543210' not in student.get('/api/me/').text)

    person = User.objects.get(email__iexact=email)
    check('finance has an account to pay',
          BankAccount.objects.filter(user=person, is_current=True).count() == 1)

    replaced = student.put('/api/me/banking/',
                           json={**BANK, 'account_number': '1111222233'})
    check('replacing it is accepted', replaced.status_code == 200,
          f'{replaced.status_code} {replaced.text[:160]}')
    accounts = BankAccount.objects.filter(user=person).order_by('id')
    check('the previous account is retired rather than edited',
          accounts.count() == 2 and not accounts[0].is_current
          and accounts[0].retired_at is not None,
          f'{accounts.count()} account(s)')
    check('exactly one is current',
          BankAccount.objects.filter(user=person, is_current=True).count() == 1)
    check('saving the same details twice does not churn the record',
          student.put('/api/me/banking/',
                      json={**BANK, 'account_number': '1111222233'}).status_code == 200
          and BankAccount.objects.filter(user=person).count() == 2,
          str(BankAccount.objects.filter(user=person).count()))
    check('the change is audited without the digits',
          AuditEntry.objects.filter(action='account.banking_updated',
                                    actor=person).exists()
          and not AuditEntry.objects.filter(
              action='account.banking_updated', actor=person,
              detail__contains='1111222233').exists())


def audit_permissions(student: Actor) -> None:
    section('Whose profile it is')

    other, _ = register('other')
    if not check('a second student registered', other is not None and other.signed_in):
        return

    other.put('/api/me/enrolment/', json={'institution_name': 'Somewhere Else'})
    mine = student.get('/api/me/enrolment/').json()
    check('one student\'s profile is not another\'s',
          mine.get('institution_name') == 'Aurora College',
          mine.get('institution_name'))

    for path in ('/api/me/', '/api/me/eligibility/', '/api/me/enrolment/',
                 '/api/me/banking/'):
        response = requests.get(f'{BASE}{path}')
        check(f'{path} is closed to anonymous callers', response.status_code == 401,
              f'{response.status_code}')

    for name in ('worker', 'director', 'finance', 'admin'):
        staff = Actor(f'{name}@dgg.test')
        if not staff.signed_in:
            check(f'{name} can sign in', False, 'run: python manage.py seed_demo')
            continue
        for path in ('/api/me/eligibility/', '/api/me/enrolment/', '/api/me/banking/'):
            response = staff.get(f'{path}')
            check(f'{name} has no {path}', response.status_code == 403,
                  f'{response.status_code} {response.text[:120]}')


def main() -> int:
    global BASE

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=BASE)
    BASE = parser.parse_args().base.rstrip('/')

    try:
        requests.get(f'{BASE}/api/schemas/', timeout=5)
    except requests.RequestException as exc:
        print(f'No server at {BASE}: {exc}')
        print('Run: python manage.py runserver 127.0.0.1:8000')
        return 1

    section('Registering somebody with nothing on file')
    student, email = register('main')
    if not check('the student registered and signed in',
                 student is not None and student.signed_in, email):
        return 1

    audit_empty_profile(student)
    audit_saving(student, email)
    audit_prefill(student)
    audit_renewal_reaches_the_registrar(student, email)
    audit_screening_change(student, email)
    audit_ineligible('nostream')
    audit_banking(student, email)
    audit_permissions(student)

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
