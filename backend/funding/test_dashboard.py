"""The numbers a person sees on opening the portal.

The screen this replaces fetched seven endpoints every thirty seconds and
counted rows in the browser, so it grew slower with every application the office
received. The cost here must not depend on how much data exists.
"""

import itertools
from decimal import Decimal

from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import BankAccount, Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    EnrollmentVerification, FundingStream,
)
from funding.services import dashboard, verification, workflow
from funding.services.decisions import record_decision
from funding.test_rules import seed_rates

_counter = itertools.count(1)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'd{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name=f'P{next(_counter)}', role=role,
    )


def make_application(student=None, status=ApplicationStatus.SUBMITTED, **kwargs):
    defaults = dict(
        student=student or make_user(), type=ApplicationType.ADMISSION,
        stream=FundingStream.PSSSP, schema_slug='admission', status=status,
        answers={'course_load': 'full_time', 'confirmed_tuition': '6000',
                 'semester_start': '2026-09-01', 'semester_end': '2026-12-31'},
    )
    defaults.update(kwargs)
    return Application.objects.create(**defaults)


class StaffSummaryTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.staff = make_user(Role.SUPPORT_WORKER)

    def test_applications_are_counted_by_status(self):
        make_application()
        make_application(status=ApplicationStatus.APPROVED)
        make_application(status=ApplicationStatus.DECLINED)

        summary = dashboard.summary(self.staff)
        by_status = summary['applications']['by_status']
        self.assertEqual(by_status['submitted'], 1)
        self.assertEqual(by_status['approved'], 1)
        self.assertEqual(by_status['declined'], 1)
        self.assertEqual(summary['applications']['total'], 3)

    def test_every_status_appears_even_when_none_are_in_it(self):
        """A missing key would make a dashboard show nothing rather than zero."""
        summary = dashboard.summary(self.staff)
        for status in ApplicationStatus.values:
            self.assertIn(status, summary['applications']['by_status'])

    def test_open_excludes_decided_applications(self):
        make_application()
        make_application(status=ApplicationStatus.APPROVED)
        self.assertEqual(dashboard.summary(self.staff)['applications']['open'], 1)

    def test_the_queues_are_the_ones_staff_work_from(self):
        make_application()
        make_application(status=ApplicationStatus.AWAITING_DECISION)

        queues = dashboard.summary(self.staff)['queues']
        self.assertEqual(queues['to_review'], 1)
        self.assertEqual(queues['awaiting_decision'], 1)

    def test_outstanding_enrolment_confirmations_are_counted(self):
        application = make_application()
        verification.issue(application, 'registrar@aurora.ca')
        self.assertEqual(
            dashboard.summary(self.staff)['queues']['awaiting_enrolment_confirmation'], 1)

        # Once confirmed it drops off the queue.
        EnrollmentVerification.objects.update(
            status=EnrollmentVerification.Status.COMPLETED)
        self.assertEqual(
            dashboard.summary(self.staff)['queues']['awaiting_enrolment_confirmation'], 0)

    def test_money_is_split_by_where_it_has_reached(self):
        application = make_application()
        record_decision(application)
        awarded = application.awarded_total

        summary = dashboard.summary(self.staff)
        self.assertEqual(Decimal(summary['money']['awarded']), awarded)
        self.assertEqual(Decimal(summary['money']['awaiting_payment']), awarded)
        self.assertEqual(Decimal(summary['money']['sent_to_finance']), Decimal('0.00'))

    def test_money_moves_once_a_batch_is_dispatched(self):
        from funding.services import finance

        student = make_user()
        BankAccount.objects.create(
            user=student, account_holder=student.full_name, transit_number='12345',
            institution_number='001', account_number='9876543210')
        application = make_application(student=student)
        director = make_user(Role.DIRECTOR)
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.staff)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.staff)
        workflow.record(application, ApplicationEvent.Action.APPROVED, director)
        record_decision(application)
        finance.dispatch(actor=make_user(Role.FINANCE))

        money = dashboard.summary(self.staff)['money']
        self.assertEqual(Decimal(money['awaiting_payment']), Decimal('0.00'))
        self.assertGreater(Decimal(money['sent_to_finance']), Decimal('0.00'))

    def test_applications_needing_attention_are_surfaced(self):
        make_application(submitted_after_deadline=True)
        make_application(residency_flag='Declared outside the NWT')

        attention = dashboard.summary(self.staff)['attention']
        self.assertEqual(attention['submitted_late'], 1)
        self.assertEqual(attention['residency_mismatch'], 1)

    def test_an_empty_office_reads_as_zero_not_as_an_error(self):
        summary = dashboard.summary(self.staff)
        self.assertEqual(summary['applications']['total'], 0)
        self.assertEqual(Decimal(summary['money']['awarded']), Decimal('0.00'))


class StudentSummaryTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.student = make_user()

    def test_a_student_sees_only_their_own(self):
        make_application(student=self.student)
        make_application()      # somebody else's

        summary = dashboard.summary(self.student)
        self.assertEqual(summary['scope'], 'student')
        self.assertEqual(summary['applications']['total'], 1)

    def test_money_counts_only_their_own_awards(self):
        mine = make_application(student=self.student)
        record_decision(mine)
        record_decision(make_application())     # somebody else's

        summary = dashboard.summary(self.student)
        self.assertEqual(Decimal(summary['money']['awarded']), mine.awarded_total)

    def test_a_student_is_told_what_is_waiting_on_them(self):
        make_application(student=self.student,
                         status=ApplicationStatus.INFO_REQUESTED)
        self.assertEqual(dashboard.summary(self.student)['waiting_on_you'], 1)

    def test_a_student_is_not_shown_the_office_queues(self):
        summary = dashboard.summary(self.student)
        self.assertNotIn('queues', summary)
        self.assertNotIn('attention', summary)


class CostTests(TestCase):
    """The property that made the old dashboard unusable."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.staff = make_user(Role.SUPPORT_WORKER)

    def test_the_cost_does_not_grow_with_the_number_of_applications(self):
        for _ in range(3):
            make_application()
        with CaptureQueriesContext(connection) as few:
            dashboard.summary(self.staff)

        for _ in range(40):
            make_application()
        with CaptureQueriesContext(connection) as many:
            dashboard.summary(self.staff)

        self.assertEqual(
            len(many), len(few),
            f'cost grew from {len(few)} to {len(many)} queries as data was added',
        )

    def test_the_whole_summary_is_a_handful_of_queries(self):
        for _ in range(10):
            make_application()
        with CaptureQueriesContext(connection) as queries:
            dashboard.summary(self.staff)
        self.assertLessEqual(len(queries), 5, [q['sql'] for q in queries])


class EndpointTests(TestCase):

    def setUp(self):
        seed_rates()
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')

    def test_one_request_serves_the_whole_screen(self):
        staff = make_user(Role.SUPPORT_WORKER)
        make_application()
        self.client.force_authenticate(staff)

        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, 200)
        for key in ('applications', 'money', 'queues', 'attention'):
            self.assertIn(key, response.data)

    def test_the_payload_is_scoped_to_the_role(self):
        student = make_user()
        make_application(student=student)
        self.client.force_authenticate(student)

        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.data['scope'], 'student')
        self.assertNotIn('queues', response.data)

    def test_anonymous_requests_are_rejected(self):
        self.assertEqual(self.client.get('/api/dashboard/').status_code, 401)
