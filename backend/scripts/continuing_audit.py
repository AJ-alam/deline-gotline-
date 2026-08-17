"""Drive the continuing-funding renewal against a running server, over HTTP.

Every serious defect on this project was found this way rather than by reading
code or by passing unit tests — a filter backend that ignored every query
parameter, a client that sent file uploads as JSON. Both had a green suite.

This exercises the renewal the way the browser does: log in, ask what the form
is, ask what it opens with, upload real files, submit, and check that what came
out the other end is what the award calculation will actually read.

    python manage.py runserver 127.0.0.1:8000
    python scripts/continuing_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on the first failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import io
import sys
import uuid

import requests

PASSWORD = 'DemoPass123!'

# Exactly what the renewal screen shows.
EXPECTED_FIELDS = {
    'full_name', 'beneficiary_number', 'email',
    'institution_name', 'program', 'course_load', 'dependent_count',
    'semester', 'receives_sfa',
    'doc_transcript', 'doc_enrollment_confirmation',
    'declaration_confirmed', 'signature',
}

# One-pixel PNG. A real upload, because the bug that mattered was in how the
# client asked, not in what the server did with it.
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

checks = 0
failures: list[str] = []


def check(description: str, condition: bool, detail: str = '') -> None:
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)


class Session:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.http = requests.Session()

    def login(self, email: str, password: str = PASSWORD) -> bool:
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': password})
        if response.status_code != 200:
            return False
        token = response.json().get('access')
        if not token:
            return False
        self.http.headers['Authorization'] = f'Bearer {token}'
        return True

    def get(self, path: str, **kwargs):
        return self.http.get(f'{self.base}{path}', **kwargs)

    def post(self, path: str, **kwargs):
        return self.http.post(f'{self.base}{path}', **kwargs)


def upload(session: Session, field_key: str) -> str:
    """A genuine multipart upload. Returns the reference the answer holds."""
    response = session.post(
        '/api/documents/',
        files={'file': (f'{field_key}.png', io.BytesIO(PNG), 'image/png')},
        data={'field_key': field_key},
    )
    check(f'uploading {field_key} is accepted as a file',
          response.status_code in (200, 201), f'{response.status_code} {response.text[:300]}')
    if response.status_code not in (200, 201):
        return ''
    return response.json()['reference']


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--student', default='student@dgg.test')
    arguments = parser.parse_args()

    session = Session(arguments.base)

    print('\nSigning in')
    if not session.login(arguments.student):
        print(f'  FAIL  could not sign in as {arguments.student}')
        print('        Run: python manage.py seed_demo')
        return 1
    print(f'  ok    signed in as {arguments.student}')

    print('\nThe form, as the browser asks for it')
    response = session.get('/api/schemas/continuing_funding/')
    check('the schema is fetchable', response.status_code == 200,
          f'{response.status_code} {response.text[:200]}')
    if response.status_code != 200:
        return 1
    schema = response.json()
    keys = {field['key'] for field in schema['fields']}
    check('it asks exactly what the renewal screen shows', keys == EXPECTED_FIELDS,
          f'unexpected {keys - EXPECTED_FIELDS}, missing {EXPECTED_FIELDS - keys}')

    by_key = {field['key']: field for field in schema['fields']}
    check('the SFA question is required',
          by_key.get('receives_sfa', {}).get('required') is True)
    check('the SFA question is a real boolean, not a yes/no word',
          by_key.get('receives_sfa', {}).get('type') == 'boolean',
          "a choice field spelled yes/no reads as 'on SFA' for both answers")
    check('the semester is required',
          by_key.get('semester', {}).get('required') is True)
    check('the declaration is its own type, not an ordinary tick',
          by_key.get('declaration_confirmed', {}).get('type') == 'confirm')
    check('the form falls into the two steps the screen shows',
          set(schema['sections']) == {'Review your information',
                                      'Upload required documents', 'Declaration'},
          str(schema['sections']))

    print('\nWhat the form opens with')
    response = session.get('/api/form-prefill/continuing_funding/')
    check('prefill is fetchable', response.status_code == 200,
          f'{response.status_code} {response.text[:200]}')
    prefilled = response.json().get('answers', {}) if response.status_code == 200 else {}
    check('it is never cached in between',
          'no-store' in response.headers.get('Cache-Control', ''),
          response.headers.get('Cache-Control', '<absent>'))
    check('the student does not retype their own name',
          bool(prefilled.get('full_name')), str(prefilled))
    check('nor their contact email', bool(prefilled.get('email')))
    check('every prefilled key is one the schema defines',
          set(prefilled) <= keys, str(set(prefilled) - keys))
    for key in ('semester', 'receives_sfa', 'declaration_confirmed', 'signature'):
        check(f'{key} is left for the student to answer', key not in prefilled)

    print('\nDocuments')
    transcript = upload(session, 'doc_transcript')
    enrolment_copy = upload(session, 'doc_enrollment_confirmation')

    print('\nWhat the server refuses')
    complete = {
        'full_name': prefilled.get('full_name') or 'Majid Khan',
        'beneficiary_number': prefilled.get('beneficiary_number') or 'DGG-2026-0041',
        'email': prefilled.get('email') or arguments.student,
        'institution_name': prefilled.get('institution_name') or 'Aurora College',
        'program': prefilled.get('program') or 'Environmental Science',
        'course_load': 'full_time',
        'dependent_count': 2,
        'semester': 'fall',
        'receives_sfa': False,
        'doc_transcript': transcript,
        'doc_enrollment_confirmation': enrolment_copy,
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
    }

    def submit(answers):
        return session.post('/api/applications/',
                            json={'type': 'continuing_funding', 'answers': answers})

    refused = submit({**complete, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    without_sfa = {k: v for k, v in complete.items() if k != 'receives_sfa'}
    refused = submit(without_sfa)
    check('an unanswered SFA question is refused, not read as "no"',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    without_semester = {k: v for k, v in complete.items() if k != 'semester'}
    refused = submit(without_semester)
    check('an unanswered semester is refused, not left unmeasured',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({**complete, 'tuition_requested': '6000'})
    check("a student's own tuition figure is not accepted here",
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nSubmitting')
    created = submit(complete)
    check('the renewal is filed', created.status_code == 201,
          f'{created.status_code} {created.text[:400]}')
    if created.status_code != 201:
        return 1
    application = created.json()
    print(f'        application {application["id"]}, stream {application["stream"]}')

    check('it is submitted, not left as a draft',
          application['status'] == 'submitted', application['status'])
    check('the declaration is stored as a real true',
          application['answers'].get('declaration_confirmed') is True)
    check('the SFA answer is stored as a real boolean',
          isinstance(application['answers'].get('receives_sfa'), bool),
          repr(application['answers'].get('receives_sfa')))
    check('the documents are references to stored files, not claims',
          str(application['answers'].get('doc_transcript', '')).startswith('document:'),
          repr(application['answers'].get('doc_transcript')))
    check('the registrar email is not copied into the renewal',
          'registrar_email' not in application['answers'])

    print('\nOn SFA, the same student is not funded from PSSSP')
    on_sfa = submit({**complete, 'receives_sfa': True})
    check('a renewal declaring SFA is filed', on_sfa.status_code == 201,
          f'{on_sfa.status_code} {on_sfa.text[:200]}')
    if on_sfa.status_code == 201:
        check('and lands in a different stream than the one that declared no SFA',
              on_sfa.json()['stream'] != application['stream'],
              f"both came out as {application['stream']}")

    print('\nThe enrolment verification the banner promises')
    detail = session.get(f'/api/applications/{application["id"]}/')
    check('the renewal is readable back', detail.status_code == 200)
    if detail.status_code == 200:
        enrolment = detail.json().get('enrolment') or {}
        check('a verification was raised for it',
              enrolment.get('required') is True
              and enrolment.get('status') not in (None, 'not_required'),
              'the form says DGG will contact the registrar; nothing was raised. '
              f'Check the student has an earlier application carrying a registrar '
              f'email. Got: {enrolment}')
        check('addressed to the registrar from the application on file',
              bool(enrolment.get('registrar_email')), str(enrolment))
        check('and the renewal itself never asked for that address',
              'registrar_email' not in keys)
        print(f'        addressed to {enrolment.get("registrar_email")}')

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
