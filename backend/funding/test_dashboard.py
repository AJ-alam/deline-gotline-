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
from funding.test_fixtures import confirm_enrolment

_counter = itertools.count(1)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'd{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name=f'P{next(_counter)}', role=role,is_deline_beneficiary=True, is_indian_act_registered=True)


def make_application(student=None, status=ApplicationStatus.SUBMITTED, **kwargs):
    defaults = dict(
        student=student or make_user(), type=ApplicationType.ADMISSION,
        stream=FundingStream.PSSSP, schema_slug='admission', status=status,
        answers={'course_load': 'full_time', 'confirmed_tuition': '6000',
                 'semester_start': '2026-09-01', 'semester_end': '2026-12-31'},
    )
    confirmed = kwargs.pop('enrolment_confirmed', True)
    defaults.update(kwargs)
    application = Application.objects.create(**defaults)
    # An admission application cannot be forwarded or approved until the
    # institution confirms; these tests are about what is sent, not about
    # that gate, so they start past it.
    if confirmed and application.type in (
            ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING):
        confirm_enrolment(application)
    return application


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
        # Not confirmed: the point of the queue is what is still outstanding.
        application = make_application(enrolment_confirmed=False)
        verification.issue(application, 'registrar@aurora.ca')
        self.assertEqual(
            dashboard.summary(self.staff)['queues']['awaiting_enrolment_confirmation'], 1)

        # Once confirmed it drops off the queue.
        EnrollmentVerification.objects.update(
            status=EnrollmentVerification.Status.COMPLETED)
        self.assertEqual(
            dashboard.summary(self.staff)['queues']['awaiting_enrolment_confirmation'], 0)

    def test_a_decided_application_leaves_the_enrolment_queue(self):
        """A queue with a floor it cannot reach stops being read.

        A registrar who has not answered by the time the office decides never
        will, so the request stays REQUESTED for good. Counted regardless of the
        application, every declined application added one to a work queue
        permanently — the same fault that told the *student* their institution
        was still being waited on after they had been refused.
        """
        for status in (ApplicationStatus.DECLINED, ApplicationStatus.APPROVED,
                       ApplicationStatus.SENT_TO_FINANCE):
            with self.subTest(status=status):
                EnrollmentVerification.objects.all().delete()
                Application.objects.all().delete()
                application = make_application(status=status,
                                               enrolment_confirmed=False)
                verification.issue(application, 'registrar@aurora.ca')
                self.assertEqual(
                    dashboard.summary(self.staff)['queues']
                    ['awaiting_enrolment_confirmation'], 0)

    def test_attention_counts_only_what_can_still_be_acted_on(self):
        """`submitted_late` is an attention item, not a historical tally."""
        make_application(status=ApplicationStatus.SUBMITTED,
                         submitted_after_deadline=True)
        make_application(status=ApplicationStatus.DECLINED,
                         submitted_after_deadline=True)
        make_application(status=ApplicationStatus.APPROVED,
                         submitted_after_deadline=True)

        attention = dashboard.summary(self.staff)['attention']
        self.assertEqual(attention['submitted_late'], 1)

    def test_money_is_split_by_where_it_has_reached(self):
        application = make_application()
        # Approved, because the office's totals are money it has committed to.
        # Priced but undecided, this reported the figure as awarded *and* as
        # awaiting payment, while `finance.preview` — which filters on the
        # application's status — offered nothing. The two screens disagreed
        # about the same money and only the payment file was right.
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.staff)
        workflow.record(application, ApplicationEvent.Action.APPROVED,
                        make_user(Role.DIRECTOR))
        record_decision(application)
        application.refresh_from_db()
        awarded = application.awarded_total

        summary = dashboard.summary(self.staff)
        self.assertEqual(Decimal(summary['money']['awarded']), awarded)
        self.assertEqual(Decimal(summary['money']['awaiting_payment']), awarded)
        self.assertEqual(Decimal(summary['money']['paid']), Decimal('0.00'))

    def test_an_undecided_pricing_is_absent_from_the_office_totals_too(self):
        """The office's figure has to match the payment file's.

        `finance.pending_awards` has always filtered on the application status;
        the dashboard did not, so a priced-but-undecided application inflated
        every total on the staff screen while being correctly absent from the
        run. Both read `Award.objects.awarded()` now.
        """
        from funding.services import finance

        application = make_application()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.staff)
        record_decision(application)

        summary = dashboard.summary(self.staff)
        self.assertEqual(Decimal(summary['money']['awarded']), Decimal('0.00'))
        self.assertEqual(
            {row['award'].application_id for row in finance.preview()[0]}, set())

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
        self.assertGreater(Decimal(money['paid']), Decimal('0.00'))

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

    def test_a_student_who_has_been_paid_is_told_so(self):
        """The 'paid' figure was $0.00 on every account, always.

        Nothing wrote Award.Status.PAID, so the tile beside a six-figure
        awarded total read zero — for a student who had already had their money.
        """
        from funding.services import finance

        BankAccount.objects.create(
            user=self.student, account_holder=self.student.full_name,
            transit_number='12345', institution_number='001',
            account_number='9876543210')
        application = make_application(student=self.student)
        director = make_user(Role.DIRECTOR)
        workflow.record(application, ApplicationEvent.Action.REVIEWED, director)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, director)
        workflow.record(application, ApplicationEvent.Action.APPROVED, director)
        record_decision(application)

        self.assertEqual(
            Decimal(dashboard.summary(self.student)['money']['paid']), Decimal('0.00'))

        finance.dispatch(actor=make_user(Role.FINANCE))

        money = dashboard.summary(self.student)['money']
        self.assertGreater(Decimal(money['paid']), Decimal('0.00'))
        self.assertEqual(Decimal(money['paid']), Decimal(money['awarded']))

    def _approve(self, application):
        """Carry an application to approved, the way the office does."""
        staff = make_user(Role.SUPPORT_WORKER)
        workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
        workflow.record(application, ApplicationEvent.Action.APPROVED,
                        make_user(Role.DIRECTOR))
        application.refresh_from_db()
        return application

    def test_money_counts_only_their_own_awards(self):
        mine = self._approve(make_application(student=self.student))
        record_decision(mine)
        record_decision(self._approve(make_application()))   # somebody else's

        mine.refresh_from_db()
        summary = dashboard.summary(self.student)
        self.assertEqual(Decimal(summary['money']['awarded']), mine.awarded_total)
        self.assertGreater(mine.awarded_total, Decimal('0.00'))

    def test_a_priced_application_nobody_has_decided_is_not_money_yet(self):
        """Reported by the owner against his own test run.

        The office reviewed an application, recorded an award on it, and the
        student's portal showed the amount as though it had been granted —
        before the institution had confirmed the enrolment and before anybody
        had approved anything. Scoping by the current decision was the earlier
        fix for a related fault and only answered half the question: it stopped
        a re-pricing counting twice, and still counted a pricing nobody had
        decided on. A pricing is not a promise.
        """
        priced = make_application(student=self.student)
        workflow.record(priced, ApplicationEvent.Action.REVIEWED,
                        make_user(Role.SUPPORT_WORKER))
        record_decision(priced)
        priced.refresh_from_db()

        self.assertGreater(priced.awarded_total, Decimal('0.00'),
                           'the pricing itself is still recorded')
        summary = dashboard.summary(self.student)
        self.assertEqual(Decimal(summary['money']['awarded']), Decimal('0.00'))
        self.assertEqual(Decimal(summary['recent'][0]['awarded_total']),
                         Decimal('0.00'))

    def test_a_declined_application_stops_reporting_an_award(self):
        """The same fault on the other side, and the worse half of it.

        A student whose application was refused went on being shown the amount
        it had been priced at. The decision is kept — an appeal is argued from
        it — but it is not money, and the portal must not say it is.
        """
        declined = make_application(student=self.student)
        staff = make_user(Role.SUPPORT_WORKER)
        workflow.record(declined, ApplicationEvent.Action.REVIEWED, staff)
        record_decision(declined)
        workflow.record(declined, ApplicationEvent.Action.DECLINED, staff,
                        note='Not an approved programme.')
        declined.refresh_from_db()

        self.assertEqual(declined.status, ApplicationStatus.DECLINED)
        self.assertTrue(declined.decisions.filter(is_current=True).exists(),
                        'the pricing is kept, so an appeal can argue with it')
        self.assertEqual(declined.awarded_amount, Decimal('0.00'))

        summary = dashboard.summary(self.student)
        self.assertEqual(Decimal(summary['money']['awarded']), Decimal('0.00'))
        self.assertEqual(Decimal(summary['recent'][0]['awarded_total']),
                         Decimal('0.00'))

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


class NextStepTests(TestCase):
    """The one thing a student should do next.

    Three totals and nothing else told someone with no applications nothing at
    all — the opening screen read as a report on an empty file rather than a way
    in. These pin what it says instead, in priority order: what the office is
    waiting on from them beats everything, and an empty file is told where to
    start.
    """

    def setUp(self):
        self.student = make_user()

    def step(self):
        return dashboard.summary(self.student)['next_step']

    def test_a_student_with_nothing_is_sent_to_the_admission_application(self):
        self.assertEqual(self.step()['key'], 'apply_admission')
        self.assertEqual(self.step()['href'], '/apply/admission')

    def test_a_request_for_information_outranks_everything_else(self):
        make_application(student=self.student,
                         status=ApplicationStatus.INFO_REQUESTED)
        self.assertEqual(self.step()['key'], 'provide_information')

    def test_an_application_in_review_is_reported_as_such(self):
        make_application(student=self.student, status=ApplicationStatus.UNDER_REVIEW)
        self.assertEqual(self.step()['key'], 'in_review')

    def test_an_outstanding_enrolment_request_is_named_as_the_hold_up(self):
        """Tuition cannot be awarded until the registrar answers, and a student
        with no way to see that is left wondering why nothing is happening."""
        # Opts out of the builder's confirmation: this test is about what an
        # application looks like while the institution has not answered.
        application = make_application(student=self.student,
                                       status=ApplicationStatus.UNDER_REVIEW,
                                       enrolment_confirmed=False)
        verification.issue(application, 'registrar@example.com')

        step = self.step()
        self.assertEqual(step['key'], 'awaiting_enrolment')
        # Nothing for them to do: it must not read as an action they are failing
        # to take.
        self.assertEqual(step['action'], '')

    def test_a_student_whose_work_is_done_is_pointed_at_further_funding(self):
        make_application(student=self.student, status=ApplicationStatus.APPROVED)
        self.assertEqual(self.step()['key'], 'apply_more')

    def test_another_students_application_does_not_decide_this_students_step(self):
        make_application(student=make_user(), status=ApplicationStatus.INFO_REQUESTED)
        self.assertEqual(self.step()['key'], 'apply_admission')

    # ── What a closed application must stop saying ───────────────────────────
    #
    # Reported by the owner: a declined application went on telling the student
    # "Waiting on your institution — nothing is needed from you." The
    # verification is still REQUESTED, because a registrar who never answered
    # never will, and the query asked about the verification without asking what
    # had happened to the application it belonged to. The same shape as the
    # award bug: a related object read without reference to its parent's state.

    def _unanswered(self, status):
        """An application in `status` whose registrar never replied."""
        application = make_application(student=self.student, status=status,
                                       enrolment_confirmed=False)
        verification.issue(application, 'registrar@example.com')
        return application

    def test_a_declined_application_stops_blaming_the_institution(self):
        """The owner's report, isolated to the guard it is about.

        Written as a lone declined admission it passed with the guard removed:
        a declined admission sends the student to `apply_admission` before the
        enrolment check is ever reached, so the test was watching a different
        fix. It needs an admission that is *not* declined to get past that
        branch, and a decided application behind the unanswered request.
        """
        make_application(student=self.student, status=ApplicationStatus.APPROVED)
        declined = make_application(student=self.student,
                                    type=ApplicationType.CONTINUING_FUNDING,
                                    status=ApplicationStatus.DECLINED,
                                    enrolment_confirmed=False)
        verification.issue(declined, 'registrar@example.com')

        step = self.step()
        self.assertNotEqual(step['key'], 'awaiting_enrolment')
        self.assertNotIn('institution', step['title'].lower())

    def test_an_approved_application_stops_blaming_the_institution_too(self):
        """Approval requires a confirmed enrolment, so an outstanding request
        beside an approved application is a stale row and not a hold-up."""
        self._unanswered(ApplicationStatus.APPROVED)
        self.assertNotEqual(self.step()['key'], 'awaiting_enrolment')

    def test_an_open_application_still_names_the_institution(self):
        """The guard must not swallow the case it was written for."""
        self._unanswered(ApplicationStatus.UNDER_REVIEW)
        self.assertEqual(self.step()['key'], 'awaiting_enrolment')

    def test_a_student_told_to_answer_is_not_told_to_wait_instead(self):
        """Priority, with both true at once: a request for information is
        something they can act on and the registrar is not."""
        self._unanswered(ApplicationStatus.UNDER_REVIEW)
        make_application(student=self.student,
                         status=ApplicationStatus.INFO_REQUESTED)
        self.assertEqual(self.step()['key'], 'provide_information')

    def test_a_student_whose_only_admission_was_declined_can_start_again(self):
        """They have no funding and were being pointed at travel and bursaries.

        `apply_more` reads as "you are funded, here is what else there is". To
        somebody who has just been refused it is close to a taunt, and it hides
        the one thing they might actually do.
        """
        make_application(student=self.student, status=ApplicationStatus.DECLINED)
        step = self.step()
        self.assertEqual(step['key'], 'apply_admission')
        self.assertEqual(step['href'], '/apply/admission')

    def test_a_declined_admission_beside_an_approved_one_is_not_a_fresh_start(self):
        """Having been funded, the next step is further funding, not reapplying."""
        make_application(student=self.student, status=ApplicationStatus.DECLINED)
        make_application(student=self.student, status=ApplicationStatus.APPROVED)
        self.assertEqual(self.step()['key'], 'apply_more')

    def test_every_status_produces_a_step_that_can_be_rendered(self):
        """Whatever an application is doing, the screen has something to say.

        A missing key, an empty title, or a href with no action would each
        render as a blank panel on the one screen that exists to tell somebody
        what to do next.
        """
        for status in ApplicationStatus.values:
            with self.subTest(status=status):
                student = make_user()
                make_application(student=student, status=status,
                                 enrolment_confirmed=False)
                step = dashboard.summary(student)['next_step']
                self.assertTrue(step.get('key'), status)
                self.assertTrue(step.get('title'), status)
                self.assertTrue(step.get('detail'), status)
                # An action with nowhere to go, or a link with no label, is a
                # dead control. Both empty is fine: it means "nothing to do".
                self.assertEqual(bool(step.get('action')), bool(step.get('href')),
                                 f'{status}: {step["action"]!r} / {step["href"]!r}')


class StudentPayloadTests(TestCase):

    def setUp(self):
        self.student = make_user()

    def test_recent_applications_are_newest_first_and_capped(self):
        for _ in range(7):
            make_application(student=self.student)

        recent = dashboard.summary(self.student)['recent']

        self.assertEqual(len(recent), 5)
        submitted = [row['submitted_at'] for row in recent]
        self.assertEqual(submitted, sorted(submitted, reverse=True))

    def test_recent_holds_only_this_students_applications(self):
        make_application(student=make_user())
        self.assertEqual(dashboard.summary(self.student)['recent'], [])

    def test_the_student_reference_is_carried_for_the_header(self):
        self.student.beneficiary_number = 'B-2001'
        self.student.save(update_fields=['beneficiary_number'])
        self.assertEqual(
            dashboard.summary(self.student)['student']['reference'], 'B-2001')

    def test_no_deadlines_set_yields_an_empty_list_rather_than_invented_dates(self):
        self.assertEqual(dashboard.summary(self.student)['deadlines'], [])


class StudentDashboardCostTests(TestCase):
    """The student screen gained a next step, recent activity and deadlines.

    Each of those is a chance to reintroduce the behaviour this whole rewrite
    removed: a dashboard whose cost grows with how much data exists. The screen
    it replaces pulled every application with every answer and counted them in
    the browser.
    """

    def setUp(self):
        self.student = make_user()

    def test_the_cost_does_not_grow_with_the_number_of_applications(self):
        for _ in range(3):
            make_application(student=self.student)
        with CaptureQueriesContext(connection) as few:
            dashboard.summary(self.student)

        for _ in range(40):
            make_application(student=self.student)
        with CaptureQueriesContext(connection) as many:
            dashboard.summary(self.student)

        self.assertEqual(
            len(many), len(few),
            f'{len(few)} queries for 3 applications, {len(many)} for 43',
        )

    def test_the_whole_screen_is_a_handful_of_queries(self):
        for _ in range(5):
            make_application(student=self.student)
        with CaptureQueriesContext(connection) as queries:
            dashboard.summary(self.student)
        self.assertLessEqual(len(queries), 9, [q['sql'] for q in queries])

    def test_recent_activity_does_not_query_once_per_row(self):
        """A serializer reaching for a related object per row is the N+1 this
        replaced."""
        for _ in range(5):
            make_application(student=self.student)
        with CaptureQueriesContext(connection) as five:
            dashboard.summary(self.student)['recent']

        for _ in range(5):
            make_application(student=self.student)
        with CaptureQueriesContext(connection) as ten:
            dashboard.summary(self.student)['recent']

        self.assertEqual(len(ten), len(five))
