"""The appeal request, driven over HTTP through every role that touches it.

An appeal argues with a decision that has already been made. That makes it
unlike every other form here in three ways worth checking against the running
server rather than against the schema:

  * it can never be late. Filing after something went wrong is the point, and
    it only became possible to badge one late when the form started asking for
    a semester — any application carrying one gets a term, and a term with a
    deadline behind it gets a flag;
  * its evidence is plural, and every document has to reach the people deciding
    it;
  * it pays nothing, so it must pass through review and a decision without
    falling into the payment run or out of the queue.

    python manage.py runserver 127.0.0.1:8000
    python scripts/appeal_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import io
import sys

import requests

PASSWORD = 'DemoPass123!'

EXPECTED_FIELDS = {
    'full_name', 'student_number', 'institution_name', 'semester', 'academic_year',
    'appeal_reason', 'policy_reference',
    'doc_supporting',
    'declaration_confirmed', 'signature', 'signed_on',
}

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

checks = 0
failures: list[str] = []


def check(description: str, condition, detail: str = '') -> bool:
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)
    return bool(condition)


class Session:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.http = requests.Session()

    def login(self, email: str) -> bool:
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': PASSWORD})
        token = response.json().get('access') if response.status_code == 200 else None
        if not token:
            return False
        self.http.headers['Authorization'] = f'Bearer {token}'
        return True

    def get(self, path, **kw):
        return self.http.get(f'{self.base}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{self.base}{path}', **kw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    base = parser.parse_args().base.rstrip('/')

    student, worker, director, finance = (Session(base) for _ in range(4))
    print('\nSigning in as everyone who touches an appeal')
    signed_in = all([
        student.login('student@dgg.test'),
        worker.login('worker@dgg.test'),
        director.login('director@dgg.test'),
        finance.login('finance@dgg.test'),
    ])
    check('student, worker, director and finance can all sign in', signed_in,
          'run: python manage.py seed_demo')
    if not signed_in:
        return 1

    print('\nThe form, as the browser asks for it')
    response = student.get('/api/schemas/appeal/')
    if not check('the schema is fetchable', response.status_code == 200,
                 f'{response.status_code} {response.text[:200]}'):
        return 1
    schema = response.json()
    by_key = {field['key']: field for field in schema['fields']}

    check('it asks exactly what the office asked for',
          set(by_key) == EXPECTED_FIELDS,
          f'unexpected {set(by_key) - EXPECTED_FIELDS}, '
          f'missing {EXPECTED_FIELDS - set(by_key)}')
    check('it falls into the three steps the screens show',
          schema['sections'] == ['Student and academic context', 'Reason for appeal',
                                 'Supporting evidence', 'Declaration'],
          str(schema['sections']))
    check('the evidence takes more than one file',
          by_key.get('doc_supporting', {}).get('type') == 'files',
          str(by_key.get('doc_supporting', 'absent')))
    check('and is not required — not every appeal has a document behind it',
          by_key.get('doc_supporting', {}).get('required') is False)
    check('the policy reference is optional',
          by_key.get('policy_reference', {}).get('required') is False)
    check('the date signed opens on today',
          by_key.get('signed_on', {}).get('defaults_to_today') is True)
    check('no amount is asked for — an appeal pays nothing directly',
          'amount_requested' not in by_key)

    print('\nWhat the form opens with')
    prefill = student.get('/api/form-prefill/appeal/')
    if check('prefill is fetchable', prefill.status_code == 200,
             f'{prefill.status_code} {prefill.text[:200]}'):
        opening = prefill.json().get('answers', {})
        check('the student does not retype their own name',
              bool(opening.get('full_name')), str(opening))
        check('every prefilled key is one the schema defines',
              set(opening) <= set(by_key), str(set(opening) - set(by_key)))
        for key in ('appeal_reason', 'declaration_confirmed', 'signature'):
            check(f'{key} is left for the student to answer', key not in opening)

    print('\nEvidence')
    references = []
    for name in ('transcript.png', 'letter.png', 'medical-note.png'):
        upload = student.post('/api/documents/',
                              files={'file': (name, io.BytesIO(PNG), 'image/png')},
                              data={'field_key': 'doc_supporting'})
        if check(f'{name} uploads', upload.status_code in (200, 201),
                 f'{upload.status_code} {upload.text[:200]}'):
            references.append(upload.json()['reference'])
    check('three documents get three references', len(set(references)) == 3,
          str(references))

    answers = {
        'full_name': 'Majid Khan',
        'student_number': 'A-99213',
        'institution_name': 'Aurora College',
        'semester': 'fall',
        'academic_year': '2026-2027',
        'appeal_reason': ('The living allowance was priced for part-time study. '
                          'I was registered full-time for the whole term.'),
        'policy_reference': 'Section 4.2',
        'doc_supporting': references,
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
        'signed_on': '2026-08-15',
    }

    def submit(payload):
        return student.post('/api/applications/',
                            json={'type': 'appeal', 'answers': payload})

    print('\nWhat the server refuses')
    refused = submit({**answers, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({k: v for k, v in answers.items() if k != 'appeal_reason'})
    check('an appeal with no reason is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({k: v for k, v in answers.items() if k != 'semester'})
    check('an appeal that does not say which term it argues with is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'amount_requested': '5000'})
    check('an amount the form does not ask for is refused, not stored',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nStudent portal — filing it')
    created = submit(answers)
    if not check('the appeal is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    appeal = created.json()
    appeal_id = appeal['id']
    print(f'        application {appeal_id}')

    check('it is submitted, not left as a draft',
          appeal['status'] == 'submitted', appeal['status'])
    check('all three documents survived as a list',
          appeal['answers'].get('doc_supporting') == references,
          repr(appeal['answers'].get('doc_supporting')))
    # Read from the answers, which is where a client actually gets it: neither
    # the detail nor the list serializer exposes the stamped `semester` column.
    # That the column itself is written is covered by test_appeal.NeverLateTests
    # — this is about what a reviewer opening the appeal can see.
    check('the term it argues with is on the record a reviewer reads',
          appeal['answers'].get('semester') == 'fall',
          repr(appeal['answers'].get('semester')))
    check('and the academic year with it',
          appeal['answers'].get('academic_year') == '2026-2027',
          repr(appeal['answers'].get('academic_year')))
    # The reason this is worth a check over HTTP: a deadline for the term may
    # well have closed, and an appeal is the one form filed *because* something
    # already went wrong.
    check('and it is not badged as submitted late',
          appeal.get('submitted_after_deadline') is False,
          'an appeal is filed after the fact by definition')

    print('\nStaff queue — the worker')
    listed = worker.get('/api/applications/?type=appeal')
    if check('appeals can be filtered out of the queue', listed.status_code == 200,
             f'{listed.status_code} {listed.text[:200]}'):
        rows = listed.json().get('results', [])
        check('and this one is in the list',
              any(row['id'] == appeal_id for row in rows),
              f'{len(rows)} appeals listed, none of them this one')
        check('the filter returns appeals and nothing else',
              all(row['type'] == 'appeal' for row in rows),
              str({row['type'] for row in rows}))

    detail = worker.get(f'/api/applications/{appeal_id}/')
    if check('a reviewer can open it', detail.status_code == 200,
             f'{detail.status_code} {detail.text[:200]}'):
        seen = detail.json()['answers']
        check('and reads the argument being made',
              'part-time' in str(seen.get('appeal_reason', '')),
              repr(seen.get('appeal_reason'))[:200])
        check('and has all three documents, not just the first',
              len(seen.get('doc_supporting', [])) == 3,
              repr(seen.get('doc_supporting')))
        check('and the policy section the student relied on',
              seen.get('policy_reference') == 'Section 4.2',
              repr(seen.get('policy_reference')))

    reviewed = worker.post(f'/api/applications/{appeal_id}/transition/',
                           json={'action': 'reviewed'})
    check('a worker can take it under review', reviewed.status_code == 200,
          f'{reviewed.status_code} {reviewed.text[:300]}')
    forwarded = worker.post(f'/api/applications/{appeal_id}/transition/',
                            json={'action': 'forwarded'})
    check('and forward it without an enrolment confirmation it never needed',
          forwarded.status_code == 200, f'{forwarded.status_code} {forwarded.text[:300]}')
    check('a worker cannot decide it themselves',
          worker.post(f'/api/applications/{appeal_id}/transition/',
                      json={'action': 'approved'}).status_code == 403)

    print('\nDirector — the decision')
    check('the director can see it waiting',
          any(row['id'] == appeal_id
              for row in director.get('/api/applications/?status=awaiting_decision')
              .json().get('results', [])),
          'it is not in the awaiting-decision queue')

    approved = director.post(f'/api/applications/{appeal_id}/transition/',
                             json={'action': 'approved'})
    check('the director can allow the appeal', approved.status_code == 200,
          f'{approved.status_code} {approved.text[:300]}')

    print('\nFinance — an appeal pays nothing')
    run = finance.get('/api/finance/pending/')
    if check('the payment run is readable', run.status_code == 200,
             f'{run.status_code} {run.text[:200]}'):
        batch = run.json()
        in_run = [row for row in batch['awards'] + batch['blocked']
                  if row['application_id'] == appeal_id]
        check('and an allowed appeal is neither payable nor blocked in it',
              not in_run,
              f'an appeal reached the payment run: {in_run}')

    print('\nAcross the portals')
    check('a student cannot decide their own appeal',
          student.post(f'/api/applications/{appeal_id}/transition/',
                       json={'action': 'approved'}).status_code == 403)
    other = Session(base)
    if other.login('student2@dgg.test'):
        check('another student cannot read it',
              other.get(f'/api/applications/{appeal_id}/').status_code in (403, 404))

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
