"""Drive the travel claim against a running server, over HTTP.

The claim is the first form that asks a question with more than one answer: an
expense breakdown of as many lines as the trip had, and receipts as several
files rather than one. Both travel as lists, and a list is exactly the shape
that survives a unit test and dies on the way to the database — `jsonable`
stringified anything that was not a scalar, so a list of expense rows would have
been stored as the text of a Python repr and read back by nothing.

It also checks the thing the money depends on: the amount claimed is the sum of
the lines, worked out by the server, and cannot be sent by a client.

    python manage.py runserver 127.0.0.1:8000
    python scripts/travel_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on the first failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import io
import sys
from decimal import Decimal

import requests

PASSWORD = 'DemoPass123!'

# Everything the office's paper form asks, plus the purpose of travel — which
# the paper form leaves implicit and the award calculation caps against.
EXPECTED_FIELDS = {
    'first_name', 'last_name', 'date_of_birth', 'treaty_number',
    'beneficiary_number', 'email', 'phone',
    'travel_purpose', 'travel_from', 'travel_to',
    'departure_date', 'return_date', 'travel_mode', 'total_km',
    'expenses', 'amount_requested', 'doc_receipts',
    'account_holder', 'transit_number', 'institution_number', 'account_number',
    'declaration_confirmed', 'signature',
}

EXPENSES = [
    {'description': 'Air North YZF–YEG return', 'amount': '812.50', 'receipt_attached': True},
    {'description': 'Hotel, one night', 'amount': '189.00', 'receipt_attached': True},
    {'description': 'Taxi from airport', 'amount': '48.25', 'receipt_attached': True},
]
TOTAL = Decimal('1049.75')

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


def upload(session: Session, field_key: str, name: str) -> str:
    """A genuine multipart upload. Returns the reference the answer holds."""
    response = session.post(
        '/api/documents/',
        files={'file': (name, io.BytesIO(PNG), 'image/png')},
        data={'field_key': field_key},
    )
    check(f'uploading {name} is accepted as a file',
          response.status_code in (200, 201),
          f'{response.status_code} {response.text[:300]}')
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
    response = session.get('/api/schemas/travel/')
    check('the schema is fetchable', response.status_code == 200,
          f'{response.status_code} {response.text[:200]}')
    if response.status_code != 200:
        return 1
    schema = response.json()
    by_key = {field['key']: field for field in schema['fields']}
    keys = set(by_key)

    check('it asks exactly what the claim screen shows', keys == EXPECTED_FIELDS,
          f'unexpected {keys - EXPECTED_FIELDS}, missing {EXPECTED_FIELDS - keys}')
    check('it falls into the six sections the three steps are built from',
          set(schema['sections']) == {'Student', 'Travel', 'Expenses',
                                      'Receipts', 'Payment', 'Declaration'},
          str(schema['sections']))

    expenses = by_key.get('expenses', {})
    check('the expense breakdown is a table, not one amount in a box',
          expenses.get('type') == 'table', repr(expenses.get('type')))
    check('and the client is told what its columns are',
          {column['key'] for column in expenses.get('columns', [])}
          == {'description', 'amount', 'receipt_attached'},
          str(expenses.get('columns')))
    check('an amount inside the table is typed as money',
          next((c['type'] for c in expenses.get('columns', [])
                if c['key'] == 'amount'), None) == 'money')
    check('the number of lines is capped', bool(expenses.get('max_items')),
          'an uncapped list is a JSON column a client can fill')

    receipts = by_key.get('doc_receipts', {})
    check('receipts take more than one file', receipts.get('type') == 'files',
          repr(receipts.get('type')))
    check('and are required — the claim is paid against them',
          receipts.get('required') is True)

    total = by_key.get('amount_requested', {})
    check('the total is marked as worked out by the server',
          total.get('computed') is True, repr(total))
    check('and is therefore not a required question',
          total.get('required') is False)

    print('\nReceipts')
    references = [
        upload(session, 'doc_receipts', 'boarding-pass.png'),
        upload(session, 'doc_receipts', 'hotel.png'),
        upload(session, 'doc_receipts', 'taxi.png'),
    ]
    check('three separate receipts get three separate references',
          len(set(references)) == 3, str(references))

    complete = {
        'first_name': 'Majid', 'last_name': 'Khan',
        'date_of_birth': '2001-06-24', 'treaty_number': 'T-0041',
        'email': arguments.student,
        'travel_purpose': 'graduation',
        'travel_from': 'Deline, NT', 'travel_to': 'Edmonton, AB',
        'departure_date': '2026-05-28', 'return_date': '2026-06-02',
        'travel_mode': 'air',
        'expenses': EXPENSES,
        'doc_receipts': references,
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
    }

    def submit(answers):
        return session.post('/api/applications/',
                            json={'type': 'travel', 'answers': answers})

    print('\nWhat the server refuses')
    refused = submit({k: v for k, v in complete.items() if k != 'doc_receipts'})
    check('a claim with no receipts is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({**complete, 'expenses': []})
    check('a claim with no expense lines is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({**complete, 'expenses': [
        {'description': 'Taxi', 'amount': 'about forty dollars'}]})
    check('a line whose amount is not an amount is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    if refused.status_code == 400:
        message = str(refused.json())
        check('and the message says which line to fix', 'Row 1' in message,
              message[:300])

    refused = submit({**complete, 'expenses': [
        {'description': 'Flight', 'amount': '100', 'approved_by': 'me'}]})
    check('a column no form asks for is refused rather than stored',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    refused = submit({**complete, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nSubmitting')
    created = submit(complete)
    check('the claim is filed', created.status_code == 201,
          f'{created.status_code} {created.text[:400]}')
    if created.status_code != 201:
        return 1
    application = created.json()
    answers = application['answers']
    print(f'        application {application["id"]}, stream {application["stream"]}')

    check('it is submitted, not left as a draft',
          application['status'] == 'submitted', application['status'])

    print('\nWhat came back out')
    check('the expenses come back as rows, not as the text of a list',
          isinstance(answers.get('expenses'), list)
          and all(isinstance(row, dict) for row in answers.get('expenses', [])),
          repr(answers.get('expenses'))[:300])
    check('all three lines survived', len(answers.get('expenses', [])) == 3,
          repr(answers.get('expenses'))[:300])
    check('a description reads back as it was typed',
          answers['expenses'][0]['description'] == EXPENSES[0]['description'],
          repr(answers.get('expenses', [{}])[0]))
    check('the receipts come back as a list of stored references',
          isinstance(answers.get('doc_receipts'), list)
          and all(str(r).startswith('document:') for r in answers.get('doc_receipts', [])),
          repr(answers.get('doc_receipts')))
    check('all three receipts survived', len(answers.get('doc_receipts', [])) == 3,
          repr(answers.get('doc_receipts')))

    print('\nThe figure the award is calculated from')
    check('the total is the lines added up',
          Decimal(str(answers.get('amount_requested'))) == TOTAL,
          f'{answers.get("amount_requested")!r}, expected {TOTAL}')

    lied = submit({**complete, 'amount_requested': '99999.00'})
    check('a claim carrying its own total is still filed', lied.status_code == 201,
          f'{lied.status_code} {lied.text[:300]}')
    if lied.status_code == 201:
        check('and the total the client sent is discarded, not paid',
              Decimal(str(lied.json()['answers'].get('amount_requested'))) == TOTAL,
              f'server kept {lied.json()["answers"].get("amount_requested")!r}')

    blanks = submit({**complete, 'expenses': [
        EXPENSES[0], {'description': '', 'amount': ''}, EXPENSES[1], EXPENSES[2]]})
    check('a blank line typed and left alone is dropped, not counted',
          blanks.status_code == 201
          and len(blanks.json()['answers']['expenses']) == 3,
          f'{blanks.status_code} {blanks.text[:300]}')

    print('\nBank details, which this form also asks for')
    with_bank = submit({
        **complete,
        'account_holder': 'Majid Khan', 'transit_number': '12345',
        'institution_number': '001', 'account_number': '1234567',
    })
    check('a claim carrying bank details is filed', with_bank.status_code == 201,
          f'{with_bank.status_code} {with_bank.text[:300]}')
    if with_bank.status_code == 201:
        stored = with_bank.json()['answers']
        check('and the account number is nowhere in the answers',
              'account_number' not in stored, str(sorted(stored)))

    print('\nReading it back the way a reviewer does')
    detail = session.get(f'/api/applications/{application["id"]}/')
    check('the claim is readable back', detail.status_code == 200,
          f'{detail.status_code} {detail.text[:200]}')
    if detail.status_code == 200:
        read = detail.json()['answers']
        check('the reviewer sees the same three lines',
              len(read.get('expenses', [])) == 3, repr(read.get('expenses'))[:300])
        check('and the same total', str(read.get('amount_requested')) == str(TOTAL),
              repr(read.get('amount_requested')))

    print('\nThrough the office')
    reviewer = Session(arguments.base)
    approver = Session(arguments.base)
    payer = Session(arguments.base)
    # Evaluated eagerly rather than short-circuited: which of the three cannot
    # sign in is the thing worth knowing.
    signed_in = all([
        reviewer.login('worker@dgg.test'),
        approver.login('director@dgg.test'),
        payer.login('finance@dgg.test'),
    ])
    # `check` records the result; it does not return it. Branching on its return
    # value made this section exit before it ran a single check of substance,
    # and it reported success on the way out.
    check('the office can sign in', signed_in, 'run: python manage.py seed_demo')
    if not signed_in:
        return 1

    claim_id = application['id']

    # What a reviewer is actually shown. The expense lines are the claim; a
    # reviewer who cannot see them is approving a number.
    staff_view = reviewer.get(f'/api/applications/{claim_id}/')
    check('a reviewer can open the claim', staff_view.status_code == 200,
          f'{staff_view.status_code} {staff_view.text[:200]}')
    if staff_view.status_code == 200:
        seen = staff_view.json()['answers']
        check('and is shown the itemised lines, not just a total',
              isinstance(seen.get('expenses'), list) and len(seen['expenses']) == 3,
              repr(seen.get('expenses'))[:300])
        check('and the receipts that back them',
              len(seen.get('doc_receipts', [])) == 3, repr(seen.get('doc_receipts')))
        check('and the total the award will be calculated from',
              str(seen.get('amount_requested')) == str(TOTAL),
              repr(seen.get('amount_requested')))
        check('the account number is not on the reviewer\'s screen either',
              'account_number' not in seen, str(sorted(seen)))

    # A travel claim has no enrolment verification behind it, so unlike an
    # admission it should move without one. That gate applies to tuition, and
    # applying it here would strand every claim.
    reviewed = reviewer.post(f'/api/applications/{claim_id}/transition/',
                             json={'action': 'reviewed'})
    check('a worker can take it under review', reviewed.status_code == 200,
          f'{reviewed.status_code} {reviewed.text[:300]}')
    forwarded = reviewer.post(f'/api/applications/{claim_id}/transition/',
                              json={'action': 'forwarded'})
    check('and forward it without an enrolment confirmation it never needed',
          forwarded.status_code == 200, f'{forwarded.status_code} {forwarded.text[:300]}')

    check('a worker cannot approve it themselves',
          reviewer.post(f'/api/applications/{claim_id}/transition/',
                        json={'action': 'approved'}).status_code == 403)

    priced = approver.post(f'/api/applications/{claim_id}/price/')
    check('the director can price it', priced.status_code == 201,
          f'{priced.status_code} {priced.text[:300]}')
    if priced.status_code == 201:
        decision = priced.json()
        # The claim is 1049.75 against a 1200 cap for graduation travel, so it
        # is paid in full — and the figure has to be the one derived from the
        # lines, not one anybody typed.
        check('at the total derived from the expense lines',
              Decimal(str(decision['total'])) == TOTAL,
              f'{decision["total"]!r}, expected {TOTAL}')
        travel_line = next((rule for rule in decision['trace']['rules']
                            if rule['code'] == 'travel_assistance'), None)
        check('and the trace names the rule that produced it',
              travel_line is not None and travel_line['applied'] is True,
              str(travel_line))
        if travel_line:
            check('and says what it was capped against',
                  'capped at' in travel_line['reason'], travel_line['reason'])

    approved = approver.post(f'/api/applications/{claim_id}/transition/',
                             json={'action': 'approved'})
    check('the director can approve it', approved.status_code == 200,
          f'{approved.status_code} {approved.text[:300]}')

    run = payer.get('/api/finance/pending/')
    check('finance can see the payment run', run.status_code == 200,
          f'{run.status_code} {run.text[:200]}')
    if run.status_code == 200:
        batch = run.json()
        listed = [row for row in batch['awards'] if row['application_id'] == claim_id]
        blocked = [row for row in batch['blocked'] if row['application_id'] == claim_id]
        check('the approved claim reaches the run, or says why not',
              bool(listed) or bool(blocked),
              'it is neither payable nor blocked — it has fallen out of the run')
        if blocked:
            print(f'        blocked: {blocked[0]["reason"]}')
        if listed:
            check('and is to be paid the amount that was itemised',
                  Decimal(str(listed[0]['amount'])) == TOTAL,
                  f'{listed[0]["amount"]!r}, expected {TOTAL}')

    check('a student cannot price their own claim',
          session.post(f'/api/applications/{claim_id}/price/').status_code == 403)

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
