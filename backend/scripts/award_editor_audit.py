"""Editing a funding breakdown that already exists, over real HTTP.

The reported symptom: open the breakdown editor and the auto-priced lines are
not there, only an empty row; add one, save, and the rest disappear.

This drives the server directly, to separate two questions the screen conflates:
does the *server* allow an existing award to be corrected, and does saving one
line take the others with it.

    python manage.py runserver 127.0.0.1:8000
    python award_editor_audit.py [--base http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import io as _io
import sys
import time

import requests

PASSWORD = 'DemoPass123!'
STAMP = time.strftime('%m%d%H%M%S')
BASE = 'http://127.0.0.1:8000'

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

ELIGIBLE = {
    'indian_act_registered': 'yes', 'deline_beneficiary': 'yes',
    'receives_sfa': 'no', 'lives_in_nwt': 'yes',
    'accredited_institution': 'yes', 'programme_twelve_weeks': 'yes',
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
                   files={'file': (f'{field_key}.png', _io.BytesIO(PNG), 'image/png')},
                   data={'field_key': field_key})
    return r.json()['reference'] if r.status_code in (200, 201) else ''


def answers_for(actor, slug):
    schema = requests.get(f'{BASE}/api/schemas/{slug}/').json()
    answers = {}
    for f in schema['fields']:
        key, kind = f['key'], (f.get('type') or '').lower()
        if f.get('computed') or not f.get('required'):
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
            answers[key] = 'Award Audit'
        elif kind == 'table':
            row = {}
            for col in f.get('columns') or ():
                ck = (col.get('type') or '').lower()
                row[col['key']] = ('250.00' if ck == 'money'
                                   else True if ck == 'boolean'
                                   else 'Recorded for the audit')
            answers[key] = [row]
        elif kind in ('file', 'files'):
            ref = upload(actor, key)
            answers[key] = [ref] if kind == 'files' else ref
        else:
            answers[key] = 'Recorded for the audit'
    return answers


def lines_of(admin, app_id):
    body = admin.get(f'/api/applications/{app_id}/').json()
    dec = body.get('decision') or {}
    return body.get('status'), (dec.get('lines') or []), dec.get('total')


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=BASE)
    BASE = ap.parse_args().base.rstrip('/')

    section('Setting up an application with an auto-priced award')
    email = f'awardaudit.{STAMP}@example.com'
    made = requests.post(f'{BASE}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Award', 'last_name': f'Audit{STAMP}',
        'phone': '867-555-0101', 'eligibility': dict(ELIGIBLE),
    })
    if not check('a student registers', made.status_code == 201,
                 f'{made.status_code} {made.text[:200]}'):
        return 1
    student = Actor(email)
    admin = Actor('admin@dgg.test')
    if not check('the office signs in', admin.signed_in):
        return 1

    filed = student.post('/api/applications/',
                         json={'type': 'travel', 'answers': answers_for(student, 'travel')})
    if not check('a travel claim is filed', filed.status_code == 201,
                 f'{filed.status_code} {filed.text[:300]}'):
        return 1
    app_id = filed.json()['id']

    admin.post(f'/api/applications/{app_id}/transition/', json={'action': 'reviewed'})
    priced = admin.post(f'/api/applications/{app_id}/price/')
    check('the rules price it', priced.status_code in (200, 201),
          f'{priced.status_code} {priced.text[:300]}')

    status_now, auto_lines, auto_total = lines_of(admin, app_id)
    check('it now carries auto-generated award lines', len(auto_lines) >= 1,
          f'status={status_now} lines={len(auto_lines)}')
    for ln in auto_lines:
        print(f'        auto line: {ln["category"]:<10} {ln["amount"]:>10}  rule={ln["rule_code"]}')

    section('What the SERVER allows, at each status')
    one_line = [{'category': auto_lines[0]['category'],
                 'description': 'Agreed at the counter',
                 'amount': '111.00'}]

    still = admin.post(f'/api/applications/{app_id}/award/',
                       json={'lines': one_line, 'note': 'audit: while under review'})
    check('an under-review award can be set by hand', still.status_code == 201,
          f'{still.status_code} {still.text[:200]}')

    st, after_manual, _ = lines_of(admin, app_id)
    check('DATA LOSS: saving one line replaced every auto-generated line',
          len(after_manual) == 1,
          f'{len(after_manual)} lines remain (was {len(auto_lines)})')
    check('  and the surviving line is the hand-set one',
          after_manual and after_manual[0]['amount'] == '111.00',
          str(after_manual)[:200])

    # Put the rules' figures back, then approve, and try again.
    admin.post(f'/api/applications/{app_id}/price/')
    _, restored, _ = lines_of(admin, app_id)
    check('re-pricing restores the rules\' lines', len(restored) == len(auto_lines),
          f'{len(restored)} vs {len(auto_lines)}')

    approved = admin.post(f'/api/applications/{app_id}/transition/',
                          json={'action': 'approved'})
    check('the office approves it', approved.status_code in (200, 201),
          f'{approved.status_code} {approved.text[:300]}')
    st, _, _ = lines_of(admin, app_id)
    check('  and the status really is approved', st == 'approved', str(st))

    on_approved = admin.post(f'/api/applications/{app_id}/award/',
                             json={'lines': one_line, 'note': 'audit: while approved'})
    check('THE POINT: the SERVER allows an APPROVED award to be corrected',
          on_approved.status_code == 201,
          f'{on_approved.status_code} {on_approved.text[:300]}')

    section('What the SERVER refuses')
    declined_app = student.post('/api/applications/',
                                json={'type': 'travel', 'answers': answers_for(student, 'travel')})
    if declined_app.status_code == 201:
        d_id = declined_app.json()['id']
        admin.post(f'/api/applications/{d_id}/transition/', json={'action': 'reviewed'})
        admin.post(f'/api/applications/{d_id}/transition/', json={'action': 'declined'})
        refused = admin.post(f'/api/applications/{d_id}/award/', json={'lines': one_line})
        check('a declined application is refused', refused.status_code == 409,
              f'{refused.status_code} {refused.text[:200]}')

    worker = Actor('worker@dgg.test')
    if worker.signed_in:
        not_admin = worker.post(f'/api/applications/{app_id}/award/',
                                json={'lines': one_line})
        check('a support worker is refused', not_admin.status_code == 403,
              f'{not_admin.status_code} {not_admin.text[:200]}')

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nfailed:')
        for f in failures:
            print(f'  - {f}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
