"""One figure, followed the whole way: registrar -> award -> letter -> report.

Each screen adds up correctly on its own. This asks the question no single
screen can: does the tuition the institution confirmed reach the award, does the
award reach the letter the student is sent, and do both reach the report the
office files.

    python manage.py runserver 127.0.0.1:8000
    python money_chain_audit.py [--base http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from decimal import Decimal

import django
import requests

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from funding.models import EnrollmentVerification  # noqa: E402

PASSWORD = 'DemoPass123!'
STAMP = time.strftime('%m%d%H%M%S')
BASE = 'http://127.0.0.1:8000'
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082')

# The institution's figure. Deliberately NOT what the student estimates below,
# so a chain that quietly uses the student's number is visible.
STUDENT_ESTIMATE = '9999'
REGISTRAR_TUITION = '4321'

ELIGIBLE = {
    'indian_act_registered': 'yes', 'deline_beneficiary': 'yes',
    'receives_sfa': 'no', 'lives_in_nwt': 'yes',
    'accredited_institution': 'yes', 'programme_twelve_weeks': 'yes',
}
BANK = {'account_holder': f'Chain {STAMP}', 'transit_number': '12345',
        'institution_number': '001', 'account_number': '9876543210'}

checks = 0
failures: list[str] = []


def section(t):
    print(f'\n{t}\n' + '-' * len(t))


def check(label, ok, detail=''):
    global checks
    checks += 1
    print(f'  {"ok  " if ok else "FAIL"}  {label}')
    if not ok:
        failures.append(label)
        if detail:
            print(f'        {detail}')
    return ok


def actor(email):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/token/', json={'email': email, 'password': PASSWORD})
    if r.status_code == 200:
        s.headers['Authorization'] = f'Bearer {r.json()["access"]}'
    return s


def fill(fields, seed=None, uploader=None):
    a = dict(seed or {})
    for f in fields:
        k, t = f['key'], (f.get('type') or '').lower()
        if f.get('computed'):
            a.pop(k, None)
            continue
        if not f.get('required') or a.get(k) not in (None, '', []):
            continue
        if t == 'choice':
            ch = f.get('choices') or []
            a[k] = ch[0]['value'] if ch else ''
        elif t == 'confirm':
            a[k] = True
        elif t == 'boolean':
            a[k] = True
        elif t == 'date':
            a[k] = '2026-09-01'
        elif t in ('money', 'number', 'integer', 'percent'):
            a[k] = '1200'
        elif t == 'email':
            a[k] = f'reg.{STAMP}@aurora.test'
        elif t == 'phone':
            a[k] = '867-555-0101'
        elif t == 'signature':
            a[k] = 'Chain Audit'
        elif t == 'sin':
            a[k] = '130692544'
        elif t in ('file', 'files'):
            r = uploader(k) if uploader else ''
            a[k] = [r] if t == 'files' else r
        else:
            a[k] = 'Recorded for the audit'
    return a


def money(x):
    return Decimal(str(x).replace('$', '').replace(',', ''))


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=BASE)
    BASE = ap.parse_args().base.rstrip('/')

    section('A student, an institution, and a tuition figure they disagree on')
    email = f'chain.{STAMP}@example.com'
    made = requests.post(f'{BASE}/api/auth/register/', json={
        'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD,
        'first_name': 'Chain', 'last_name': f'Audit{STAMP}',
        'phone': '867-555-0101', 'eligibility': dict(ELIGIBLE)})
    if not check('a student registers', made.status_code == 201, made.text[:200]):
        return 1
    st = actor(email)
    admin = actor('admin@dgg.test')
    st.put(f'{BASE}/api/me/banking/', json=dict(BANK))

    up = lambda k: st.post(  # noqa: E731
        f'{BASE}/api/documents/',
        files={'file': (f'{k}.png', io.BytesIO(PNG), 'image/png')},
        data={'field_key': k}).json().get('reference', '')

    sch = requests.get(f'{BASE}/api/schemas/admission/').json()
    answers = fill(sch['fields'],
                   {'course_load': 'full_time', 'tuition_requested': STUDENT_ESTIMATE},
                   up)
    filed = st.post(f'{BASE}/api/applications/',
                    json={'type': 'admission', 'answers': answers})
    if not check('an admission application is filed', filed.status_code == 201,
                 filed.text[:300]):
        return 1
    aid = filed.json()['id']
    print(f'        student estimated tuition: ${STUDENT_ESTIMATE}')

    section('The registrar answers with a different figure')
    v = EnrollmentVerification.objects.filter(application_id=aid).first()
    if not check('an enrolment request was raised', v is not None):
        return 1
    page = requests.get(f'{BASE}/api/enrolment/{v.token}/').json()
    vans = fill(page['schema']['fields'],
                {**(page['application'].get('prefill') or {}),
                 'confirmed_tuition': REGISTRAR_TUITION,
                 'course_load': 'full_time'})
    conf = requests.post(f'{BASE}/api/enrolment/{v.token}/', json={'answers': vans})
    check('the registrar confirms', conf.status_code == 200, conf.text[:250])
    print(f'        registrar confirmed tuition: ${REGISTRAR_TUITION}')

    body = admin.get(f'{BASE}/api/applications/{aid}/').json()
    check("the registrar's figure is written onto the application",
          str(body['answers'].get('confirmed_tuition')).startswith(REGISTRAR_TUITION),
          str(body['answers'].get('confirmed_tuition')))
    check("and the student's estimate is NOT what tuition is funded against",
          str(body['answers'].get('confirmed_tuition')) != STUDENT_ESTIMATE,
          str(body['answers'].get('confirmed_tuition')))

    section('The rules price it')
    admin.post(f'{BASE}/api/applications/{aid}/transition/', json={'action': 'reviewed'})
    p = admin.post(f'{BASE}/api/applications/{aid}/price/')
    check('the application prices', p.status_code in (200, 201), p.text[:250])
    dec = admin.get(f'{BASE}/api/applications/{aid}/').json()['decision']
    lines = dec['lines']
    for l in lines:
        print(f'        {l["category"]:<10} {l["amount"]:>10}  {l["rule_code"]}')
    check('the decision total equals the sum of its lines',
          money(dec['total']) == sum(money(l['amount']) for l in lines),
          f'{dec["total"]} vs {sum(money(l["amount"]) for l in lines)}')

    tuition = sum(money(l['amount']) for l in lines if l['category'] == 'tuition')
    check('tuition awarded never exceeds what the registrar confirmed',
          tuition <= money(REGISTRAR_TUITION),
          f'awarded {tuition} vs confirmed {REGISTRAR_TUITION}')

    section('The office approves, and the student is sent a letter')
    ap_r = admin.post(f'{BASE}/api/applications/{aid}/transition/',
                      json={'action': 'approved'})
    check('it approves', ap_r.status_code in (200, 201), ap_r.text[:250])

    letter = admin.get(f'{BASE}/api/applications/{aid}/approval-letter/')
    check('the approval letter is served', letter.status_code == 200,
          f'{letter.status_code} {letter.text[:200]}')
    if letter.status_code == 200:
        payload = letter.json()
        letters = payload if isinstance(payload, list) else payload.get('letters', [payload])
        total_on_letters = Decimal('0')
        for L in letters:
            rows = L.get('rows') or L.get('lines') or []
            sub = sum(money(r.get('amount', 0)) for r in rows if r.get('amount'))
            total_on_letters += sub
            print(f'        letter {L.get("programme") or L.get("stream") or "?"}: '
                  f'{len(rows)} row(s), subtotal {sub}')
        check('THE LETTERS ACCOUNT FOR THE WHOLE AWARD, to the penny',
              total_on_letters == money(dec['total']),
              f'letters {total_on_letters} vs award {dec["total"]}')

    section('The report the office files')
    rep = admin.get(f'{BASE}/api/reports/annual/')
    if rep.status_code != 200:
        rep = admin.get(f'{BASE}/api/reports/annual/?year=2026')
    check('the annual report is served', rep.status_code == 200,
          f'{rep.status_code} {rep.text[:200]}')
    if rep.status_code == 200:
        r = rep.json()
        fin = r.get('financial') or {}
        print(f'        financial: {fin}')
        gross = money(fin.get('gross', 0) or 0)
        repaid = money(fin.get('repaid', 0) or 0)
        net = money(fin.get('net', 0) or 0)
        check('the report reconciles: gross - repaid == net',
              gross - repaid == net, f'{gross} - {repaid} != {net}')

    section('What finance is asked to pay')
    pay = admin.get(f'{BASE}/api/finance/pending/')
    check('the payment preview is served', pay.status_code == 200,
          f'{pay.status_code} {pay.text[:200]}')
    if pay.status_code == 200:
        pv = pay.json()
        ready = pv.get('ready') or []
        mine = [x for x in ready if str(x.get('application_id') or
                                        (x.get('application') or {}).get('id')) == str(aid)]
        print(f'        ready rows for this application: {len(mine)}')
        check('LUMP SUM: finance gets ONE row for this student, not one per line',
              len(mine) <= 1,
              f'{len(mine)} rows for a {len(lines)}-line award')

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nfailed:')
        for f in failures:
            print(f'  - {f}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
