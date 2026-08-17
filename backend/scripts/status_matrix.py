"""Every office action against an application in every status, enumerated.

    python manage.py runserver 127.0.0.1:8000
    python scripts/status_matrix.py

Not a pass/fail audit — a probe. It builds one application in each status and
calls every endpoint the office has against each, printing the status code. The
point is to *read* the matrix and notice a cell that should not be what it is,
rather than to guess in advance which combination might be wrong.

Three real defects came out of one reading of it, all of the same shape — an
action that keeps working after the application it belongs to has moved on:

  * price/ on an application whose award had already been dispatched. Re-pricing
    writes fresh PENDING lines, and the payment run offers them again: 4,850
    would have gone out a second time. A passing test asserted this was correct.
  * award/ and price/ on a declined application — a decision, with lines,
    against a refusal.
  * request-enrolment/ on a decided application, which sends a real email to a
    real institution about something already settled.

Kept because the reading is the value, and it is worth repeating whenever the
workflow gains a status or the office gains an action.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
import django
django.setup()

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests

B = 'http://127.0.0.1:8000'
PW = 'DemoPass123!'
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082')


def tok(email):
    return requests.post(f'{B}/api/auth/token/',
                         json={'email': email, 'password': PW}).json()['access']


H = {r: {'Authorization': f'Bearer {tok(f"{r}@dgg.test")}'}
     for r in ('admin', 'director', 'worker', 'finance', 'student')}

SCHEMA = requests.get(f'{B}/api/schemas/admission/').json()
FILL = {'text': 'Aurora College', 'long_text': 'x', 'email': 's@example.com',
        'phone': '8675550143', 'date': '2026-09-01', 'money': '9000',
        'integer': '1', 'percent': '85', 'boolean': 'false', 'confirm': 'true',
        'signature': 'Sara Student', 'sin': '199999996'}


def doc():
    r = requests.post(f'{B}/api/documents/', files={'file': ('t.png', PNG, 'image/png')})
    b = r.json()
    return b.get('reference') or f"document:{b.get('id')}"


def answers():
    a = {}
    for f in SCHEMA['fields']:
        if f['computed'] or not f['required']:
            continue
        t = f['type']
        a[f['key']] = (f['choices'][0]['value'] if t == 'choice'
                       else [doc()] if t == 'files'
                       else doc() if t == 'file'
                       else FILL.get(t, 'x'))
    a.update({'course_load': 'full_time', 'semester': 'fall',
              'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
              'program_start': '2026-09-01', 'program_end': '2030-06-30',
              'tuition_requested': '9000', 'receives_sfa': 'false',
              'has_dependents': 'false', 'institution_name': 'Aurora College',
              'registrar_email': 'reg@example.com',
              'account_holder': 'Sara Student', 'transit_number': '12345',
              'institution_number': '001', 'account_number': '9876543210'})
    return a


def confirm(app_id):
    from notifications.models import OutboundEmail
    import re
    from funding.models import EnrollmentVerification
    v = EnrollmentVerification.objects.filter(application_id=app_id).first()
    if not v:
        return
    vs = requests.get(f'{B}/api/schemas/enrollment_verification/').json()
    ans = {}
    for f in vs['fields']:
        if f['computed'] or not f['required']:
            continue
        t = f['type']
        ans[f['key']] = (f['choices'][0]['value'] if t == 'choice'
                         else FILL.get(t, 'x'))
    ans.update({'is_enrolled': 'true', 'course_load': 'full_time',
                'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
                'confirmed_tuition': '9000', 'registrar_name': 'R. Registrar',
                'registrar_title': 'Registrar', 'completed_on': '2026-08-17',
                'institution_name': 'Aurora College'})
    requests.post(f'{B}/api/enrolment/{v.token}/', json={'answers': ans})


def build(target):
    """An application sitting in `target`."""
    r = requests.post(f'{B}/api/applications/',
                      json={'type': 'admission', 'answers': answers()},
                      headers=H['student'])
    app = r.json()['id']
    A = H['admin']
    if target == 'submitted':
        return app
    if target == 'info_requested':
        requests.post(f'{B}/api/applications/{app}/transition/',
                      json={'action': 'info_requested', 'note': 'more please'}, headers=A)
        return app
    requests.post(f'{B}/api/applications/{app}/transition/',
                  json={'action': 'reviewed'}, headers=A)
    if target == 'under_review':
        return app
    confirm(app)
    if target == 'awaiting_decision':
        requests.post(f'{B}/api/applications/{app}/transition/',
                      json={'action': 'forwarded'}, headers=A)
        return app
    if target == 'declined':
        requests.post(f'{B}/api/applications/{app}/transition/',
                      json={'action': 'declined', 'note': 'no'}, headers=A)
        return app
    requests.post(f'{B}/api/applications/{app}/price/', headers=A)
    requests.post(f'{B}/api/applications/{app}/transition/',
                  json={'action': 'approved'}, headers=A)
    if target == 'approved':
        return app
    if target == 'sent_to_finance':
        requests.post(f'{B}/api/finance/dispatch/', headers=H['finance'])
        return app
    return app


PROBES = [
    ('price',        lambda a: requests.post(f'{B}/api/applications/{a}/price/', headers=H['admin'])),
    ('award',        lambda a: requests.post(f'{B}/api/applications/{a}/award/', headers=H['admin'],
                                             json={'lines': [{'category': 'tuition', 'description': 'x', 'amount': '1'}]})),
    ('amend',        lambda a: requests.post(f'{B}/api/applications/{a}/amend/', headers=H['admin'],
                                             json={'answers': answers()})),
    ('req-enrol',    lambda a: requests.post(f'{B}/api/applications/{a}/request-enrolment/', headers=H['admin'],
                                             json={'registrar_email': 'probe@example.com'})),
    ('revise(stu)',  lambda a: requests.post(f'{B}/api/applications/{a}/revise/', headers=H['student'],
                                             json={'answers': answers()})),
    ('attach',       lambda a: requests.post(f'{B}/api/applications/{a}/attach/', headers=H['admin'],
                                             json={'student_id': 9999})),
    ('upload(stu)',  lambda a: requests.post(f'{B}/api/documents/', headers=H['student'],
                                             data={'application': a, 'field_key': 'doc_transcript'},
                                             files={'file': ('t.png', PNG, 'image/png')})),
]

STATUSES = ['submitted', 'under_review', 'info_requested', 'awaiting_decision',
            'approved', 'declined', 'sent_to_finance']

print(f'{"status":<20}' + ''.join(f'{name:<13}' for name, _ in PROBES))
print('-' * (20 + 13 * len(PROBES)))
for st in STATUSES:
    app = build(st)
    actual = requests.get(f'{B}/api/applications/{app}/', headers=H['admin']).json()['status']
    row = f'{actual:<20}'
    for name, call in PROBES:
        try:
            row += f'{call(app).status_code:<13}'
        except Exception as exc:
            row += f'{type(exc).__name__:<13}'
    print(row)
