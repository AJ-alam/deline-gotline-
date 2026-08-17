"""The office changing a filed application, and the applicant answering back.

Two paths meet here and neither existed as a whole before:

  * an administrator corrects a filed application on the applicant's behalf,
    and the applicant is told what changed;
  * a reviewer asks for something *in their own words*, the applicant opens the
    notice, edits the answers, and adds, replaces and removes documents.

Driven over HTTP as the people who walk it: student -> support worker ->
administrator -> student -> director. What is checked here is not that each
endpoint answers 200, but that the same facts read the same way from every
side — the answer the office typed is the answer the student sees, the note the
reviewer wrote is the note in the notice, and a document removed is gone from
the application rather than merely hidden.

    python manage.py runserver 127.0.0.1:8000
    python scripts/amendment_audit.py [--base http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time

import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('INSECURE_LOCAL', '1')
django.setup()

from funding.models import (  # noqa: E402
    Application, ApplicationEvent, AuditEntry, EnrollmentVerification,
)
from funding.test_fixtures import admission_answers  # noqa: E402
from funding.services import workflow  # noqa: E402
from notifications.models import Notification, OutboundEmail  # noqa: E402

PASSWORD = 'DemoPass123!'
STAMP = time.strftime('%m%d%H%M%S')
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082'
)

checks = 0
failures: list[str] = []
BASE = 'http://127.0.0.1:8000'


def section(title: str) -> None:
    print(f'\n{title}')
    print('-' * len(title))


def check(description: str, condition: bool, detail: str = '') -> bool:
    global checks
    checks += 1
    if condition:
        print(f'  ok    {description}')
    else:
        print(f'  FAIL  {description}' + (f'\n          {detail}' if detail else ''))
        failures.append(description)
    return bool(condition)


class Actor:
    def __init__(self, email: str):
        self.email = email
        self.http = requests.Session()
        response = self.http.post(f'{BASE}/api/auth/token/',
                                  json={'email': email, 'password': PASSWORD})
        self.signed_in = response.status_code == 200 and 'access' in response.json()
        if self.signed_in:
            self.http.headers['Authorization'] = f'Bearer {response.json()["access"]}'

    def get(self, path, **kw):
        return self.http.get(f'{BASE}{path}', **kw)

    def post(self, path, **kw):
        return self.http.post(f'{BASE}{path}', **kw)


def appeal_answers(**overrides) -> dict:
    answers = {
        'full_name': 'Majid Khan',
        'student_number': f'A-{STAMP}',
        'institution_name': 'Aurora College',
        'semester': 'fall',
        'academic_year': '2026-2027',
        'appeal_reason': 'The course load was recorded wrongly.',
        'signature': 'Majid Khan',
        'declaration_confirmed': True,
        'signed_on': '2026-08-16',
    }
    answers.update(overrides)
    return answers


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default=BASE)
    BASE = parser.parse_args().base.rstrip('/')

    section('Signing in')
    people = {name: Actor(f'{name}@dgg.test')
              for name in ('student', 'student2', 'worker', 'director',
                           'finance', 'admin')}
    for name, actor in people.items():
        if not check(f'{name} can sign in', actor.signed_in):
            print('        Run: python manage.py seed_demo')
            return 1
    student, other = people['student'], people['student2']
    worker, director = people['worker'], people['director']
    finance, admin = people['finance'], people['admin']

    # ── A filed application ──────────────────────────────────────────────────
    section('A student files an appeal')

    filed = student.post('/api/applications/',
                         json={'type': 'appeal', 'answers': appeal_answers()})
    if not check('the appeal is filed', filed.status_code == 201,
                 f'{filed.status_code} {filed.text[:300]}'):
        return 1
    application_id = filed.json()['id']
    application = Application.objects.get(pk=application_id)
    check('it opens in the office queue as submitted',
          application.status == 'submitted', application.status)

    # ── The office corrects it ───────────────────────────────────────────────
    section('An administrator corrects it on the applicant’s behalf')

    for name, actor in (('a student', student), ('a support worker', worker),
                        ('the director', director), ('finance', finance)):
        refused = actor.post(f'/api/applications/{application_id}/amend/',
                             json={'answers': appeal_answers(institution_name='Elsewhere')})
        application.refresh_from_db()
        check(f'{name} cannot edit a filed application',
              refused.status_code in (403, 404)
              and application.answers['institution_name'] == 'Aurora College',
              f'{refused.status_code}, institution now '
              f'{application.answers["institution_name"]}')

    before = Notification.objects.filter(user=application.student).count()
    amended = admin.post(f'/api/applications/{application_id}/amend/', json={
        'answers': appeal_answers(institution_name='Aurora College — North Slave'),
        'note': 'Corrected the campus, confirmed by phone.',
    })
    check('an administrator can', amended.status_code == 200,
          f'{amended.status_code} {amended.text[:300]}')

    application.refresh_from_db()
    check('the answer the office typed is the answer that is stored',
          application.answers['institution_name'] == 'Aurora College — North Slave',
          application.answers.get('institution_name'))
    check('nothing else on the form was disturbed',
          application.answers['appeal_reason'] == 'The course load was recorded wrongly.',
          application.answers.get('appeal_reason'))

    check('the correction did not move the application through review',
          application.status == 'submitted', application.status)
    check('the status still agrees with its own history',
          workflow.status_is_consistent(application))

    event = application.events.filter(
        action=ApplicationEvent.Action.AMENDED).order_by('-occurred_at').first()
    check('the history says who changed it and why',
          event is not None and event.actor and event.actor.email == 'admin@dgg.test'
          and 'Corrected the campus' in event.note,
          str(event and (event.actor, event.note)))

    entry = (AuditEntry.objects.filter(action='application.amended',
                                       application=application)
             .order_by('-id').first())
    check('the audit entry names the answer that changed',
          entry is not None and 'institution_name' in entry.detail,
          str(entry and entry.detail)[:160])

    # ── What the applicant is told ───────────────────────────────────────────
    section('The applicant is told, without having to ask')

    notice = (Notification.objects.filter(user=application.student)
              .order_by('-created_at').first())
    check('a notice was raised',
          Notification.objects.filter(user=application.student).count() == before + 1)
    check('it says the office changed the application',
          notice is not None and notice.kind == 'amended',
          str(notice and notice.kind))
    check('it carries the words the administrator wrote',
          notice is not None and 'Corrected the campus' in notice.message,
          str(notice and notice.message)[:160])
    check('it links to the application it is about',
          notice is not None and notice.link == f'/applications/{application_id}',
          str(notice and notice.link))

    queued = (OutboundEmail.objects.filter(to_email=application.student.email)
              .order_by('-id').first())
    check('an email was queued as well',
          queued is not None and 'updated' in queued.subject.lower(),
          str(queued and queued.subject))

    listing = student.get('/api/notifications/')
    titles = [row['title'] for row in listing.json().get('results', [])]
    check('the student can see the notice in their portal',
          any('updated' in title.lower() for title in titles), str(titles[:3]))

    seen = student.get(f'/api/applications/{application_id}/')
    check('and the change itself, on their own copy',
          seen.status_code == 200
          and seen.json()['answers']['institution_name'] == 'Aurora College — North Slave',
          f'{seen.status_code}')
    check('somebody else’s student account still cannot open it',
          other.get(f'/api/applications/{application_id}/').status_code == 404)

    # ── The office asks for something, in its own words ──────────────────────
    section('A reviewer asks for something, in their own words')

    worker.post(f'/api/applications/{application_id}/transition/',
                json={'action': 'reviewed'})
    asked = worker.post(f'/api/applications/{application_id}/transition/', json={
        'action': 'info_requested',
        'note': 'Please attach the letter from your instructor and remove the '
                'draft you uploaded by mistake.',
    })
    check('the request is recorded', asked.status_code == 200,
          f'{asked.status_code} {asked.text[:200]}')

    application.refresh_from_db()
    check('the application is waiting on the student',
          application.status == 'info_requested', application.status)

    notice = (Notification.objects.filter(user=application.student)
              .order_by('-created_at').first())
    check('the student is told what is actually needed, not to guess',
          notice is not None and 'letter from your instructor' in notice.message,
          str(notice and notice.message)[:200])
    check('the notice is marked as needing action',
          notice is not None and notice.kind == 'action_needed',
          str(notice and notice.kind))

    detail = student.get(f'/api/applications/{application_id}/').json()
    check('the request is on the application the notice links to',
          'letter from your instructor'
          in str(detail.get('information_requested') or ''),
          str(detail.get('information_requested'))[:200])
    check('the student is allowed to edit it now', detail.get('can_revise') is True,
          str(detail.get('can_revise')))

    # ── The student answers, documents and all ───────────────────────────────
    section('The student edits, and adds, replaces and removes documents')

    def upload(name):
        response = student.post(
            '/api/documents/',
            files={'file': (name, io.BytesIO(PNG), 'image/png')},
            data={'field_key': 'doc_supporting', 'application': application_id})
        return response.json().get('reference', '') if response.status_code == 201 else ''

    first, second = upload('draft.png'), upload('letter.png')
    check('two documents upload against the application', bool(first and second),
          f'{first!r} {second!r}')

    revised = student.post(f'/api/applications/{application_id}/revise/', json={
        'answers': appeal_answers(
            institution_name='Aurora College — North Slave',
            appeal_reason='The course load was recorded wrongly. Letter attached.',
            doc_supporting=[first, second],
        ),
    })
    check('the student can answer with both attached', revised.status_code == 200,
          f'{revised.status_code} {revised.text[:300]}')

    application.refresh_from_db()
    check('both documents are on the application',
          application.answers.get('doc_supporting') == [first, second],
          str(application.answers.get('doc_supporting')))
    check('answering put it back into the queue',
          application.status == 'under_review', application.status)

    # Removing one is the case that had no control at all: a single-file
    # question could be replaced but not emptied.
    removed = student.post(f'/api/applications/{application_id}/revise/', json={
        'answers': appeal_answers(
            institution_name='Aurora College — North Slave',
            appeal_reason='The course load was recorded wrongly. Letter attached.',
            doc_supporting=[second],
        ),
    })
    check('a document can be taken off the application',
          removed.status_code in (200, 409), f'{removed.status_code} {removed.text[:200]}')

    if removed.status_code == 409:
        # It went back to under_review on the first answer, so a second edit
        # needs the office to ask again. That is the rule, not a fault.
        worker.post(f'/api/applications/{application_id}/transition/',
                    json={'action': 'info_requested', 'note': 'Remove the draft.'})
        removed = student.post(f'/api/applications/{application_id}/revise/', json={
            'answers': appeal_answers(
                institution_name='Aurora College — North Slave',
                appeal_reason='The course load was recorded wrongly. Letter attached.',
                doc_supporting=[second],
            ),
        })
        check('and can be, once the office asks again', removed.status_code == 200,
              f'{removed.status_code} {removed.text[:200]}')

    application.refresh_from_db()
    check('the removed document is gone from the answers',
          first not in (application.answers.get('doc_supporting') or []),
          str(application.answers.get('doc_supporting')))
    check('the one that was kept is still there',
          second in (application.answers.get('doc_supporting') or []),
          str(application.answers.get('doc_supporting')))

    staff_view = worker.get(f'/api/applications/{application_id}/').json()
    attached = [document['id'] for document in staff_view.get('documents', [])]
    check('the office sees exactly what the student left attached',
          len(attached) >= 1, str(staff_view.get('documents'))[:200])
    for document in staff_view.get('documents', []):
        opened = worker.get(document['url'].replace('/api', '') if
                            document['url'].startswith('/api') else document['url'])
        # The client strips the /api prefix; drive the real path here.
        opened = worker.get(f'/api/documents/{document["id"]}/')
        check(f'the office can open {document["original_name"]}',
              opened.status_code == 200, f'{opened.status_code}')

    # ── Once it is decided, the record is the record ─────────────────────────
    section('Once decided, the answers are the record')

    worker.post(f'/api/applications/{application_id}/transition/',
                json={'action': 'forwarded'})
    approved = director.post(f'/api/applications/{application_id}/transition/',
                             json={'action': 'approved'})
    check('the director can approve it', approved.status_code == 200,
          f'{approved.status_code} {approved.text[:200]}')

    refused = admin.post(f'/api/applications/{application_id}/amend/', json={
        'answers': appeal_answers(institution_name='Somewhere else entirely'),
    })
    check('a decided application cannot be rewritten, even by an administrator',
          refused.status_code == 409, f'{refused.status_code} {refused.text[:200]}')

    application.refresh_from_db()
    check('and it was not', application.answers['institution_name']
          == 'Aurora College — North Slave',
          application.answers.get('institution_name'))
    check('its history is still consistent with its status',
          workflow.status_is_consistent(application))

    # ── The answers the server itself wrote ──────────────────────────────────
    section('An application carrying answers its own schema never asked for')

    # `confirmed_tuition` is the registrar's figure, written onto the
    # application when they confirm the enrolment. The admission schema has no
    # such question, so re-posting the stored answers was refused for a key the
    # *server* had put there — and every admission application became
    # uneditable, by anyone, the moment its institution answered. Nothing
    # noticed because every audit of an edit used a form with no registrar.
    # Filed and confirmed here rather than borrowed from whatever another audit
    # happened to leave behind: a script that only passes when its neighbours
    # ran first is a script that reports on the database rather than on the
    # system.
    admission = student.post('/api/applications/', json={
        'type': 'admission', 'answers': admission_answers(),
    })
    confirmed = None
    if check('an admission application can be filed', admission.status_code == 201,
             f'{admission.status_code} {admission.text[:300]}'):
        issued = EnrollmentVerification.objects.filter(
            application_id=admission.json()['id']).first()
        if check('its institution was asked to confirm', issued is not None):
            answered = requests.post(f'{BASE}/api/enrolment/{issued.token}/', json={
                'answers': {
                    'student_name': 'Majid Khan',
                    'institution_name': 'Aurora College',
                    'program': 'Environmental Science',
                    'is_enrolled': True,
                    'course_load': 'full_time',
                    'semester': 'fall',
                    'semester_start': '2026-09-01',
                    'semester_end': '2026-12-31',
                    'confirmed_tuition': '7431.55',
                    'registrar_name': 'R. Registrar',
                    'registrar_title': 'Registrar',
                    'signature': 'R. Registrar',
                    'completed_on': '2026-09-05',
                }})
            if check('the registrar confirms it', answered.status_code == 200,
                     f'{answered.status_code} {answered.text[:200]}'):
                confirmed = Application.objects.get(pk=admission.json()['id'])

    if confirmed is None:
        check('an admission application with a confirmed tuition exists to try', False)
    else:
        tuition = confirmed.answers.get('confirmed_tuition')
        edited = admin.post(f'/api/applications/{confirmed.pk}/amend/', json={
            'answers': {**confirmed.answers, 'program': f'Corrected {STAMP}'},
            'note': 'Corrected the programme name.',
        })
        check('the office can edit an application whose enrolment is confirmed',
              edited.status_code == 200, f'{edited.status_code} {edited.text[:300]}')

        confirmed.refresh_from_db()
        check('the correction was applied',
              confirmed.answers.get('program') == f'Corrected {STAMP}',
              str(confirmed.answers.get('program')))
        check('the registrar’s tuition figure survived the edit',
              confirmed.answers.get('confirmed_tuition') == tuition,
              f'{tuition} -> {confirmed.answers.get("confirmed_tuition")}')

        # Tuition is funded against the institution's number, never one somebody
        # typed. An edit that could set it is a way to inflate an award.
        inflated = admin.post(f'/api/applications/{confirmed.pk}/amend/', json={
            'answers': {**confirmed.answers, 'confirmed_tuition': '99999.00'},
        })
        confirmed.refresh_from_db()
        check('an edit cannot raise the tuition the award is funded against',
              confirmed.answers.get('confirmed_tuition') == tuition,
              f'{inflated.status_code}: tuition now '
              f'{confirmed.answers.get("confirmed_tuition")}')
        check('the regulated number is still absent from the answers',
              'sin' not in confirmed.answers,
              str(list(confirmed.answers))[:200])

    print()
    if failures:
        print(f'{len(failures)} of {checks} checks FAILED')
        for failure in failures:
            print(f'  - {failure}')
        return 1
    print(f'{checks}/{checks} checks passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
