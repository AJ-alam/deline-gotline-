"""Emergency relief, over HTTP, through every role that touches it.

Somebody files this on a bad day, which decides what is worth driving against
a running server rather than asserting about a schema:

  * it can be filed with nothing attached. A form that withholds help until a
    landlord writes a letter is the opposite of what this is for;
  * the amount is what gets paid, capped by the office's published maximum —
    so an inflated request must not beat the cap, and moving the cap must move
    what is paid;
  * the bank details reach the account finance pays from and never the answers
    column, which the detail endpoint returns whole;
  * a request approved for a real amount reaches the payment run.

    python manage.py runserver 127.0.0.1:8000
    python scripts/emergency_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import io
import sys
from decimal import Decimal

import requests

PASSWORD = 'DemoPass123!'

EXPECTED_FIELDS = {
    'full_name', 'email', 'phone', 'beneficiary_number',
    'emergency_type', 'emergency_description', 'amount_requested',
    'doc_supporting',
    'account_holder', 'transit_number', 'institution_number', 'account_number',
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

    def patch(self, path, **kw):
        return self.http.patch(f'{self.base}{path}', **kw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    base = parser.parse_args().base.rstrip('/')

    student, worker, director, finance, admin = (Session(base) for _ in range(5))
    print('\nSigning in as everyone who touches an emergency request')
    signed_in = all([
        student.login('student@dgg.test'),
        worker.login('worker@dgg.test'),
        director.login('director@dgg.test'),
        finance.login('finance@dgg.test'),
        admin.login('admin@dgg.test'),
    ])
    check('student, worker, director, finance and admin can all sign in', signed_in,
          'run: python manage.py seed_demo')
    if not signed_in:
        return 1

    print('\nThe form, as the browser asks for it')
    response = student.get('/api/schemas/emergency_relief/')
    if not check('the schema is fetchable', response.status_code == 200,
                 f'{response.status_code} {response.text[:200]}'):
        return 1
    schema = response.json()
    by_key = {field['key']: field for field in schema['fields']}

    check('it asks exactly what the office needs',
          set(by_key) == EXPECTED_FIELDS,
          f'unexpected {set(by_key) - EXPECTED_FIELDS}, '
          f'missing {EXPECTED_FIELDS - set(by_key)}')
    check('it falls into the three steps the client builds',
          schema['sections'] == ['Your details', 'The emergency',
                                 'Supporting documents', 'Payment', 'Declaration'],
          str(schema['sections']))
    check('a phone number is required — this is the form the office may have to '
          'answer today',
          by_key.get('phone', {}).get('required') is True)
    check('the nature of the emergency is a closed list',
          by_key.get('emergency_type', {}).get('type') == 'choice'
          and len(by_key.get('emergency_type', {}).get('choices', [])) == 5,
          str(by_key.get('emergency_type', 'absent')))
    check('the amount is money, because it is what gets paid',
          by_key.get('amount_requested', {}).get('type') == 'money')
    check('documents are plural',
          by_key.get('doc_supporting', {}).get('type') == 'files')
    check('and not required — waiting for a letter is not asking for help',
          by_key.get('doc_supporting', {}).get('required') is False)
    check('the declaration is a confirmation, not a yes/no',
          by_key.get('declaration_confirmed', {}).get('type') == 'confirm',
          'it used to have a signature and nothing above it to sign')
    check('the date signed opens on today',
          by_key.get('signed_on', {}).get('defaults_to_today') is True)

    answers = {
        'full_name': 'Majid Khan',
        'email': 'student@dgg.test',
        'phone': '8675550143',
        'emergency_type': 'housing',
        'emergency_description': 'The furnace failed and the rental is uninhabitable.',
        'amount_requested': '900',
        'account_holder': 'Majid Khan', 'transit_number': '12345',
        'institution_number': '001', 'account_number': '9876543210',
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
        'signed_on': '2026-08-15',
    }

    def submit(payload):
        return student.post('/api/applications/',
                            json={'type': 'emergency_relief', 'answers': payload})

    print('\nWhat the server refuses')
    refused = submit({**answers, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'emergency_type': 'car trouble'})
    check('an emergency outside the list is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'amount_requested': '-500'})
    check('a negative amount is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({k: v for k, v in answers.items() if k != 'phone'})
    check('a request with no phone number is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nAsking for help with nothing to hand')
    bare = submit({k: v for k, v in answers.items() if k != 'doc_supporting'})
    check('a request with no documents at all is accepted',
          bare.status_code == 201, f'{bare.status_code} {bare.text[:300]}')

    print('\nWith what evidence there is')
    references = []
    for name in ('landlord-letter.png', 'repair-quote.png'):
        upload = student.post('/api/documents/',
                              files={'file': (name, io.BytesIO(PNG), 'image/png')},
                              data={'field_key': 'doc_supporting'})
        if check(f'{name} uploads', upload.status_code in (200, 201),
                 f'{upload.status_code} {upload.text[:200]}'):
            references.append(upload.json()['reference'])

    created = submit({**answers, 'doc_supporting': references})
    if not check('the request is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    request_id = created.json()['id']
    stored = created.json()['answers']
    print(f'        application {request_id}')

    check('both documents survived as a list',
          stored.get('doc_supporting') == references,
          repr(stored.get('doc_supporting')))
    check('the account number is nowhere in the answers',
          'account_number' not in stored, str(sorted(stored)))
    check('and what happened reads back as it was written',
          'furnace' in str(stored.get('emergency_description', '')),
          repr(stored.get('emergency_description'))[:200])

    print('\nStaff queue — the worker')
    detail = worker.get(f'/api/applications/{request_id}/')
    if check('a reviewer can open it', detail.status_code == 200,
             f'{detail.status_code} {detail.text[:200]}'):
        body = detail.json()
        check('and is told an account is on file without being shown the number',
              body['banking']['on_file'] is True
              and '9876543210' not in detail.text,
              str(body.get('banking')))
        check('and has both documents',
              len(body['answers'].get('doc_supporting', [])) == 2,
              repr(body['answers'].get('doc_supporting')))

    reviewed = worker.post(f'/api/applications/{request_id}/transition/',
                           json={'action': 'reviewed'})
    check('a worker can take it under review', reviewed.status_code == 200,
          f'{reviewed.status_code} {reviewed.text[:300]}')
    forwarded = worker.post(f'/api/applications/{request_id}/transition/',
                            json={'action': 'forwarded'})
    check('and forward it without an enrolment confirmation it never needed',
          forwarded.status_code == 200, f'{forwarded.status_code} {forwarded.text[:300]}')
    check('a worker cannot price it',
          worker.post(f'/api/applications/{request_id}/price/').status_code == 403)

    print('\nDirector — the decision, and the cap')
    rates = admin.get('/api/policy/rates/')
    cap = None
    if check('an administrator can read the rates', rates.status_code == 200):
        cap = next((setting for group in rates.json()
                    if group['section'] == 'emergency_relief'
                    for setting in group['settings']
                    if setting['key'] == 'max_per_student'), None)
        check('the emergency cap is a published rate the office can move',
              cap is not None, 'no emergency_relief:max_per_student rate')

    director.post(f'/api/applications/{request_id}/transition/',
                  json={'action': 'approved'})
    priced = director.post(f'/api/applications/{request_id}/price/')
    if check('the director can price it', priced.status_code == 201,
             f'{priced.status_code} {priced.text[:300]}'):
        check('at what was asked for, since it is under the cap',
              Decimal(str(priced.json()['total'])) == Decimal('900'),
              f'{priced.json()["total"]} for a request of 900')

    if cap:
        lowered = admin.patch(f'/api/policy/rates/{cap["id"]}/', json={'value': '400'})
        check('an administrator can lower the cap below the request',
              lowered.status_code == 200, f'{lowered.status_code} {lowered.text[:200]}')
        again = director.post(f'/api/applications/{request_id}/price/')
        if check('and the request can be priced again', again.status_code == 201,
                 f'{again.status_code} {again.text[:300]}'):
            check('at the cap the office set, not the amount that was asked for',
                  Decimal(str(again.json()['total'])) == Decimal('400'),
                  f'{again.json()["total"]} against a cap of 400')
        restored = admin.patch(f'/api/policy/rates/{cap["id"]}/',
                               json={'value': str(cap['value'])})
        check('and the cap can be put back', restored.status_code == 200,
              f'{restored.status_code} {restored.text[:200]}')

    print('\nFinance — it is real money')
    run = finance.get('/api/finance/pending/')
    if check('the payment run is readable', run.status_code == 200,
             f'{run.status_code} {run.text[:200]}'):
        batch = run.json()
        listed = [row for row in batch['awards'] if row['application_id'] == request_id]
        blocked = [row for row in batch['blocked'] if row['application_id'] == request_id]
        check('the approved request reaches the run, or says why not',
              bool(listed) or bool(blocked),
              'it is neither payable nor blocked — it has fallen out of the run')
        if blocked:
            print(f'        blocked: {blocked[0]["reason"]}')

    print('\nAcross the portals')
    check('a student cannot price their own request',
          student.post(f'/api/applications/{request_id}/price/').status_code == 403)
    if cap:
        check('a student cannot move the emergency cap',
              student.patch(f'/api/policy/rates/{cap["id"]}/',
                            json={'value': '1'}).status_code == 403)
        check('nor can the director who decides the award',
              director.patch(f'/api/policy/rates/{cap["id"]}/',
                             json={'value': '1'}).status_code == 403)
    other = Session(base)
    if other.login('student2@dgg.test'):
        check('another student cannot read the request',
              other.get(f'/api/applications/{request_id}/').status_code in (403, 404))

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
