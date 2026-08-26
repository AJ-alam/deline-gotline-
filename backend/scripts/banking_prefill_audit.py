"""Does the payment section a student fills in on their profile reach a form?

The reported symptom: save banking on the profile, open an application, and the
Payment section is empty again.

    python manage.py runserver 127.0.0.1:8000
    python banking_prefill_audit.py [--base http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time

import django
import requests

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from accounts.models import BankAccount, User  # noqa: E402

PASSWORD = 'DemoPass123!'
STAMP = time.strftime('%m%d%H%M%S')
TEST_SIN = '130692544'
BASE = 'http://127.0.0.1:8000'

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

BANKING_KEYS = ('account_holder', 'transit_number',
                'institution_number', 'account_number')

ELIGIBLE = {
    'indian_act_registered': 'yes', 'deline_beneficiary': 'yes',
    'receives_sfa': 'no', 'lives_in_nwt': 'yes',
    'accredited_institution': 'yes', 'programme_twelve_weeks': 'yes',
}

PROFILE = {
    'institution_name': 'Aurora College', 'institution_location': 'Yellowknife, NT',
    'program': 'Bachelor of Nursing', 'credential_level': 'degree',
    'learning_style': 'in_person', 'course_load': 'full_time',
    'student_number': f'B-{STAMP}', 'program_start': '2026-09-01',
    'program_end': '2030-06-30', 'program_year': 1, 'program_length_years': 4,
    'registrar_email': f'registrar.{STAMP}@aurora.test',
    'institution_phone': '867-555-0177', 'dependent_count': 0,
}

BANK = {
    'account_holder': f'Bank Audit {STAMP}',
    'transit_number': '12345',
    'institution_number': '001',
    'account_number': '9876543210',
}

checks = 0
failures: list[str] = []


def section(title: str) -> None:
    print(f'\n{title}\n' + '-' * len(title))


def check(label: str, ok: bool, detail: str = '') -> bool:
    global checks
    checks += 1
    print(f'  {"ok  " if ok else "FAIL"}  {label}')
    if not ok:
        failures.append(label)
        if detail:
            print(f'        {detail}')
    return ok


class Actor:
    def __init__(self, email: str):
        self.http = requests.Session()
        r = self.http.post(f'{BASE}/api/auth/token/',
                           json={'email': email, 'password': PASSWORD})
        self.signed_in = r.status_code == 200 and 'access' in r.json()
        if self.signed_in:
            self.http.headers['Authorization'] = f'Bearer {r.json()["access"]}'

    def get(self, p, **kw):
        return self.http.get(f'{BASE}{p}', **kw)

    def post(self, p, **kw):
        return self.http.post(f'{BASE}{p}', **kw)

    def put(self, p, **kw):
        return self.http.put(f'{BASE}{p}', **kw)


def upload(actor, field_key):
    r = actor.post('/api/documents/',
                   files={'file': (f'{field_key}.png', io.BytesIO(PNG), 'image/png')},
                   data={'field_key': field_key})
    return r.json()['reference'] if r.status_code in (200, 201) else ''


def answers_for(actor, slug, prefill=None, skip=()):
    """Fill a form the way a browser would: prefill first, then what is left."""
    schema = requests.get(f'{BASE}/api/schemas/{slug}/').json()
    answers = dict(prefill or {})
    for f in schema['fields']:
        key, kind = f['key'], (f.get('type') or '').lower()
        if f.get('computed'):
            answers.pop(key, None)
            continue
        if key in skip:
            answers.pop(key, None)
            continue
        if not f.get('required') or answers.get(key) not in (None, '', []):
            continue
        if kind == 'choice':
            ch = f.get('choices') or []
            answers[key] = ch[0]['value'] if ch else ''
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
            answers[key] = 'Bank Audit'
        elif kind == 'sin':
            answers[key] = TEST_SIN
        elif kind in ('file', 'files'):
            ref = upload(actor, key)
            answers[key] = [ref] if kind == 'files' else ref
        elif kind == 'table':
            row = {}
            for col in f.get('columns') or ():
                ckind = (col.get('type') or '').lower()
                if ckind == 'money':
                    row[col['key']] = '250.00'
                elif ckind == 'boolean':
                    row[col['key']] = True
                else:
                    row[col['key']] = 'Recorded for the audit'
            answers[key] = [row]
        else:
            answers[key] = 'Recorded for the audit'
    return answers


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=BASE)
    BASE = ap.parse_args().base.rstrip('/')

    section('A student who has filled in their profile')
    email = f'bankaudit.{STAMP}@example.com'
    made = requests.post(f'{BASE}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Bank', 'last_name': f'Audit{STAMP}',
        'phone': '867-555-0101', 'eligibility': dict(ELIGIBLE),
    })
    if not check('the student registers', made.status_code == 201,
                 f'{made.status_code} {made.text[:200]}'):
        return 1
    student = Actor(email)
    if not check('and signs in', student.signed_in):
        return 1

    saved_profile = student.put('/api/me/enrolment/', json=dict(PROFILE))
    check('their enrolment profile saves', saved_profile.status_code == 200,
          f'{saved_profile.status_code} {saved_profile.text[:200]}')

    saved_bank = student.put('/api/me/banking/', json=dict(BANK))
    check('their payment details save', saved_bank.status_code == 200,
          f'{saved_bank.status_code} {saved_bank.text[:200]}')
    check('and come back as a card, the way the screen shows them',
          (saved_bank.json().get('account') or {}).get('account_number') == '****3210',
          saved_bank.text[:200])

    person = User.objects.get(email__iexact=email)
    account = BankAccount.objects.filter(user=person, is_current=True).first()
    check('finance has an account on file for them, before any application',
          account is not None and account.account_number == '9876543210',
          str(account))

    section('What the next form opens with')
    pre = student.get('/api/form-prefill/admission/')
    check('the prefill endpoint answers', pre.status_code == 200,
          f'{pre.status_code} {pre.text[:200]}')
    prefill = (pre.json() or {}).get('answers', {}) if pre.status_code == 200 else {}

    check('it carries the institution from the profile',
          prefill.get('institution_name') == 'Aurora College',
          str(prefill)[:200])
    check('it carries the programme from the profile',
          prefill.get('program') == 'Bachelor of Nursing', str(prefill)[:200])

    # The three the server may hand back arrive filled in; the account number
    # never does, because it is written once and read only by the finance
    # export. A blank one is accepted at submission when an account is on file.
    for key in ('account_holder', 'transit_number', 'institution_number'):
        check(f'{key} arrives from the profile',
              prefill.get(key) not in (None, ''), repr(prefill.get(key)))
    check('the account number is never returned, even to its owner',
          prefill.get('account_number') in (None, ''),
          repr(prefill.get('account_number')))

    section('The student does not retype what the office already has')
    without = answers_for(student, 'admission', prefill, skip=BANKING_KEYS)
    filed = student.post('/api/applications/',
                         json={'type': 'admission', 'answers': without})
    check('a student with an account on file may leave the boxes blank',
          filed.status_code == 201, f'{filed.status_code} {filed.text[:300]}')

    # And the rule itself, from the other end: somebody with nothing on file
    # cannot file at all. This is the office's rule - an application cannot be
    # submitted without somewhere to pay it - and it is what keeps "no bank
    # account on file" off the payment run weeks later.
    other = f'nobank.{STAMP}@example.com'
    requests.post(f'{BASE}/api/auth/register/', json={
        'email': other, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'No', 'last_name': f'Bank{STAMP}',
        'phone': '867-555-0101', 'eligibility': dict(ELIGIBLE)})
    stranger = Actor(other)
    bare = answers_for(stranger, 'travel', skip=BANKING_KEYS)
    refused = stranger.post('/api/applications/',
                            json={'type': 'travel', 'answers': bare})
    check('a student with nothing on file cannot file without payment details',
          refused.status_code == 400, f'{refused.status_code} {refused.text[:200]}')
    named = [k for k in BANKING_KEYS if k in refused.text]
    check('  and all four boxes are named',
          sorted(named) == sorted(BANKING_KEYS), f'named: {named}')

    section('And typing a new account still replaces it')
    with_bank = answers_for(student, 'admission', {**prefill, **BANK})
    again = student.post('/api/applications/',
                         json={'type': 'admission', 'answers': with_bank})
    check('the identical application is accepted once banking is typed in',
          again.status_code == 201, f'{again.status_code} {again.text[:300]}')

    after = BankAccount.objects.filter(user=person, is_current=True).first()
    check('and it wrote the same digits that were already on file',
          after is not None and after.account_number == '9876543210', str(after))
    check('so the retyping changed nothing finance did not already have',
          BankAccount.objects.filter(user=person).count() >= 1,
          str(BankAccount.objects.filter(user=person).count()))

    section('An optional form, for contrast')
    pre_t = student.get('/api/form-prefill/travel/')
    pre_travel = (pre_t.json() or {}).get('answers', {}) if pre_t.status_code == 200 else {}
    check('travel pre-fills payment from the same account',
          pre_travel.get('account_holder') not in (None, ''),
          repr(pre_travel.get('account_holder')))
    travel = answers_for(student, 'travel', pre_travel, skip=BANKING_KEYS)
    t_filed = student.post('/api/applications/',
                           json={'type': 'travel', 'answers': travel})
    check('travel files too, on the same account already on file',
          t_filed.status_code == 201, f'{t_filed.status_code} {t_filed.text[:300]}')

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nfailed:')
        for f in failures:
            print(f'  - {f}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
