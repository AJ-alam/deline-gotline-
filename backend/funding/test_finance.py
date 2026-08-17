"""Sending approved awards to be paid.

The last step in the money path. A mistake here reaches someone's bank account,
or leaves them out of a payment run entirely.
"""

import csv
import io
import itertools
from decimal import Decimal

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import BankAccount, Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType, AuditEntry,
    Award, FundingStream,
)
from funding.services import finance, workflow
from funding.services.decisions import record_decision
from funding.test_rules import seed_rates
from funding.test_fixtures import confirm_enrolment

_counter = itertools.count(1)


def make_user(role=Role.STUDENT, with_account=True):
    user = User.objects.create_user(
        f'f{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name=f'Person{next(_counter)}', role=role,
        beneficiary_number='B-1234',is_deline_beneficiary=True, is_indian_act_registered=True)
    if with_account and role == Role.STUDENT:
        BankAccount.objects.create(
            user=user, account_holder=user.full_name, transit_number='12345',
            institution_number='001', account_number='9876543210',
        )
    return user


def approved_application(student=None, **kwargs):
    """An application carried through review to approved, with awards recorded."""
    student = student or make_user()
    application = Application.objects.create(
        student=student, type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
        schema_slug='admission', status=ApplicationStatus.SUBMITTED,
        answers={
            'course_load': 'full_time', 'confirmed_tuition': '6000',
            'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
        },
        **kwargs,
    )
    staff, director = make_user(Role.SUPPORT_WORKER), make_user(Role.DIRECTOR)
    workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
    # Tuition is funded against the registrar's figure, so nothing reaches the
    # director until the institution has confirmed it.
    confirm_enrolment(application)
    workflow.record(application, ApplicationEvent.Action.FORWARDED, staff)
    workflow.record(application, ApplicationEvent.Action.APPROVED, director)
    record_decision(application, actor=director)
    application.refresh_from_db()
    return application


class SelectionTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def test_only_approved_applications_are_ready_to_pay(self):
        approved_application()
        # A submitted application, priced but not decided, must not be paid.
        pending = Application.objects.create(
            student=make_user(), type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            status=ApplicationStatus.SUBMITTED,
            answers={'course_load': 'full_time', 'confirmed_tuition': '6000',
                     'semester_start': '2026-09-01', 'semester_end': '2026-12-31'},
        )
        record_decision(pending)

        applications = {row['award'].application_id for row in finance.preview()[0]}
        self.assertNotIn(pending.pk, applications)

    def test_an_award_survives_staff_marking_the_application_sent_by_hand(self):
        """The application screen offers 'Send to finance' as the next step on
        anything approved, and pressing it does not dispatch anything.

        Selecting on the *application* status dropped the award out of every
        payment run at that moment, permanently, while it was still PENDING and
        still owed. Nothing reported it: it was not ready, not blocked, just
        absent. The award's own status is what records whether money has left.
        """
        application = approved_application()
        staff = make_user(Role.SUPPORT_WORKER)
        workflow.record(application, ApplicationEvent.Action.SENT_TO_FINANCE, staff)
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.SENT_TO_FINANCE)

        ready, blocked = finance.preview()
        payable = {row['award'].application_id for row in ready}
        self.assertIn(
            application.pk, payable,
            'an approved, unpaid award vanished from the payment run',
        )
        self.assertEqual(blocked, [])

    def test_an_award_already_paid_is_not_offered_again(self):
        """The counterpart: the award's status, not the application's, is what
        stops a second payment."""
        approved_application()
        finance.dispatch()
        ready, blocked = finance.preview()
        self.assertEqual((ready, blocked), ([], []))

    def test_a_student_with_no_bank_account_is_reported_not_dropped(self):
        """A missing row in a finance file is a person who does not get paid."""
        approved_application(student=make_user(with_account=False))
        ready, blocked = finance.preview()

        self.assertEqual(ready, [])
        self.assertTrue(blocked)
        self.assertIn('no bank account', blocked[0]['reason'])

    def test_nothing_to_send_is_refused_rather_than_producing_an_empty_file(self):
        with self.assertRaises(finance.DispatchError):
            finance.dispatch()


class DispatchTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.finance_officer = make_user(Role.FINANCE)

    def test_dispatch_marks_every_award_paid(self):
        application = approved_application()
        result = finance.dispatch(actor=self.finance_officer)

        self.assertGreater(result['count'], 0)
        self.assertGreater(result['total'], Decimal('0'))
        for award in application.awards.all():
            self.assertEqual(award.status, Award.Status.PAID)
            self.assertIsNotNone(award.sent_to_finance_at)
            self.assertEqual(award.sent_to_finance_by, self.finance_officer)

    def test_dispatched_money_is_money_paid(self):
        """The status is not the point; what reads it is.

        `Award.objects.paid()` is what every 'how much has actually gone out'
        figure is built on, including the student's own dashboard. Nothing wrote
        PAID, so it answered nothing on every database, and the dashboard
        reported $0.00 paid beside an awarded total in the millions. Asserted
        through the queryset rather than the column, because the column being
        right is only interesting if the reader finds it.
        """
        application = approved_application()
        self.assertFalse(Award.objects.paid().exists())

        finance.dispatch(actor=self.finance_officer)

        paid = Award.objects.paid().filter(application=application)
        self.assertEqual(paid.count(), application.awards.count())
        self.assertEqual(
            paid.aggregate(total=Sum('amount'))['total'],
            application.awards.aggregate(total=Sum('amount'))['total'],
        )

    def test_an_award_is_never_sent_twice(self):
        approved_application()
        finance.dispatch(actor=self.finance_officer)

        with self.assertRaises(finance.DispatchError):
            finance.dispatch(actor=self.finance_officer)

    def test_the_application_follows_its_awards_through_the_workflow(self):
        application = approved_application()
        finance.dispatch(actor=self.finance_officer)

        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.SENT_TO_FINANCE)
        # Recorded as an event, not assigned — the history stays complete.
        self.assertTrue(application.events.filter(
            action=ApplicationEvent.Action.SENT_TO_FINANCE).exists())

    def test_a_dispatch_is_audited(self):
        approved_application()
        finance.dispatch(actor=self.finance_officer)

        entry = AuditEntry.objects.get(action='finance.dispatched')
        self.assertEqual(entry.actor, self.finance_officer)
        self.assertIn('totalling', entry.detail)

    def test_a_blocked_student_is_left_pending_and_kept_out_of_the_file(self):
        """The payable award goes; the unpayable one waits rather than being
        written into a file with no account to pay into."""
        payable = approved_application()
        unpayable = approved_application(student=make_user(with_account=False))

        result = finance.dispatch(actor=self.finance_officer)

        for award in payable.awards.all():
            self.assertEqual(award.status, Award.Status.PAID)
        for award in unpayable.awards.all():
            self.assertEqual(award.status, Award.Status.PENDING)
            self.assertIsNone(award.sent_to_finance_at)

        self.assertIn(payable.student.full_name, result['csv'])
        self.assertNotIn(unpayable.student.full_name, result['csv'])

        # And the blocked application has not moved on as though it were paid.
        unpayable.refresh_from_db()
        self.assertEqual(unpayable.status, ApplicationStatus.APPROVED)
        self.assertTrue(result['blocked'])

    def test_a_blocked_award_can_be_sent_once_the_account_is_added(self):
        application = approved_application(student=make_user(with_account=False))
        with self.assertRaises(finance.DispatchError):
            finance.dispatch(actor=self.finance_officer)

        BankAccount.objects.create(
            user=application.student, account_holder='Later Added',
            transit_number='54321', institution_number='002',
            account_number='1122334455',
        )
        result = finance.dispatch(actor=self.finance_officer)
        self.assertGreater(result['count'], 0)
        self.assertIn('1122334455', result['csv'])

    def test_the_total_matches_the_awards_actually_sent(self):
        first = approved_application()
        second = approved_application()
        result = finance.dispatch(actor=self.finance_officer)

        expected = sum(
            (a.amount for app in (first, second) for a in app.awards.all()),
            Decimal('0.00'),
        )
        self.assertEqual(result['total'], expected)


class CsvTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.application = approved_application()

    def _rows(self):
        result = finance.dispatch(actor=make_user(Role.FINANCE))
        return list(csv.DictReader(io.StringIO(result['csv'])))

    def test_one_row_per_award_line_not_one_lump_per_student(self):
        """Finance reconciles against categories; a lump sum cannot be traced
        back to the rule that produced it."""
        rows = self._rows()
        self.assertEqual(len(rows), self.application.awards.count())
        self.assertGreater(len(rows), 1)

    def test_the_file_carries_what_finance_needs_to_pay_someone(self):
        row = self._rows()[0]
        self.assertEqual(row['Transit'], '12345')
        self.assertEqual(row['Institution'], '001')
        self.assertEqual(row['Account number'], '9876543210')
        self.assertEqual(row['Beneficiary number'], 'B-1234')
        self.assertTrue(row['Approved on'])

    def test_amounts_are_written_to_the_cent(self):
        for row in self._rows():
            self.assertRegex(row['Amount'], r'^\d+\.\d{2}$')

    def test_every_row_names_the_award_category(self):
        for row in self._rows():
            self.assertTrue(row['Award'])
            self.assertTrue(row['Reference'])


class EndpointTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.application = approved_application()
        self.officer = make_user(Role.FINANCE)
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.student = make_user()

    def test_finance_can_see_what_is_ready(self):
        self.client.force_authenticate(self.officer)
        response = self.client.get('/api/finance/pending/')

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.data['count'], 0)
        self.assertGreater(Decimal(response.data['total']), 0)

    def test_a_support_worker_cannot_reach_the_payment_run(self):
        self.client.force_authenticate(self.worker)
        self.assertEqual(self.client.get('/api/finance/pending/').status_code, 403)

    def test_a_student_cannot_reach_the_payment_run(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post('/api/finance/dispatch/').status_code, 403)

    def test_dispatch_returns_the_file(self):
        self.client.force_authenticate(self.officer)
        response = self.client.post('/api/finance/dispatch/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('Account number', response.content.decode())

    def test_dispatching_nothing_explains_why(self):
        finance.dispatch(actor=self.officer)
        self.client.force_authenticate(self.officer)
        response = self.client.post('/api/finance/dispatch/')

        self.assertEqual(response.status_code, 409)
        self.assertIn('nothing ready', response.data['detail'].lower())
