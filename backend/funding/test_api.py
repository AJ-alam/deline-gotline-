"""HTTP surface for the funding domain."""

import itertools
from decimal import Decimal

from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from funding.test_fixtures import confirm_enrolment
from funding.models import Application, ApplicationStatus, ApplicationType, FundingStream
from funding.test_fixtures import (
    admission_answers, confirm_enrolment, verification_answers,
)
from funding.test_rules import seed_rates

_counter = itertools.count(1)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'{role}{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name='Person', role=role,is_deline_beneficiary=True, is_indian_act_registered=True)


VALID_ADMISSION = admission_answers()


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
        # Tuition is funded against the registrar's figure, so an admission
        # application cannot leave review until the institution confirms.
        confirm_enrolment(self.application)
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
        # The registrar's answer is what writes `confirmed_tuition`, and
        # what lets an admission be priced at all.
        confirm_enrolment(self.application)

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


class QueryCostTests(APITestCase):
    """Endpoint cost must not grow with the amount of data.

    The previous dashboard fired seven requests every thirty seconds, two of
    them for the same records under two models, and returned every answer with
    every row.
    """

    def setUp(self):
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.client.force_authenticate(self.worker)
        for _ in range(25):
            Application.objects.create(
                student=make_user(), type=ApplicationType.ADMISSION,
                stream=FundingStream.PSSSP, schema_slug='admission',
                answers=dict(VALID_ADMISSION), status=ApplicationStatus.SUBMITTED,
            )

    def test_the_queue_costs_the_same_however_many_rows(self):
        # Three: the count, the page, and one prefetch for the enrolment
        # verifications on that page. What matters is that the number does not
        # change with the number of rows — a per-row lookup is the thing this
        # guards against.
        with self.assertNumQueries(3):
            self.client.get('/api/applications/?page_size=5')
        with self.assertNumQueries(3):
            self.client.get('/api/applications/?page_size=25')

    def test_detail_reads_the_prefetched_decision_rather_than_refetching(self):
        """Repricing must not make reading the application more expensive.

        A queryset call inside the serializer would issue a fresh query per
        decision, defeating the prefetch.
        """
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        application = Application.objects.first()
        application.answers = {**VALID_ADMISSION, 'confirmed_tuition': '6000'}
        application.save(update_fields=['answers'])
        confirm_enrolment(application)

        from funding.services.decisions import record_decision
        record_decision(application)
        with CaptureQueriesContext(connection) as first:
            self.client.get(f'/api/applications/{application.id}/')

        for _ in range(3):
            record_decision(application)
        with CaptureQueriesContext(connection) as after:
            self.client.get(f'/api/applications/{application.id}/')

        self.assertEqual(
            len(after), len(first),
            f'reading cost grew from {len(first)} to {len(after)} queries '
            'as decisions accumulated',
        )


class SchemaCachingTests(APITestCase):
    """Schemas are defined in code and cannot change between deploys.

    25KB that every visitor would otherwise download before seeing a field.
    """

    def test_the_response_carries_a_validator(self):
        response = self.client.get('/api/schemas/')
        self.assertTrue(response['ETag'])
        self.assertIn('max-age', response['Cache-Control'])

    def test_a_repeat_request_is_not_sent_again(self):
        first = self.client.get('/api/schemas/')
        second = self.client.get('/api/schemas/', HTTP_IF_NONE_MATCH=first['ETag'])
        self.assertEqual(second.status_code, status.HTTP_304_NOT_MODIFIED)
        self.assertFalse(second.content)

    def test_serving_a_schema_costs_no_database_queries(self):
        with self.assertNumQueries(0):
            self.client.get('/api/schemas/admission/')

    def test_a_changed_validator_still_serves_the_body(self):
        response = self.client.get('/api/schemas/', HTTP_IF_NONE_MATCH='"stale"')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)


class ListFilterTests(APITestCase):
    """Filtering the application list.

    DjangoFilterBackend is enabled globally, but a view that declares no
    filterset filters nothing — and does so silently, returning 200 and the
    whole list. Both the student's list and the staff queue passed ?status=
    and were quietly given everything, so a student filtering to "being
    reviewed" still saw applications that had been declined.
    """

    def setUp(self):
        self.student = make_user()
        self.reviewed = Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            status=ApplicationStatus.UNDER_REVIEW, answers={})
        self.declined = Application.objects.create(
            student=self.student, type=ApplicationType.TRAVEL,
            stream=FundingStream.DGGR, schema_slug='travel',
            status=ApplicationStatus.DECLINED, answers={})
        self.client.force_authenticate(self.student)

    def ids(self, query=''):
        response = self.client.get(f'/api/applications/{query}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row['id'] for row in response.data['results']}

    def test_unfiltered_returns_everything(self):
        self.assertEqual(self.ids(), {self.reviewed.pk, self.declined.pk})

    def test_filtering_by_status_excludes_the_others(self):
        self.assertEqual(self.ids('?status=under_review'), {self.reviewed.pk})

    def test_a_declined_application_is_not_returned_as_under_review(self):
        """The reported symptom."""
        self.assertNotIn(self.declined.pk, self.ids('?status=under_review'))

    def test_filtering_by_type_excludes_the_others(self):
        self.assertEqual(self.ids('?type=travel'), {self.declined.pk})

    def test_filtering_by_stream_excludes_the_others(self):
        self.assertEqual(self.ids('?stream=psssp'), {self.reviewed.pk})

    def test_the_count_reflects_the_filter(self):
        """A count of everything under a filtered list misreports the total."""
        response = self.client.get('/api/applications/?status=under_review')
        self.assertEqual(response.data['count'], 1)

    def test_filters_combine(self):
        self.assertEqual(
            self.ids('?status=under_review&type=admission'), {self.reviewed.pk})
        self.assertEqual(self.ids('?status=under_review&type=travel'), set())

    def test_an_unknown_status_is_refused_rather_than_ignored(self):
        """Silently returning everything is how this went unnoticed."""
        response = self.client.get('/api/applications/?status=not_a_status')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_filter_cannot_reach_another_students_applications(self):
        other = Application.objects.create(
            student=make_user(), type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            status=ApplicationStatus.UNDER_REVIEW, answers={})
        self.assertNotIn(other.pk, self.ids('?status=under_review'))

    def test_staff_filtering_narrows_the_queue(self):
        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER))
        self.assertEqual(self.ids('?status=declined'), {self.declined.pk})
