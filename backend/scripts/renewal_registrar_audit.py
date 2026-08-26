"""A renewal from somebody the portal has never seen, all the way to the money.

Every other audit that files a renewal does it as a student with history — an
admission on file, or a profile with a registrar on it. That is the easy half.
The half that was broken is the other one: no admission, no profile, nothing to
carry. Such a renewal used to submit, tell the student "we ask your registrar to
confirm your enrolment", ask nobody, and leave an application that could never
be priced for tuition by anyone, with nothing on any screen saying why.

`continuing_funding` asks for `registrar_email` now, so this path exists. It is
audited here rather than folded into `continuing_audit.py` because that one
signs in as the seeded student, who *has* history — the bug lived precisely in
the case a returning student cannot reproduce.

Registers its own throwaway student each run: the fault is about an account with
no past, and reusing one leaves a past behind on the second run. The account
looks like the ones `purge_applications --drop-test-accounts` clears.

    python manage.py runserver 127.0.0.1:8000
    python scripts/renewal_registrar_audit.py [--base http://127.0.0.1:8000]

Reads the outbox through the ORM as well as over HTTP, so `--base` alone is not
enough to point it at a second database — set DATABASE_URL to the same one, the
way lifecycle_audit.py documents.

Exits non-zero on any failed expectation.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import uuid
from pathlib import Path

import django
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from funding.models import EnrollmentVerification         # noqa: E402
from notifications.models import OutboundEmail            # noqa: E402

PASSWORD = 'DemoPass123!'

# One-pixel PNG. A real upload, because the bug that mattered on this project
# was in how the client asked, not in what the server did with it.
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

# Deliberately unlike anything the student typed, and unlike the seeded rates:
# the award has to be built from the registrar's figure and from nothing else.
CONFIRMED_TUITION = '6431.55'

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
    print(f'\n{title}\n{"-" * len(title)}')


class Session:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.http = requests.Session()

    def login(self, email: str, password: str = PASSWORD) -> bool:
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': password})
        if response.status_code != 200:
            return False
        self.http.headers['Authorization'] = f'Bearer {response.json()["access"]}'
        return True

    def get(self, path: str, **kwargs):
        return self.http.get(f'{self.base}{path}', **kwargs)

    def post(self, path: str, **kwargs):
        return self.http.post(f'{self.base}{path}', **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--staff', default='admin@dgg.test')
    arguments = parser.parse_args()
    base = arguments.base.rstrip('/')

    stamp = uuid.uuid4().hex[:8]
    email = f'renewal.{stamp}@example.com'
    registrar_email = f'registrar.{stamp}@aurora.test'

    section('A student the portal has never seen')
    registered = requests.post(f'{base}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'New', 'last_name': 'Comer',
        # Qualifies for something, or there would be no form to file.
        'eligibility': {
            'indian_act_registered': 'yes',
            'deline_beneficiary': 'yes',
            'receives_sfa': 'no',
            'lives_in_nwt': 'yes',
            'accredited_institution': 'yes',
            'programme_twelve_weeks': 'yes',
        },
    })
    if not check('registers', registered.status_code in (200, 201),
                 f'{registered.status_code} {registered.text[:300]}'):
        return 1

    student = Session(base)
    if not check('and can sign in', student.login(email)):
        return 1

    mine = student.get('/api/applications/').json()
    rows = mine.get('results', mine)
    check('has filed nothing at all', len(rows) == 0, str(rows)[:200])
    profile = student.get('/api/me/enrolment/').json()
    check('and has no registrar anywhere on file',
          not profile.get('registrar_email'), str(profile)[:200])

    section('The renewal, with nothing to carry')
    opening = student.get('/api/form-prefill/continuing_funding/')
    check('the form opens', opening.status_code == 200)
    prefilled = opening.json().get('answers', {}) if opening.status_code == 200 else {}
    check('and the registrar box opens empty, because nothing is on file',
          not prefilled.get('registrar_email'),
          'a pre-filled value here would make the rest of this audit prove '
          f'nothing about a student with no history: {prefilled}')

    def upload(field_key: str) -> str:
        response = student.post(
            '/api/documents/',
            files={'file': (f'{field_key}.png', io.BytesIO(PNG), 'image/png')},
            data={'field_key': field_key})
        return response.json()['reference'] if response.status_code in (200, 201) else ''

    answers = {
        'full_name': 'New Comer',
        'beneficiary_number': f'DGG-2026-{stamp[:4]}',
        'email': email,
        'institution_name': 'Aurora College',
        'registrar_email': registrar_email,
        'program': 'Nursing',
        'course_load': 'full_time',
        'dependent_count': 0,
        'semester': 'fall',
        'receives_sfa': False,
        'doc_transcript': upload('doc_transcript'),
        'doc_enrollment_confirmation': upload('doc_enrollment_confirmation'),
        # The renewal pays tuition and a living allowance and now asks where to
        # send them. Without this the award would be priced, approved and then
        # held out of the payment file — the fault this form's banking section
        # was added to close.
        'account_holder': 'New Comer',
        'transit_number': '12345',
        'institution_number': '003',
        'account_number': '7654321',
        'declaration_confirmed': True,
        'signature': 'New Comer',
    }

    without = {k: v for k, v in answers.items() if k != 'registrar_email'}
    refused = student.post('/api/applications/',
                           json={'type': 'continuing_funding', 'answers': without})
    check('a renewal naming no registrar is refused rather than silently unfulfillable',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    created = student.post('/api/applications/',
                           json={'type': 'continuing_funding', 'answers': answers})
    if not check('the renewal is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    app_id = created.json()['id']
    print(f'        application {app_id}')

    detail = student.get(f'/api/applications/{app_id}/').json()
    enrolment = detail.get('enrolment') or {}
    check('the institution WAS asked — this is the silence that used to be here',
          enrolment.get('registrar_email') == registrar_email,
          'the form promises the registrar is contacted; for a student with no '
          f'history nobody was. Got: {enrolment}')
    check('and the screen reports it asked rather than not_requested',
          enrolment.get('status') == 'requested', str(enrolment))

    section('What the registrar actually received')
    verification = EnrollmentVerification.objects.filter(application_id=app_id).first()
    if not check('a verification row exists', verification is not None):
        return 1
    queued = (OutboundEmail.objects
              .filter(to_email=registrar_email, body_html__contains=verification.token)
              .order_by('-id').first())
    # Read out of the outbox rather than from the row, because that is where a
    # real registrar gets it: a request raised and never queued is the same
    # silence one step further along.
    if not check('an email carrying the link was queued to that exact address',
                 queued is not None,
                 'the request was raised but nothing was queued to send'):
        return 1
    found = re.search(r'/enrolment/([A-Za-z0-9_\-]+)', queued.body_html)
    token = found.group(1) if found else ''
    check('the link in the body is usable', bool(token))
    if not token:
        return 1

    section('The registrar opens the link and confirms')
    opened = requests.get(f'{base}/api/enrolment/{token}/')
    check('opens without an account', opened.status_code == 200,
          f'{opened.status_code} {opened.text[:200]}')
    if opened.status_code == 200:
        context = opened.json()['application']
        check('it names the student', context.get('student_name') == 'New Comer',
              str(context)[:200])
        prefill = context.get('prefill') or {}
        check('and arrives pre-filled from the renewal',
              prefill.get('institution_name') == 'Aurora College', str(prefill)[:200])
        check('including the address to confirm back to',
              prefill.get('institution_email') == registrar_email, str(prefill)[:200])
        # Checked against the keys, not against the rendered dictionary.
        # `'sin' in str(prefill).lower()` is true of a student on a **Nurs**ing
        # programme, which is this project's substring fault in miniature — the
        # same class as "nt" inside Ontario. It fails loudly rather than passing
        # wrongly, but a check that cannot survive a real programme name is not
        # a check.
        check('and hands the institution no SIN and no date of birth',
              'sin' not in prefill and 'date_of_birth' not in prefill,
              str(sorted(prefill))[:300])

    confirmed = requests.post(f'{base}/api/enrolment/{token}/', json={'answers': {
        'is_enrolled': True,
        'student_name': 'New Comer',
        'institution_name': 'Aurora College',
        'program': 'Nursing',
        'course_load': 'full_time',
        'semester': 'fall',
        'semester_start': '2026-09-01',
        'semester_end': '2026-12-31',
        'confirmed_tuition': CONFIRMED_TUITION,
        'registrar_name': 'R. Registrar',
        'registrar_title': 'Registrar',
        'institution_email': registrar_email,
        'signature': 'R. Registrar',
        'completed_on': '2026-08-27',
    }})
    check('the registrar can confirm the enrolment', confirmed.status_code == 200,
          f'{confirmed.status_code} {confirmed.text[:400]}')
    check('and the link is single-use',
          requests.post(f'{base}/api/enrolment/{token}/',
                        json={'answers': {}}).status_code != 200)

    section('The figure the registrar gave is the one that gets funded')
    detail = student.get(f'/api/applications/{app_id}/').json()
    check("the registrar's tuition reached the application",
          float(detail['answers'].get('confirmed_tuition') or 0)
          == float(CONFIRMED_TUITION),
          repr(detail['answers'].get('confirmed_tuition')))

    staff = Session(base)
    if not check(f'{arguments.staff} can sign in', staff.login(arguments.staff),
                 'run: python manage.py seed_demo'):
        return 1
    staff.post(f'/api/applications/{app_id}/transition/', json={'action': 'reviewed'})
    priced = staff.post(f'/api/applications/{app_id}/price/', json={})
    if check('it can be priced — the thing that was impossible before',
             priced.status_code in (200, 201),
             f'{priced.status_code} {priced.text[:300]}'):
        decision = staff.get(f'/api/applications/{app_id}/').json().get('decision') or {}
        total = float(decision.get('total') or 0)
        check('and the award is more than nothing', total > 0,
              f'total {total}: the whole failure was tuition that could never '
              f'be awarded')
        # The tuition has to trace to the registrar's number rather than to a
        # rate or to anything the student typed — summed across the lines, not
        # matched against one of them.
        #
        # One semester's tuition is routinely several award lines: the
        # per-semester cap is paid by one rule and the balance by another, and
        # `remaining_tuition` is shared and decremented so no two streams fund
        # the same dollar. A check looking for a single line equal to the
        # figure passes only while the confirmed tuition sits under one cap,
        # which is a fact about the fixture rather than about the money.
        lines = decision.get('lines') or []
        tuition = [line for line in lines if 'tuition' in (line.get('rule_code') or '')]
        paid = sum(float(line.get('amount') or 0) for line in tuition)
        check('and the tuition lines add up to the registrar’s figure, to the penny',
              round(paid, 2) == float(CONFIRMED_TUITION),
              f'tuition rules paid {paid}, registrar confirmed {CONFIRMED_TUITION}; '
              f'lines were {[(l.get("rule_code"), l.get("amount")) for l in lines]}')
        print(f'        awarded {total}')

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
