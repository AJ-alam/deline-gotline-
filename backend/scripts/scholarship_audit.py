"""The academic achievement scholarship, over HTTP, through every role.

The grade decides the amount. That makes this the form where the two failures
this project keeps having are most expensive: a display string that carries
meaning, and a figure written in two places that agree only by habit.

So besides the shape of the form, this drives the thing that was actually
broken — an administrator moving an achievement threshold on the policy screen
and the engine paying against it. Both thresholds were published as editable
rates while the rule carried 80 and 70 written into it, so the screen offered a
change that saved, recorded a history entry, and did nothing.

    python manage.py runserver 127.0.0.1:8000
    python scripts/scholarship_audit.py [--base http://127.0.0.1:8000]

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
    'full_name', 'beneficiary_number', 'institution_name',
    'semester', 'academic_year',
    'gpa_achieved', 'transcripts_status', 'doc_transcript',
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

    student, worker, director, admin = (Session(base) for _ in range(4))
    print('\nSigning in as everyone who touches a scholarship')
    signed_in = all([
        student.login('student@dgg.test'),
        worker.login('worker@dgg.test'),
        director.login('director@dgg.test'),
        admin.login('admin@dgg.test'),
    ])
    check('student, worker, director and admin can all sign in', signed_in,
          'run: python manage.py seed_demo')
    if not signed_in:
        return 1

    print('\nThe form, as the browser asks for it')
    response = student.get('/api/schemas/academic_scholarship/')
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
          schema['sections'] == ['Program information', 'Achievements', 'Declaration'],
          str(schema['sections']))
    check('the grade is a bounded percentage, not free text',
          by_key.get('gpa_achieved', {}).get('type') == 'percent',
          str(by_key.get('gpa_achieved', 'absent')))
    check('the transcript is required — the band is awarded against it',
          by_key.get('doc_transcript', {}).get('required') is True)
    check('the transcript status is a closed list',
          by_key.get('transcripts_status', {}).get('type') == 'choice'
          and len(by_key.get('transcripts_status', {}).get('choices', [])) == 3,
          str(by_key.get('transcripts_status', 'absent')))
    check('the date signed opens on today',
          by_key.get('signed_on', {}).get('defaults_to_today') is True)
    check('no bank details are asked for — this needs an account already',
          not ({'account_holder', 'account_number'} & set(by_key)))
    check('and no award amount is written into the form',
          not any('$' in field.get('help_text', '') for field in schema['fields']),
          'the amounts are policy rates; a copy in help text is a second place '
          'for them to disagree')

    print('\nWhat the server refuses')
    answers = {
        'full_name': 'Majid Khan',
        'beneficiary_number': 'B-1017',
        'institution_name': 'Aurora College',
        'semester': 'fall',
        'academic_year': '2026-2027',
        'gpa_achieved': '85',
        'transcripts_status': 'uploading_now',
        'doc_transcript': 'provided',
        'declaration_confirmed': True,
        'signature': 'Majid Khan',
        'signed_on': '2026-08-15',
    }

    def submit(payload):
        return student.post('/api/applications/',
                            json={'type': 'academic_scholarship', 'answers': payload})

    refused = submit({**answers, 'gpa_achieved': 'A minus'})
    check('a grade that is not a number is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'gpa_achieved': '160'})
    check('a grade over a hundred is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({k: v for k, v in answers.items() if k != 'doc_transcript'})
    check('a claim with no transcript is refused',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    refused = submit({**answers, 'declaration_confirmed': False})
    check('a declaration explicitly refused is not filed',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')

    print('\nTranscript')
    upload = student.post('/api/documents/',
                          files={'file': ('transcript.png', io.BytesIO(PNG), 'image/png')},
                          data={'field_key': 'doc_transcript'})
    if check('the transcript uploads', upload.status_code in (200, 201),
             f'{upload.status_code} {upload.text[:200]}'):
        answers['doc_transcript'] = upload.json()['reference']

    print('\nStudent portal — filing it')
    created = submit(answers)
    if not check('the claim is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:400]}'):
        return 1
    claim = created.json()
    claim_id = claim['id']
    print(f'        application {claim_id}')
    check('the grade is stored as a number, not as the text that was typed',
          str(claim['answers'].get('gpa_achieved')).rstrip('0').rstrip('.') == '85',
          repr(claim['answers'].get('gpa_achieved')))
    check('the transcript is a reference to a stored file',
          str(claim['answers'].get('doc_transcript', '')).startswith('document:'),
          repr(claim['answers'].get('doc_transcript')))

    print('\nStaff queue — the worker')
    detail = worker.get(f'/api/applications/{claim_id}/')
    if check('a reviewer can open it', detail.status_code == 200,
             f'{detail.status_code} {detail.text[:200]}'):
        seen = detail.json()['answers']
        check('and sees the grade the award depends on',
              seen.get('gpa_achieved') is not None)
        check('and where the transcript is coming from',
              seen.get('transcripts_status') == 'uploading_now',
              repr(seen.get('transcripts_status')))

    reviewed = worker.post(f'/api/applications/{claim_id}/transition/',
                           json={'action': 'reviewed'})
    check('a worker can take it under review', reviewed.status_code == 200,
          f'{reviewed.status_code} {reviewed.text[:300]}')
    forwarded = worker.post(f'/api/applications/{claim_id}/transition/',
                            json={'action': 'forwarded'})
    check('and forward it without an enrolment confirmation it never needed',
          forwarded.status_code == 200, f'{forwarded.status_code} {forwarded.text[:300]}')
    check('a worker cannot price it',
          worker.post(f'/api/applications/{claim_id}/price/').status_code == 403)

    print('\nAdmin portal — the bands are policy, and the policy is read')
    rates = admin.get('/api/policy/rates/')
    if not check('an administrator can read the rates', rates.status_code == 200,
                 f'{rates.status_code} {rates.text[:200]}'):
        return 1
    scholarship = {setting['key']: setting
                   for group in rates.json() if group['section'] == 'academic_scholarship'
                   for setting in group['settings']}
    check('both achievement thresholds are published as editable rates',
          {'high_threshold_percent', 'mid_threshold_percent'} <= set(scholarship),
          str(sorted(scholarship)))
    check('and both award amounts with them',
          {'high_achievement_award', 'mid_achievement_award'} <= set(scholarship),
          str(sorted(scholarship)))

    high = scholarship.get('high_threshold_percent')
    top = scholarship.get('high_achievement_award')
    mid = scholarship.get('mid_achievement_award')
    if high and top and mid:
        was = high['value']
        print(f'        top band begins at {was}%')

        # Price it once at the published threshold, then move the threshold and
        # price it again. This is the check that would have failed before: the
        # rate saved, the history recorded it, and the engine ignored it.
        director.post(f'/api/applications/{claim_id}/transition/',
                      json={'action': 'approved'})
        first = director.post(f'/api/applications/{claim_id}/price/')
        if check('the director can price it', first.status_code == 201,
                 f'{first.status_code} {first.text[:300]}'):
            check('at the top band, for a grade above the threshold',
                  Decimal(str(first.json()['total'])) == Decimal(str(top['value'])),
                  f'{first.json()["total"]} against a top band of {top["value"]}')

        raised = admin.patch(f'/api/policy/rates/{high["id"]}/', json={'value': '90'})
        check('an administrator can raise the threshold above the grade',
              raised.status_code == 200, f'{raised.status_code} {raised.text[:200]}')

        again = director.post(f'/api/applications/{claim_id}/price/')
        if check('and the claim can be priced again', again.status_code == 201,
                 f'{again.status_code} {again.text[:300]}'):
            check('at the middle band now — the threshold the office set is the '
                  'one that is paid',
                  Decimal(str(again.json()['total'])) == Decimal(str(mid['value'])),
                  f'{again.json()["total"]} against a middle band of {mid["value"]} '
                  f'— the threshold moved and the award did not.\n'
                  '          The published rule set stores its effect as JSON. '
                  'Editing seed_rules.py changes what a *new* set contains and '
                  'leaves the one in force alone, so a database seeded before '
                  'the thresholds became rate keys still carries the literals. '
                  'Publish a new version: manage.py seed_rules --publish')

        restored = admin.patch(f'/api/policy/rates/{high["id"]}/',
                               json={'value': str(was)})
        check('and the threshold can be put back', restored.status_code == 200,
              f'{restored.status_code} {restored.text[:200]}')

    print('\nAcross the portals')
    check('a student cannot price their own claim',
          student.post(f'/api/applications/{claim_id}/price/').status_code == 403)
    check('a student cannot change an achievement threshold',
          student.patch(f'/api/policy/rates/{high["id"]}/',
                        json={'value': '1'}).status_code == 403 if high else True)
    check('nor can the director who decides the award',
          director.patch(f'/api/policy/rates/{high["id"]}/',
                         json={'value': '1'}).status_code == 403 if high else True)
    other = Session(base)
    if other.login('student2@dgg.test'):
        check('another student cannot read the claim',
              other.get(f'/api/applications/{claim_id}/').status_code in (403, 404))

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
