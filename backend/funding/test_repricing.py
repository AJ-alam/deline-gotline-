"""What happens to the money when an application is priced more than once.

`AwardDecision` supersedes rather than overwrites, so an appeal can be argued
against the figures that were in force. The `Award` rows that decision produced
are kept for the same reason.

Which means every query that adds up awards has to say which decision it means.
The ones that did not: a student approved once for $2,000 saw $4,000 on their
dashboard the moment anybody re-priced their application, the office's totals
were inflated by the same amount, and — worst — the payment run offered both
sets of rows, so the money would have gone out twice.

`Application.awarded_total` was right throughout, which is exactly why this was
hard to see: the application said $2,000 and the dashboard above it said $4,000.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationType, Award, AwardDecision,
    FundingStream, PolicySetting,
)
from funding.services import dashboard, decisions, finance, workflow

AWARDED = Decimal('2000.00')


def make_user(role=Role.STUDENT, email=None, with_account=False):
    user = User.objects.create_user(
        email or f'{role}@repricing.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)
    if with_account:
        user.bank_accounts.create(
            account_holder=user.full_name, transit_number='12345',
            institution_number='001', account_number='9876543210')
    return user


class RepricingTests(TestCase):
    """One application, approved once, priced twice."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='emergency_relief', key='max_per_student',
            defaults=dict(label='cap', value=Decimal('5000'), unit='$'))
        self.student = make_user(email='hammad@repricing.test', with_account=True)
        self.director = make_user(Role.DIRECTOR, 'director@repricing.test')

        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.EMERGENCY_RELIEF,
            stream=FundingStream.DGGR, schema_slug='emergency_relief',
            answers={'amount_requested': str(AWARDED)})
        for action in (ApplicationEvent.Action.SUBMITTED,
                       ApplicationEvent.Action.REVIEWED,
                       ApplicationEvent.Action.FORWARDED,
                       ApplicationEvent.Action.APPROVED):
            workflow.record(self.application, action, self.director)

    def price(self, times=1):
        for _ in range(times):
            decisions.record_decision(self.application, actor=self.director)
        self.application.refresh_from_db()

    # ── Priced once: the baseline every assertion below is measured against ──

    def test_priced_once_the_application_says_what_was_awarded(self):
        self.price()
        self.assertEqual(self.application.awarded_total, AWARDED)

    def test_priced_once_the_student_dashboard_agrees(self):
        self.price()
        self.assertEqual(
            Decimal(dashboard.for_student(self.student)['money']['awarded']), AWARDED)

    # ── Priced twice: same award, and the office may re-price for any reason ──

    def test_the_application_still_says_what_was_awarded(self):
        """It was always right. The second decision replaces the first."""
        self.price(times=2)
        self.assertEqual(self.application.awarded_total, AWARDED)

    def test_only_one_decision_is_current(self):
        self.price(times=2)
        self.assertEqual(
            AwardDecision.objects.filter(application=self.application,
                                         is_current=True).count(), 1)

    def test_the_superseded_decision_is_kept(self):
        """Not a leak — an appeal argues against the figures that were in
        force, so the old decision and its lines stay."""
        self.price(times=2)
        self.assertEqual(
            AwardDecision.objects.filter(application=self.application).count(), 2)
        self.assertEqual(Award.objects.filter(application=self.application).count(), 2)

    def test_the_student_dashboard_does_not_double(self):
        """The reported symptom: approved for $2,000, dashboard said $4,000."""
        self.price(times=2)
        self.assertEqual(
            Decimal(dashboard.for_student(self.student)['money']['awarded']), AWARDED)

    def test_the_office_dashboard_does_not_double(self):
        self.price(times=2)
        self.assertEqual(
            Decimal(dashboard.for_staff(self.director)['money']['awarded']), AWARDED)

    def test_the_dashboard_agrees_with_the_application_it_lists(self):
        """The two figures a student sees on one screen. Whatever the number,
        these must be the same number."""
        self.price(times=2)
        money = dashboard.for_student(self.student)['money']['awarded']
        self.assertEqual(Decimal(money), self.application.awarded_total)

    def test_the_payment_run_offers_the_money_once(self):
        """The one that is not a display bug. Two pending rows for one award is
        the money going out twice."""
        self.price(times=2)
        ready, _blocked = finance.preview()
        rows = [row for row in ready
                if row['award'].application_id == self.application.pk]
        self.assertEqual(len(rows), 1, 'the payment run would pay this twice')
        self.assertEqual(rows[0]['award'].amount, AWARDED)

    def test_the_payment_file_totals_what_was_awarded(self):
        self.price(times=2)
        ready, _blocked = finance.preview()
        total = sum(row['award'].amount for row in ready
                    if row['award'].application_id == self.application.pk)
        self.assertEqual(total, AWARDED)

    def test_pricing_five_times_changes_nothing(self):
        """Whatever number of times somebody presses the button."""
        self.price(times=5)
        self.assertEqual(
            Decimal(dashboard.for_student(self.student)['money']['awarded']), AWARDED)
        ready, _blocked = finance.preview()
        self.assertEqual(
            len([row for row in ready
                 if row['award'].application_id == self.application.pk]), 1)


class PaidAwardTests(TestCase):
    """Money that has already gone out is not un-counted by a re-price.

    The awarded total follows the current decision; what was *paid* is a fact
    about the bank, and filtering it by which decision is current now would hide
    a payment that really happened.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='emergency_relief', key='max_per_student',
            defaults=dict(label='cap', value=Decimal('5000'), unit='$'))
        self.student = make_user(email='paid@repricing.test', with_account=True)
        self.director = make_user(Role.DIRECTOR, 'director2@repricing.test')
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.EMERGENCY_RELIEF,
            stream=FundingStream.DGGR, schema_slug='emergency_relief',
            answers={'amount_requested': str(AWARDED)})
        for action in (ApplicationEvent.Action.SUBMITTED,
                       ApplicationEvent.Action.REVIEWED,
                       ApplicationEvent.Action.FORWARDED,
                       ApplicationEvent.Action.APPROVED):
            workflow.record(self.application, action, self.director)

    def _paid_once(self):
        decisions.record_decision(self.application, actor=self.director)
        paid = Award.objects.get(application=self.application)
        paid.status = Award.Status.PAID
        paid.save(update_fields=['status'])
        return paid

    def test_a_paid_award_cannot_be_priced_again(self):
        """The serious one, and it was a passing test that said otherwise.

        Re-pricing supersedes the current decision and writes a fresh set of
        lines, and a fresh line is PENDING. `finance.pending_awards()` selects
        PENDING lines on the current decision of an application in a payable
        status — and `sent_to_finance` is payable. So re-pricing a dispatched
        award put every dollar of it back in the payment file.

        The test below used to re-price a paid award and assert that the run
        offered exactly one row, reading "one" as "not twice". The one row was
        the *new* decision's line, for money that had already gone out; the
        paid line was excluded only because it was PAID. It was measuring the
        double payment and calling it correct.

        `record_manual_decision` has always refused this. `record_decision` —
        the path the "Record award" button takes — did not.
        """
        self._paid_once()

        with self.assertRaises(decisions.AlreadyPaidError):
            decisions.record_decision(self.application, actor=self.director)

    def test_a_payment_made_under_a_superseded_decision_is_still_reported(self):
        """Superseding by any other route must not un-count what was paid."""
        self._paid_once()

        self.assertEqual(
            Decimal(dashboard.for_student(self.student)['money']['paid']), AWARDED,
            'money that left the bank stopped being reported as paid')

    def test_and_is_not_offered_to_the_payment_run_again(self):
        self._paid_once()

        with self.assertRaises(decisions.AlreadyPaidError):
            decisions.record_decision(self.application, actor=self.director)

        ready, _blocked = finance.preview()
        rows = [row for row in ready
                if row['award'].application_id == self.application.pk]
        self.assertEqual(rows, [],
                         'money already paid was offered to the run a second time')


class OrphanedAwardTests(TestCase):
    """An award with no decision behind it is reported, never dropped.

    Scoping the payment run to the decision in force fixed the money going out
    twice. It also means an award whose decision link is missing is filtered
    out — and a filtered-out award is money that silently stops existing.

    Nothing creates one: `record_decision` is the only writer of an Award and it
    always sets the decision. That is a reason to expect none, not a reason to
    let one disappear.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='emergency_relief', key='max_per_student',
            defaults=dict(label='cap', value=Decimal('5000'), unit='$'))
        self.student = make_user(email='orphan@repricing.test', with_account=True)
        self.director = make_user(Role.DIRECTOR, 'director3@repricing.test')
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.EMERGENCY_RELIEF,
            stream=FundingStream.DGGR, schema_slug='emergency_relief',
            answers={'amount_requested': str(AWARDED)})
        for action in (ApplicationEvent.Action.SUBMITTED,
                       ApplicationEvent.Action.REVIEWED,
                       ApplicationEvent.Action.FORWARDED,
                       ApplicationEvent.Action.APPROVED):
            workflow.record(self.application, action, self.director)

    def test_the_only_writer_of_an_award_always_attaches_a_decision(self):
        decisions.record_decision(self.application, actor=self.director)
        self.assertFalse(
            Award.objects.filter(decision__isnull=True).exists(),
            'an award was created without a decision behind it')

    def test_an_orphaned_award_is_blocked_with_a_reason_rather_than_dropped(self):
        decisions.record_decision(self.application, actor=self.director)
        Award.objects.filter(application=self.application).update(decision=None)

        ready, blocked = finance.preview()
        self.assertNotIn(self.application.pk,
                         [row['award'].application_id for row in ready])
        reasons = [row['reason'] for row in blocked
                   if row['award'].application_id == self.application.pk]
        self.assertEqual(len(reasons), 1, 'the award vanished from the run entirely')
        self.assertIn('not attached to a pricing decision', reasons[0])
