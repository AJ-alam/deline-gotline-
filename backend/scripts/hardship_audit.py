"""The emergency hardship bursary, over HTTP, through every role.

A last resort, and the form says so twice — the applicant attests to still being
active in their programme before describing anything, and again that they have
tried the supports that come before this one. Both are `CONFIRM` fields, and a
required BOOLEAN accepts False, so which one is in place only shows on the real
endpoint.

The rest is money. The amount is itemised and added up by the server, and the
cap is a rate the office moves without a deploy — the screen prints "$500 limit"
while the seeded rate says $3,000, which is exactly why that figure is not
written into the form.

    python manage.py runserver 127.0.0.1:8000
    python scripts/hardship_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

import requests

PASSWORD = 'DemoPass123!'

EXPECTED_FIELDS = {
    'full_name', 'beneficiary_number', 'institution_name', 'active_and_compliant',
    'hardship_reason', 'other_supports_attempted',
    'fund_breakdown', 'amount_requested',
    # Added 27 Aug 2026: this form pays money and asked for nowhere to send
    # it, so an approved award on it was held in the payment run reading "has
    # no bank account on file". See PROJECT_STATE.md §5.
    'account_holder', 'transit_number', 'institution_number', 'account_number',
    'declaration_confirmed', 'signature', 'signed_on',
}

# An itemisation that sits *under* the published cap, so this audit is about
# the total the server derives from the lines rather than about the cap. It
# used to add up to $640.50 against a seeded cap of $3,000; §9(G) of the policy
# puts the cap at $500, so the claim was over it and the check that the total
# is paid in full became a check that it is not.
LINES = [
    {'purpose': 'Overdue rent', 'amount': '260.00'},
    {'purpose': 'Groceries for the month', 'amount': '90.50'},
    {'purpose': 'Bus pass', 'amount': '60.00'},
]
TOTAL = Decimal('410.50')

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
    print('\nSigning in as everyone who touches a hardship request')
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
    response = student.get('/api/schemas/hardship_bursary/')
    if not check('the schema is fetchable', response.status_code == 200,
                 f'{response.status_code} {response.text[:200]}'):
        return 1
    schema = response.json()
    by_key = {field['key']: field for field in schema['fields']}

    check('it asks exactly what the office asked for',
          set(by_key) == EXPECTED_FIELDS,
          f'unexpected {set(by_key) - EXPECTED_FIELDS}, '
          f'missing {EXPECTED_FIELDS - set(by_key)}')
    check('it falls into the four steps the screens show',
          schema['sections'] == ['Student information', 'The emergency',
                                 'Fund breakdown', 'Payment', 'Declaration'],
          str(schema['sections']))
    check("it is titled the way the office titles it",
          schema['label'] == 'Emergency Hardship Bursary (Last Resort)',
          repr(schema['label']))
    check('being active in the programme is a confirmation, not a yes/no',
          by_key.get('active_and_compliant', {}).get('type') == 'confirm',
          str(by_key.get('active_and_compliant', 'absent')))
    check('what else was tried is required — this is a last resort',
          by_key.get('other_supports_attempted', {}).get('required') is True)
    check('the fund breakdown is a table, not one amount in a box',
          by_key.get('fund_breakdown', {}).get('type') == 'table')
    check('and the client is told its columns',
          [column['key'] for column in by_key.get('fund_breakdown', {}).get('columns', [])]
          == ['purpose', 'amount'],
          str(by_key.get('fund_breakdown', {}).get('columns')))
    check('the number of lines is capped',
          bool(by_key.get('fund_breakdown', {}).get('max_items')))
    check('the total is worked out by the server',
          by_key.get('amount_requested', {}).get('computed') is True)
    check('the date signed opens on today',
          by_key.get('signed_on', {}).get('defaults_to_today') is True)
    check('no cap figure is written into the form',
          not any('$' in field.get('help_text', '') for field in schema['fields']),
          "the screen prints a $500 limit and the rate says $3,000 — a figure "
          'in two places is a figure that can disagree')

    answers = {
        'full_name': 'Majid Khan',
        'beneficiary_number': 'B-1017',
        'institution_name': 'Aurora College',
        'active_and_compliant': True,
        'hardship_reason': 'My hours were cut and rent is two weeks overdue.',
        'other_supports_attempted': 'The food bank, and my aunt, who has none to spare.',
        'fund_breakdown': LINES,
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
        'signed_on': '2026-08-15',
    }

    def submit(payload):
        return student.post('/api/applications/',
                            json={'type': 'hardship_bursary', 'answers': payload})

    print('\nWhat the server refuses')
    refused = submit({**answers, 'active_and_compliant': False})
    check('somebody who says they are not active in their programme cannot file it',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({k: v for k, v in answers.items()
                      if k != 'other_supports_attempted'})
    check('nor can somebody who will not say what else they tried',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'fund_breakdown': []})
    check('a request with no breakdown at all is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'fund_breakdown': [
        {'purpose': 'Rent', 'amount': 'about four hundred'}]})
    check('a line whose amount is not an amount is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    if refused.status_code == 400:
        check('and the message says which line to fix', 'Row 1' in refused.text,
              refused.text[:300])
    refused = submit({**answers, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nStudent portal — filing it')
    created = submit(answers)
    if not check('the request is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    request_id = created.json()['id']
    stored = created.json()['answers']
    print(f'        application {request_id}')

    check('the breakdown comes back as rows, not as the text of a list',
          isinstance(stored.get('fund_breakdown'), list)
          and all(isinstance(row, dict) for row in stored.get('fund_breakdown', [])),
          repr(stored.get('fund_breakdown'))[:300])
    check('all three lines survived', len(stored.get('fund_breakdown', [])) == 3)
    check('the total is the lines added up',
          Decimal(str(stored.get('amount_requested'))) == TOTAL,
          f'{stored.get("amount_requested")!r}, expected {TOTAL}')

    lied = submit({**answers, 'amount_requested': '99999.00'})
    if check('a request carrying its own total is still filed',
             lied.status_code == 201, f'{lied.status_code} {lied.text[:300]}'):
        check('and the total the client sent is discarded, not paid',
              Decimal(str(lied.json()['answers'].get('amount_requested'))) == TOTAL,
              f'server kept {lied.json()["answers"].get("amount_requested")!r}')

    blanks = submit({**answers, 'fund_breakdown': [
        LINES[0], {'purpose': '', 'amount': ''}, LINES[1], LINES[2]]})
    check('a blank line typed and left alone is dropped, not counted',
          blanks.status_code == 201
          and len(blanks.json()['answers']['fund_breakdown']) == 3,
          f'{blanks.status_code} {blanks.text[:300]}')

    print('\nStaff queue — the worker')
    detail = worker.get(f'/api/applications/{request_id}/')
    if check('a reviewer can open it', detail.status_code == 200,
             f'{detail.status_code} {detail.text[:200]}'):
        seen = detail.json()['answers']
        check('and is shown the itemised lines, not just a total',
              len(seen.get('fund_breakdown', [])) == 3,
              repr(seen.get('fund_breakdown'))[:300])
        check('and what else the student already tried',
              'food bank' in str(seen.get('other_supports_attempted', '')),
              repr(seen.get('other_supports_attempted'))[:200])
        check('and the attestation, stored as a real true',
              seen.get('active_and_compliant') is True,
              repr(seen.get('active_and_compliant')))

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

    print('\nDirector and admin — the total, and the cap the office sets')
    rates = admin.get('/api/policy/rates/')
    cap = None
    if check('an administrator can read the rates', rates.status_code == 200):
        cap = next((setting for group in rates.json()
                    if group['section'] == 'hardship_bursary'
                    for setting in group['settings']
                    if setting['key'] == 'max_per_student'), None)
        check('the hardship cap is a published rate', cap is not None,
              'no hardship_bursary:max_per_student rate')
        if cap:
            print(f'        cap is ${cap["value"]}')

    director.post(f'/api/applications/{request_id}/transition/',
                  json={'action': 'approved'})
    priced = director.post(f'/api/applications/{request_id}/price/')
    if check('the director can price it', priced.status_code == 201,
             f'{priced.status_code} {priced.text[:300]}'):
        # Only meaningful while the itemisation is under the cap. Said out
        # loud, because the fixture silently stopped being under it once the
        # policy cap came down and the check went on reading as a pricing bug.
        if cap and Decimal(str(cap['value'])) < TOTAL:
            check('the itemised claim is under the published cap', False,
                  f'cap ${cap["value"]} is below the itemised {TOTAL}; '
                  'the fixture needs lowering, this is not a pricing fault')
        else:
            check('at the total derived from the breakdown, since it is under the cap',
                  Decimal(str(priced.json()['total'])) == TOTAL,
                  f'{priced.json()["total"]} against an itemised {TOTAL}')

    if cap:
        lowered = admin.patch(f'/api/policy/rates/{cap["id"]}/', json={'value': '300'})
        check('an administrator can lower the cap below the breakdown',
              lowered.status_code == 200, f'{lowered.status_code} {lowered.text[:200]}')
        again = director.post(f'/api/applications/{request_id}/price/')
        if check('and the request can be priced again', again.status_code == 201,
                 f'{again.status_code} {again.text[:300]}'):
            check('at the cap the office set, not the amount itemised',
                  Decimal(str(again.json()['total'])) == Decimal('300'),
                  f'{again.json()["total"]} against a cap of 300')
        restored = admin.patch(f'/api/policy/rates/{cap["id"]}/',
                               json={'value': str(cap['value'])})
        check('and the cap can be put back', restored.status_code == 200,
              f'{restored.status_code} {restored.text[:200]}')

    print('\nFinance')
    run = finance.get('/api/finance/pending/')
    if check('the payment run is readable', run.status_code == 200,
             f'{run.status_code} {run.text[:200]}'):
        batch = run.json()
        seen = [row for row in batch['awards'] + batch['blocked']
                if row['application_id'] == request_id]
        check('the approved request reaches the run, or says why not', bool(seen),
              'it is neither payable nor blocked — it has fallen out of the run')

    print('\nAcross the portals')
    check('a student cannot price their own request',
          student.post(f'/api/applications/{request_id}/price/').status_code == 403)
    if cap:
        check('a student cannot move the hardship cap',
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
