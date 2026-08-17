"""Applying without an account.

The path exists because two awards — a summer placement allowance and a
graduation bursary — are claimed once, after the fact, by people who often are
not otherwise students here. What has to hold: the submission is a real
application subject to the same schema, it belongs to nobody until staff say
otherwise, it cannot be used to reach anything else, and the person who made it
is actually told it arrived.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, AuditEntry, FundingStream,
    PolicySetting,
)
from funding.test_fixtures import answers_for
from notifications.models import Notification, OutboundEmail

URL = '/api/guest-applications/'

# Built from the schema for the same reason the practicum answers below are:
# this was a hand-written copy, and it went stale the moment the graduation
# award started asking for an address and bank details. It failed with a 400
# that looked like a bug in the guest endpoint.
BURSARY_ANSWERS = answers_for(
    'graduation_bursary',
    full_name='Guest Applicant',
    email='guest.applicant@example.com',
    institution_name='Aurora College', program='Business Administration',
    credential='diploma', graduation_date='2026-05-30',
    signature='Guest Applicant',
    doc_proof_of_completion='provided',
)

# Built from the schema rather than written out, so a question added to the
# employer's half of the form is answered here too. The hand-written copy this
# replaces went stale the moment the placement report was added, and failed with
# a 400 that looked like a bug in the guest endpoint.
PRACTICUM_ANSWERS = answers_for(
    'practicum',
    full_name='Summer Worker', email='summer.worker@example.com',
    employer_name='Deline Health Centre', supervisor_title='Director of Care',
    placement_start='2026-06-01', placement_end='2026-08-15',
    supervisor_signature='Rita Baton', report_completed_on='2026-08-20',
)


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@test.com', 'pw12345678',
        first_name='Test', last_name='Person', role=role, is_deline_beneficiary=True, is_indian_act_registered=True)


class GuestSubmissionTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_a_graduation_bursary_can_be_claimed_without_an_account(self):
        response = self.client.post(
            URL, {'type': 'graduation_bursary', 'answers': BURSARY_ANSWERS},
            format='json')

        self.assertEqual(response.status_code, 201)
        application = Application.objects.get()
        self.assertIsNone(application.student)
        self.assertEqual(application.type, ApplicationType.GRADUATION_BURSARY)
        self.assertEqual(response.data['reference'], f'DGG-{application.pk:06d}')

    def test_a_practicum_allowance_can_be_claimed_without_an_account(self):
        response = self.client.post(
            URL, {'type': 'practicum', 'answers': PRACTICUM_ANSWERS},
            format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(Application.objects.get().student)

    def test_a_guest_submission_is_submitted_not_left_as_a_draft(self):
        """A draft nobody owns is a record no queue would ever show."""
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        application = Application.objects.get()
        self.assertEqual(application.status, ApplicationStatus.SUBMITTED)
        self.assertEqual([e.action for e in application.events.all()], ['submitted'])

    def test_the_submission_event_is_attributed_to_nobody(self):
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        self.assertIsNone(Application.objects.get().events.get().actor)

    def test_the_stream_is_set_by_the_server(self):
        """A guest cannot put a DGGR bursary against a federal programme."""
        self.client.post(
            URL,
            {'type': 'graduation_bursary', 'stream': 'psssp',
             'answers': BURSARY_ANSWERS},
            format='json')
        self.assertEqual(Application.objects.get().stream, FundingStream.DGGR)

    def test_the_applicant_is_told_it_arrived(self):
        """Every other message needs `student` and would send nothing."""
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(URL, {'type': 'graduation_bursary',
                                   'answers': BURSARY_ANSWERS}, format='json')

        queued = OutboundEmail.objects.get()
        self.assertEqual(queued.to_email, 'guest.applicant@example.com')
        self.assertIn(f'DGG-{Application.objects.get().pk:06d}', queued.subject)

    def test_the_reference_number_is_in_the_message_body(self):
        """It is the only handle a guest has on their application."""
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(URL, {'type': 'graduation_bursary',
                                   'answers': BURSARY_ANSWERS}, format='json')

        reference = f'DGG-{Application.objects.get().pk:06d}'
        self.assertIn(reference, OutboundEmail.objects.get().body_html)

    def test_a_guest_submission_queues_no_portal_notice(self):
        """There is no account for one to appear in."""
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(URL, {'type': 'graduation_bursary',
                                   'answers': BURSARY_ANSWERS}, format='json')
        self.assertEqual(Notification.objects.count(), 0)

    def test_answers_are_validated_against_the_same_schema(self):
        response = self.client.post(
            URL,
            {'type': 'graduation_bursary',
             'answers': dict(BURSARY_ANSWERS, credential='honorary doctorate')},
            format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('credential', response.data['answers'])

    def test_a_missing_required_answer_is_refused(self):
        answers = {k: v for k, v in BURSARY_ANSWERS.items() if k != 'email'}
        response = self.client.post(
            URL, {'type': 'graduation_bursary', 'answers': answers}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data['answers'])


class GuestScopeTests(TestCase):
    """What the account-less path must not become."""

    def setUp(self):
        self.client = APIClient()

    def test_types_that_need_a_continuing_record_are_refused(self):
        for application_type in ('admission', 'continuing_funding', 'appeal',
                                 'travel', 'emergency_relief',
                                 'hardship_bursary', 'academic_scholarship'):
            with self.subTest(type=application_type):
                response = self.client.post(
                    URL, {'type': application_type, 'answers': BURSARY_ANSWERS},
                    format='json')
                self.assertEqual(response.status_code, 400)
                self.assertFalse(Application.objects.exists())

    def test_only_the_two_guest_forms_are_offered(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(s['slug'] for s in response.data),
            ['graduation_bursary', 'practicum'],
        )

    def test_a_guest_application_cannot_be_read_back_anonymously(self):
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        application = Application.objects.get()
        self.assertEqual(
            self.client.get(f'/api/applications/{application.pk}/').status_code, 401)

    def test_a_student_cannot_see_an_application_nobody_owns(self):
        """Ownerless must not read as everyone's."""
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        application = Application.objects.get()

        self.client.force_authenticate(make_user())
        self.assertEqual(
            self.client.get(f'/api/applications/{application.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/applications/').data['count'], 0)

    def test_staff_do_see_it(self):
        """It is worth nothing if it never reaches the queue."""
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER))
        self.assertEqual(self.client.get('/api/applications/').data['count'], 1)


class AttachTests(TestCase):
    """Linking a guest application to an account, once there is one."""

    def setUp(self):
        self.client = APIClient()
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        self.application = Application.objects.get()
        self.student = make_user(email='student@test.com')
        self.url = f'/api/applications/{self.application.pk}/attach/'

    def test_staff_can_attach_it_to_a_student(self):
        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER, 'worker@test.com'))
        response = self.client.post(self.url, {'student_id': self.student.pk},
                                    format='json')

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.student, self.student)

    def test_the_student_can_then_see_it(self):
        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER, 'worker@test.com'))
        self.client.post(self.url, {'student_id': self.student.pk}, format='json')

        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.get(f'/api/applications/{self.application.pk}/').status_code, 200)

    def test_a_student_cannot_attach_an_application_to_themselves(self):
        """Otherwise the guest queue is a list of applications to be claimed."""
        self.client.force_authenticate(self.student)
        response = self.client.post(self.url, {'student_id': self.student.pk},
                                    format='json')

        # 404, not 403: a student's queryset never contained it to begin with.
        self.assertEqual(response.status_code, 404)
        self.application.refresh_from_db()
        self.assertIsNone(self.application.student)

    def test_an_application_that_already_has_an_owner_is_not_reassigned(self):
        self.application.student = self.student
        self.application.save(update_fields=['student'])
        other = make_user(email='other@test.com')

        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER, 'worker@test.com'))
        response = self.client.post(self.url, {'student_id': other.pk}, format='json')

        self.assertEqual(response.status_code, 409)
        self.application.refresh_from_db()
        self.assertEqual(self.application.student, self.student)

    def test_only_a_student_account_can_be_attached(self):
        director = make_user(Role.DIRECTOR, 'director@test.com')
        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER, 'worker@test.com'))
        response = self.client.post(self.url, {'student_id': director.pk}, format='json')

        self.assertEqual(response.status_code, 400)
        self.application.refresh_from_db()
        self.assertIsNone(self.application.student)

    def test_attaching_is_recorded(self):
        worker = make_user(Role.SUPPORT_WORKER, 'worker@test.com')
        self.client.force_authenticate(worker)
        self.client.post(self.url, {'student_id': self.student.pk}, format='json')

        entry = AuditEntry.objects.get(action='application.attached')
        self.assertEqual(entry.actor, worker)
        self.assertEqual(entry.application, self.application)
        self.assertIn(self.student.email, entry.detail)


class GuestPricingTests(TestCase):
    """A guest application has to be worth something at the end of it."""

    def setUp(self):
        for section, key, value in (
            ('graduation_bursary', 'diploma', '2000.00'),
        ):
            PolicySetting.objects.update_or_create(
                section=section, key=key,
                defaults=dict(label=key, value=Decimal(value), unit='$'))
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.client = APIClient()

    def test_a_guest_application_can_be_reviewed_approved_and_priced(self):
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        application = Application.objects.get()

        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER, 'worker@test.com'))
        for step in ('reviewed', 'forwarded'):
            response = self.client.post(
                f'/api/applications/{application.pk}/transition/',
                {'action': step}, format='json')
            self.assertEqual(response.status_code, 200, step)

        self.client.force_authenticate(make_user(Role.DIRECTOR, 'director@test.com'))
        response = self.client.post(
            f'/api/applications/{application.pk}/transition/',
            {'action': 'approved'}, format='json')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data['total']), Decimal('2000.00'))

    def test_deciding_a_guest_application_does_not_fail_for_want_of_a_student(self):
        """The decision messages all read `application.student`."""
        self.client.post(URL, {'type': 'graduation_bursary',
                               'answers': BURSARY_ANSWERS}, format='json')
        application = Application.objects.get()

        with self.captureOnCommitCallbacks(execute=True):
            self.client.force_authenticate(
                make_user(Role.SUPPORT_WORKER, 'worker@test.com'))
            for step in ('reviewed', 'forwarded'):
                self.client.post(f'/api/applications/{application.pk}/transition/',
                                 {'action': step}, format='json')
            self.client.force_authenticate(
                make_user(Role.DIRECTOR, 'director@test.com'))
            self.client.post(f'/api/applications/{application.pk}/transition/',
                             {'action': 'approved'}, format='json')

        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.APPROVED)


def _url_exists():
    """The route is named, so a rename cannot silently orphan the frontend."""
    return reverse('guest-applications') == URL


class RoutingTests(TestCase):

    def test_the_route_is_named_and_where_the_client_expects(self):
        self.assertTrue(_url_exists())
