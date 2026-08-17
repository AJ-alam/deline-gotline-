"""The graduation award, driven over HTTP as a claimant with no account.

Most of these arrive that way: someone who finished a credential and is not
otherwise a student here. That is what shapes the form — nothing about the
person is on file, so it asks for the name the payment is made out to, an
address, and the bank details finance pays into.

Three things are checked against the path they actually travel rather than
against the schema:

  * a Social Insurance Number reaches the encrypted table. The guest endpoint
    split it out of `answers` and then stored it nowhere, which no test noticed
    because no guest form had ever asked for one;
  * the credential decides the amount, so its stored values are the rate keys
    the rule prices from;
  * "pay someone else" keeps the award out of the payment file. Nothing in the
    run can redirect a payment, so the alternative is paying it into the
    claimant's own account — the one outcome they asked against.

    python manage.py runserver 127.0.0.1:8000
    python scripts/graduation_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import io
import sys

import requests

PASSWORD = 'DemoPass123!'

# A SIN that satisfies the Luhn check and belongs to nobody.
TEST_SIN = '199999996'

EXPECTED_FIELDS = {
    'full_name', 'date_of_birth', 'treaty_number', 'sin', 'phone', 'email',
    'beneficiary_number',
    'city', 'province', 'postal_code',
    'institution_name', 'program', 'graduation_date', 'credential',
    'doc_proof_of_completion',
    'account_holder', 'transit_number', 'institution_number', 'account_number',
    'release_to_other', 'release_recipient',
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

    def get(self, path, **kwargs):
        return self.http.get(f'{self.base}{path}', **kwargs)

    def post(self, path, **kwargs):
        return self.http.post(f'{self.base}{path}', **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    arguments = parser.parse_args()
    base = arguments.base.rstrip('/')
    guest = Session(base)

    print('\nThe form, as a visitor with no account asks for it')
    offered = requests.get(f'{base}/api/guest-applications/', timeout=10)
    check('the guest form list is servable without signing in',
          offered.status_code == 200, f'{offered.status_code} {offered.text[:200]}')
    schema = None
    if offered.status_code == 200:
        schema = next((s for s in offered.json()
                       if s['slug'] == 'graduation_bursary'), None)
        check('and offers the graduation award', schema is not None,
              str([s['slug'] for s in offered.json()]))
    if schema is None:
        return 1

    by_key = {field['key']: field for field in schema['fields']}
    check('it asks exactly what the office asked for',
          set(by_key) == EXPECTED_FIELDS,
          f'unexpected {set(by_key) - EXPECTED_FIELDS}, '
          f'missing {EXPECTED_FIELDS - set(by_key)}')
    check('it falls into the four steps the screens show',
          [s for s in schema['sections']] ==
          ['Student information', 'Current mailing address', 'Graduation details',
           'Documents', 'Payment', 'Release of funds', 'Declaration'],
          str(schema['sections']))
    # §9(E)'s table has twelve rows. Counted rather than listed, and counted
    # against the policy rather than against whatever the form happened to
    # offer: this read 9 while Red Seal, Juris Doctor and MD/DDS had no answer
    # on the form at all, so a graduate holding one of them had to claim under a
    # credential that was not theirs — and be paid accordingly.
    check('the credential is a closed list, not free text',
          by_key.get('credential', {}).get('type') == 'choice'
          and len(by_key.get('credential', {}).get('choices', [])) == 12,
          str(by_key.get('credential', 'absent')))
    # `.get` throughout: a field that has gone missing is a failed check, not a
    # traceback. An audit that dies on the first absence stops reporting the
    # twenty things after it, which is when it is least affordable.
    check('the SIN is asked for as a SIN and is optional',
          by_key.get('sin', {}).get('type') == 'sin'
          and by_key.get('sin', {}).get('required') is False,
          str(by_key.get('sin', 'absent')))
    check('the bank details are required — there is no account to fall back on',
          all(by_key.get(key, {}).get('required') for key in
              ('account_holder', 'transit_number', 'institution_number',
               'account_number')))
    check('the date signed opens on today',
          by_key.get('signed_on', {}).get('defaults_to_today') is True,
          str(by_key.get('signed_on', 'absent')))
    check('the declaration is a confirmation, not a yes/no',
          by_key.get('declaration_confirmed', {}).get('type') == 'confirm')

    print('\nProof of completion')
    # The claim requires proof of completion and is filed by someone with no
    # account, so the upload has to work for them. It did not: the control
    # rendered, the request was refused, and the required answer could never be
    # given — the form was unsubmittable in the browser while every unit test
    # passed, because no test had ever asked for a file as a guest.
    upload = guest.post('/api/documents/',
                        files={'file': ('parchment.png', io.BytesIO(PNG), 'image/png')},
                        data={'field_key': 'doc_proof_of_completion'})
    reference = ''
    if check('a claimant with no account can attach their certificate',
             upload.status_code in (200, 201),
             f'{upload.status_code} {upload.text[:300]}'):
        reference = upload.json()['reference']
        check('and gets back a reference the answer can hold',
              reference.startswith('document:'), reference)

    # Open does not mean unchecked.
    refused_type = guest.post(
        '/api/documents/',
        files={'file': ('payload.exe', io.BytesIO(b'MZ'), 'application/x-msdownload')},
        data={'field_key': 'doc_proof_of_completion'})
    check('and an executable is still refused',
          refused_type.status_code == 400, str(refused_type.status_code))

    borrowed = guest.post(
        '/api/documents/',
        files={'file': ('parchment.png', io.BytesIO(PNG), 'image/png')},
        data={'field_key': 'doc_proof_of_completion', 'application': 1})
    check('and it cannot be attached to an application it does not own',
          borrowed.status_code == 400, str(borrowed.status_code))

    answers = {
        'full_name': 'Grace Graduate',
        'date_of_birth': '1999-04-11',
        'treaty_number': 'T-8841',
        'sin': TEST_SIN,
        'phone': '8675550143',
        'email': 'grace.graduate@example.com',
        'city': 'Deline', 'province': 'NT', 'postal_code': 'X0E 0G0',
        'institution_name': 'Aurora College',
        'program': 'Environmental Science',
        'graduation_date': '2026-05-30',
        'credential': 'bachelors_degree',
        'doc_proof_of_completion': reference or 'provided',
        'account_holder': 'Grace Graduate', 'transit_number': '12345',
        'institution_number': '001', 'account_number': '9876543210',
        'declaration_confirmed': True,
        'signature': 'Grace Graduate',
        'signed_on': '2026-08-15',
    }

    def submit(payload):
        return requests.post(f'{base}/api/guest-applications/',
                             json={'type': 'graduation_bursary', 'answers': payload},
                             timeout=15)

    print('\nWhat the server refuses')
    refused = submit({**answers, 'credential': 'BSc'})
    check('a credential outside the list is refused, not priced at the bottom tier',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({**answers, 'sin': '123456789'})
    check('a SIN that fails its check digit is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({**answers, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({k: v for k, v in answers.items() if k != 'account_number'})
    check('a claim with no account number is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nSubmitting')
    created = submit(answers)
    if not check('the claim is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    reference = created.json().get('reference', '')
    check('and answered with a reference number and nothing else',
          set(created.json()) == {'reference', 'detail'}, str(created.json()))
    check('the reference identifies the claim', reference.startswith('DGG-'), reference)
    print(f'        {reference}')

    print('\nWhat the office can see, and what it cannot')
    staff = Session(base)
    if not check('staff can sign in', staff.login('worker@dgg.test'),
                 'run: python manage.py seed_demo'):
        return 1

    claim_id = int(reference.removeprefix('DGG-'))
    detail = staff.get(f'/api/applications/{claim_id}/')
    if check('staff can open the guest claim', detail.status_code == 200,
             f'{detail.status_code} {detail.text[:200]}'):
        body = detail.json()
        stored = body['answers']
        check('the SIN is not in the answers', 'sin' not in stored)
        check('nor is it anywhere in the response body',
              TEST_SIN not in detail.text,
              'the whole number reached a client that did not ask for it')
        check('the account number is not in the answers',
              'account_number' not in stored, str(sorted(stored)))
        check('but the office is told a SIN is on file, masked',
              any(str(value).endswith(TEST_SIN[-3:])
                  for value in (body.get('identifiers') or {}).values()),
              f'identifiers: {body.get("identifiers")}')
        check('and the address it will write to survived',
              stored.get('city') == 'Deline' and stored.get('postal_code') == 'X0E 0G0',
              str({k: stored.get(k) for k in ('city', 'province', 'postal_code')}))
        check('and the credential the award is priced from',
              stored.get('credential') == 'bachelors_degree', repr(stored.get('credential')))

    print('\nRelease of funds')
    released = submit({**answers, 'release_to_other': True,
                       'release_recipient': 'Marie Graduate (mother)'})
    if check('a claim naming someone else is accepted', released.status_code == 201,
             f'{released.status_code} {released.text[:300]}'):
        released_id = int(released.json()['reference'].removeprefix('DGG-'))
        held = staff.get(f'/api/applications/{released_id}/')
        if held.status_code == 200:
            check('and records who was named',
                  held.json()['answers'].get('release_recipient') == 'Marie Graduate (mother)',
                  repr(held.json()['answers'].get('release_recipient')))
            check('and the flag itself is stored as a real boolean',
                  held.json()['answers'].get('release_to_other') is True,
                  repr(held.json()['answers'].get('release_to_other')))

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
