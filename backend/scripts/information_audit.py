"""The request-for-information loop, over HTTP, as the three people live it.

A reviewer asks for something in their own words; the student is told, opens
the application, changes an answer, replaces a document, and sends it back; the
office opens what was attached.

Driven end to end because each half was fine on its own and the join was not:
the note was recorded and unreadable, the application could not be edited by
anybody, and a document could be uploaded and never opened again.

    python manage.py runserver 127.0.0.1:8000
    python scripts/information_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import io
import sys

import requests

PASSWORD = 'DemoPass123!'
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

checks = 0
failures: list[str] = []


def check(description, condition, detail=''):
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)
    return bool(condition)


class Session:
    def __init__(self, base):
        self.base, self.http = base.rstrip('/'), requests.Session()

    def login(self, email):
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': PASSWORD})
        token = response.json().get('access') if response.status_code == 200 else None
        if token:
            self.http.headers['Authorization'] = f'Bearer {token}'
        return bool(token)

    def get(self, path, **kw):
        return self.http.get(f'{self.base}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{self.base}{path}', **kw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    base = parser.parse_args().base.rstrip('/')

    student, worker, director, other = (Session(base) for _ in range(4))
    signed_in = all([
        student.login('student@dgg.test'),
        worker.login('worker@dgg.test'),
        director.login('director@dgg.test'),
        other.login('student2@dgg.test'),
    ])
    print('\nSigning in')
    check('student, worker, director and a second student can sign in', signed_in,
          'run: python manage.py seed_demo')
    if not signed_in:
        return 1

    print('\nThe student files an appeal')
    answers = {
        'full_name': 'Majid Khan', 'student_number': 'A-1',
        'institution_name': 'Aurora College', 'semester': 'fall',
        'academic_year': '2026-2027',
        'appeal_reason': 'The course load was recorded wrongly.',
        'declaration_confirmed': True, 'signature': 'Majid Khan',
        'signed_on': '2026-08-15',
    }
    created = student.post('/api/applications/',
                           json={'type': 'appeal', 'answers': answers})
    if not check('it is filed', created.status_code == 201,
                 f'{created.status_code} {created.text[:300]}'):
        return 1
    app_id = created.json()['id']
    print(f'        application {app_id}')
    check('and is not editable while the office has not asked for anything',
          created.json()['can_revise'] is False)

    print('\nThe reviewer asks for more, in their own words')
    note = 'Please attach the transcript that shows your full-time registration.'
    asked = worker.post(f'/api/applications/{app_id}/transition/',
                        json={'action': 'info_requested', 'note': note})
    check('the request is recorded', asked.status_code == 200,
          f'{asked.status_code} {asked.text[:300]}')

    seen = student.get(f'/api/applications/{app_id}/')
    if check('the student can open it', seen.status_code == 200):
        body = seen.json()
        asked_for = body.get('information_requested') or {}
        check('and is shown exactly what was asked', asked_for.get('note') == note,
              repr(asked_for.get('note')))
        check('and who asked', bool(asked_for.get('asked_by')))
        check('and the application is now editable', body['can_revise'] is True)

    print('\nThe notice that takes them there')
    notices = student.get('/api/notifications/')
    if check('notifications are readable', notices.status_code == 200):
        rows = notices.json().get('results', [])
        mine = next((row for row in rows
                     if row.get('link') == f'/applications/{app_id}'), None)
        check('a notice links straight to the application', mine is not None,
              f'no notice links to /applications/{app_id}')
        if mine:
            check('and it carries what was asked',
                  note[:20] in (mine['message'] or ''), repr(mine['message'])[:150])
            check('and is flagged as something to act on',
                  mine['kind'] == 'action_needed', repr(mine['kind']))

    print('\nThe student answers: a new document and a corrected answer')
    upload = student.post('/api/documents/',
                          files={'file': ('transcript.png', io.BytesIO(PNG), 'image/png')},
                          data={'field_key': 'doc_supporting', 'application': app_id})
    reference = ''
    if check('a document can be attached to their own application',
             upload.status_code in (200, 201),
             f'{upload.status_code} {upload.text[:200]}'):
        reference = upload.json()['reference']

    revised = student.post(f'/api/applications/{app_id}/revise/', json={
        'answers': {
            **answers,
            'appeal_reason': 'I was registered full-time for the whole term.',
            'doc_supporting': [reference] if reference else [],
        },
    })
    if check('the revision is accepted', revised.status_code == 200,
             f'{revised.status_code} {revised.text[:300]}'):
        body = revised.json()
        check('the corrected answer is stored',
              'full-time for the whole term' in str(body['answers']['appeal_reason']))
        check('the document is named in the answers',
              body['answers'].get('doc_supporting') == ([reference] if reference else None),
              repr(body['answers'].get('doc_supporting')))
        check('and it has gone back to the office',
              body['status'] == 'under_review', body['status'])
        check('and is no longer editable', body['can_revise'] is False)

    check('a second attempt to revise is refused now',
          student.post(f'/api/applications/{app_id}/revise/',
                       json={'answers': answers}).status_code == 409)

    print('\nWhat the office can open')
    detail = worker.get(f'/api/applications/{app_id}/')
    doc_url = ''
    if check('a reviewer can open the application', detail.status_code == 200):
        documents = detail.json().get('documents', [])
        check('and it lists the attached document', len(documents) >= 1, str(documents))
        if documents:
            doc_url = documents[0]['url']
            check('with the name it was uploaded under',
                  documents[0]['original_name'] == 'transcript.png',
                  repr(documents[0]['original_name']))

    if doc_url:
        for name, who in (('reviewer', worker), ('director', director)):
            opened = who.get(doc_url)
            check(f'the {name} can open the document itself',
                  opened.status_code == 200, str(opened.status_code))
        check('so can the student it belongs to',
              student.get(doc_url).status_code == 200)
        refused = other.get(doc_url)
        check('another student cannot, and is not told it exists',
              refused.status_code == 404, str(refused.status_code))
        anonymous = requests.get(f'{base}{doc_url}', timeout=10)
        check('nor can a visitor with no session',
              anonymous.status_code in (401, 403), str(anonymous.status_code))

    print('\nWhat the student still cannot do')
    check('approve their own application',
          student.post(f'/api/applications/{app_id}/transition/',
                       json={'action': 'approved'}).status_code == 403)
    check('price it',
          student.post(f'/api/applications/{app_id}/price/').status_code == 403)
    check('revise somebody else\'s',
          other.post(f'/api/applications/{app_id}/revise/',
                     json={'answers': answers}).status_code in (403, 404))

    print(f'\n{checks - len(failures)}/{checks} checks passed')
    if failures:
        print('\nFailed:')
        for description in failures:
            print(f'  - {description}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
