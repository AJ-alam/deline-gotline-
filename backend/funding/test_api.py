"""HTTP surface for the funding domain."""

import itertools
from decimal import Decimal

from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from funding.models import Application, ApplicationStatus, ApplicationType, FundingStream
from funding.test_rules import seed_rates

_counter = itertools.count(1)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'{role}{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
    )


VALID_ADMISSION = {
    'first_name': 'Jane', 'last_name': 'Doe', 'date_of_birth': '2001-05-04',
    'email': 'jane@example.com', 'street_address': '1 Main St', 'city': 'Deline',
    'province': 'NT', 'institution_name': 'Aurora College', 'program': 'Nursing',
    'registrar_email': 'registrar@aurora.ca', 'semester': 'Fall',
    'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
    'course_load': 'Full-time', 'signature': 'Jane Doe',
    'doc_transcript': 'provided', 'doc_letter_of_intent': 'provided',
    'doc_status_card': 'provided', 'doc_void_cheque': 'provided',
}


class SchemaEndpointTests(APITestCase):
    """One definition drives every client, so it has to be fetchable."""

    def test_schemas_are_public(self):
        response = self.client.get('/api/schemas/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(ApplicationType.values))

    def test_a_schema_describes_enough_to_render_a_form(self):
        response = self.client.get('/api/schemas/admission/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['sections'])
        field = next(f for f in response.data['fields'] if f['key'] == 'course_load')
        self.assertEqual(field['type'], 'choice')
        self.assertTrue(field['required'])
        self.assertEqual([c['value'] for c in field['choices']],
                         ['full_time', 'part_time'])

    def test_an_unknown_schema_is_a_404(self):
        response = self.client.get('/api/schemas/form-a/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SubmissionTests(APITestCase):

    def setUp(self):
        self.student = make_user()
        self.client.force_authenticate(self.student)

    def _submit(self, answers=None, app_type='admission'):
        return self.client.post('/api/applications/', {
            'type': app_type, 'stream': 'psssp',
            'answers': answers if answers is not None else VALID_ADMISSION,
        }, format='json')

    def test_a_student_can_submit_an_application(self):
        response = self._submit()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApplicationStatus.SUBMITTED)
        self.assertEqual(response.data['answers']['course_load'], 'full_time')

    def test_submitting_records_the_first_event(self):
        response = self._submit()
        self.assertEqual([e['action'] for e in response.data['events']], ['submitted'])

    def test_invalid_answers_are_reported_per_field(self):
        response = self._submit({**VALID_ADMISSION, 'course_load': 'whenever'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('course_load', response.data['answers'])

    def test_an_unknown_field_is_rejected(self):
        response = self._submit({**VALID_ADMISSION, 'coarse_load': 'full_time'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('coarse_load', response.data['answers'])

    def test_missing_required_answers_are_all_reported_at_once(self):
        response = self._submit({})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertGreater(len(response.data['answers']), 5)

    def test_anonymous_users_cannot_submit(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._submit().status_code, status.HTTP_401_UNAUTHORIZED)


class VisibilityTests(APITestCase):

    def setUp(self):
        self.student = make_user()
        self.other = make_user()
        self.worker = make_user(Role.SUPPORT_WORKER)
        for owner in (self.student, self.other):
            Application.objects.create(
                student=owner, type=ApplicationType.ADMISSION,
                stream=FundingStream.PSSSP, schema_slug='admission', answers={},
                status=ApplicationStatus.SUBMITTED,
            )

    def test_a_student_sees_only_their_own_applications(self):
        self.client.force_authenticate(self.student)
        response = self.client.get('/api/applications/')
        self.assertEqual(len(response.data['results']), 1)

    def test_staff_see_every_application(self):
        self.client.force_authenticate(self.worker)
        response = self.client.get('/api/applications/')
        self.assertEqual(len(response.data['results']), 2)

    def test_a_student_cannot_read_someone_elses_application(self):
        theirs = Application.objects.filter(student=self.other).get()
        self.client.force_authenticate(self.student)
        response = self.client.get(f'/api/applications/{theirs.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_the_queue_omits_answers_and_trace(self):
        """The previous list endpoint returned 30KB per 50 rows."""
        self.client.force_authenticate(self.worker)
        row = self.client.get('/api/applications/').data['results'][0]
        self.assertNotIn('answers', row)
        self.assertNotIn('events', row)


class TransitionEndpointTests(APITestCase):

    def setUp(self):
        self.student = make_user()
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.director = make_user(Role.DIRECTOR)
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission', answers={},
                status=ApplicationStatus.SUBMITTED,
        )

    def _transition(self, user, action, note=''):
        self.client.force_authenticate(user)
        return self.client.post(
            f'/api/applications/{self.application.id}/transition/',
            {'action': action, 'note': note}, format='json',
        )

    def test_a_support_worker_can_review(self):
        response = self._transition(self.worker, 'reviewed')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ApplicationStatus.UNDER_REVIEW)

    def test_a_student_cannot_advance_their_own_application(self):
        response = self._transition(self.student, 'reviewed')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_support_worker_cannot_approve(self):
        """Only the Director decides."""
        self._transition(self.worker, 'reviewed')
        self._transition(self.worker, 'forwarded')
        response = self._transition(self.worker, 'approved')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_the_director_can_approve_once_forwarded(self):
        self._transition(self.worker, 'reviewed')
        self._transition(self.worker, 'forwarded')
        response = self._transition(self.director, 'approved')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ApplicationStatus.APPROVED)

    def test_an_out_of_order_transition_is_a_conflict(self):
        response = self._transition(self.director, 'approved')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('submitted', response.data['detail'].lower())


class PricingEndpointTests(APITestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.student = make_user()
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.director = make_user(Role.DIRECTOR)
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            answers={'course_load': 'full_time', 'confirmed_tuition': '6000',
                     'semester_start': '2026-09-01', 'semester_end': '2026-12-31'},
        )

    def test_staff_can_preview_an_award_without_recording_it(self):
        self.client.force_authenticate(self.worker)
        response = self.client.get(
            f'/api/applications/{self.application.id}/decision-preview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['rules'])
        self.assertFalse(self.application.decisions.exists())

    def test_a_student_cannot_preview_an_award(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(
            f'/api/applications/{self.application.id}/decision-preview/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_the_director_can_record_a_decision(self):
        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{self.application.id}/price/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreater(Decimal(response.data['total']), 0)
        self.assertTrue(response.data['lines'])

    def test_a_support_worker_cannot_record_a_decision(self):
        self.client.force_authenticate(self.worker)
        response = self.client.post(f'/api/applications/{self.application.id}/price/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_policy_is_reported_with_the_rates_that_are_absent(self):
        from funding.models import PolicySetting
        PolicySetting.objects.all().delete()
        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{self.application.id}/price/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(response.data['missing_rates'])

    def test_decision_history_is_available_for_an_appeal(self):
        self.client.force_authenticate(self.director)
        self.client.post(f'/api/applications/{self.application.id}/price/')
        self.client.post(f'/api/applications/{self.application.id}/price/')
        response = self.client.get(
            f'/api/applications/{self.application.id}/decisions/')
        self.assertEqual(len(response.data), 2)
        self.assertEqual(sum(1 for d in response.data if d['is_current']), 1)
