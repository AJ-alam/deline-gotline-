"""What a pre-launch purge removes, and — the part that matters — what it does not.

The database this was written against held 1,516 applications, 3,196 queued
emails and 338 accounts the live audit scripts had invented. Emptying it before
the office takes real applications is a one-line query away from also emptying
the policy rates, the published rule set and the account that administers the
site, and none of those announce their absence: a missing rate reads as $0.00,
and a deleted administrator is only noticed by someone trying to log in.

So most of these tests assert survival rather than deletion.
"""

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import BankAccount, EnrolmentProfile, Role, User
from funding.models import (
    ApplicantIdentifier, Application, ApplicationDeadline, ApplicationEvent,
    ApplicationStatus, ApplicationType, AuditEntry, Award, AwardDecision,
    AwardRepayment, EnrollmentVerification, FundingStream, PolicyChange,
    PolicySetting, ReportedCost, Rule, RuleSet, SupportingDocument,
)
from core import purge
from notifications.models import Notification, OutboundEmail


class PurgeTestCase(TestCase):
    """One database with a bit of everything in it."""

    def setUp(self):
        # ── People ──
        self.owner = User.objects.create_user(
            email='owner@gmail.com', password='x', first_name='Real', last_name='Person')
        self.test_student = User.objects.create_user(
            email='surface.0817194227@example.com', password='x',
            first_name='Audit', last_name='Script')
        # On a throwaway domain and still the administrator. Deleting this
        # account by matching the domain locks the office out of its own portal.
        self.admin = User.objects.create_user(
            email='admin@dgg.test', password='x', first_name='Site', last_name='Admin')
        self.admin.role = Role.ADMIN
        self.admin.is_staff = True
        self.admin.save()

        EnrolmentProfile.objects.create(user=self.owner, institution_name='Aurora College')
        EnrolmentProfile.objects.create(user=self.test_student, institution_name='Nowhere')
        BankAccount.objects.create(
            user=self.owner, account_holder='Real Person', transit_number='12345',
            institution_number='001', account_number='9876543')
        BankAccount.objects.create(
            user=self.test_student, account_holder='Audit Script', transit_number='00000',
            institution_number='000', account_number='0000000')

        # ── Office configuration ──
        self.setting = PolicySetting.objects.create(
            section='psssp', key='tuition_max', label='Tuition maximum',
            value=Decimal('5000.00'), unit='per semester')
        PolicyChange.objects.create(
            setting=self.setting, previous_value=Decimal('7000.00'),
            new_value=Decimal('5000.00'), effective_date=date(2026, 8, 17))
        ApplicationDeadline.objects.create(
            stream=FundingStream.PSSSP, academic_year='2026-2027', semester='fall',
            closes_at=timezone.now() + timedelta(days=30))
        self.rule_set = RuleSet.objects.create(
            name='Policy rates', version=1, status=RuleSet.Status.PUBLISHED,
            effective_from=date(2026, 8, 1))
        Rule.objects.create(
            rule_set=self.rule_set, code='psssp_tuition', description='Tuition',
            condition={}, effect={}, category='tuition', order=1)
        ReportedCost.objects.create(
            fiscal_year_start=date(2026, 4, 1), label='Administration — Staff Wages',
            amount=Decimal('120000.00'))

        # ── Case data ──
        self.application = Application.objects.create(
            type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
            status=ApplicationStatus.SUBMITTED, student=self.test_student,
            schema_slug='admission', answers={'institution_name': 'Nowhere'})
        ApplicationEvent.objects.create(
            application=self.application, action=ApplicationEvent.Action.SUBMITTED)
        ApplicantIdentifier.objects.create(
            application=self.application, ciphertext='xxx', last_three='789')
        EnrollmentVerification.objects.create(
            application=self.application, registrar_email='registrar@nowhere.test',
            token='tok-1', expires_at=timezone.now() + timedelta(days=14))
        self.decision = AwardDecision.objects.create(
            application=self.application, rule_set=self.rule_set, rule_set_version=1,
            total=Decimal('5000.00'))
        self.award = Award.objects.create(
            application=self.application, decision=self.decision,
            category=Award.Category.TUITION, amount=Decimal('5000.00'))
        AwardRepayment.objects.create(
            award=self.award, amount=Decimal('100.00'), reason='withdrew',
            repaid_on=date(2026, 8, 20))
        SupportingDocument.objects.create(
            application=self.application, owner=self.test_student,
            file='documents/2026/08/x.pdf', original_name='transcript.pdf')
        # A graduation claim filed by someone with no account: reachable from
        # no application and no owner, so no cascade would ever reach it.
        self.guest_document = SupportingDocument.objects.create(
            file='documents/2026/08/guest.pdf', original_name='diploma.pdf')

        AuditEntry.objects.create(
            actor=self.admin, action='application.priced', application=self.application)
        self.office_audit = AuditEntry.objects.create(
            actor=self.admin, action='policy.rate_changed', detail='tuition_max 7000 -> 5000')

        Notification.objects.create(
            user=self.test_student, title='Received', message='We have your application.')
        OutboundEmail.objects.create(
            to_email='surface.0817194227@example.com', subject='Received',
            body_html='<p>hi</p>')


class WhatGoes(PurgeTestCase):

    def test_the_application_and_everything_hanging_off_it(self):
        purge.purge()

        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(ApplicationEvent.objects.count(), 0)
        self.assertEqual(ApplicantIdentifier.objects.count(), 0)
        self.assertEqual(EnrollmentVerification.objects.count(), 0)
        self.assertEqual(AwardDecision.objects.count(), 0)
        self.assertEqual(Award.objects.count(), 0)
        self.assertEqual(AwardRepayment.objects.count(), 0)
        self.assertEqual(SupportingDocument.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_the_guest_document_no_cascade_could_reach(self):
        purge.purge()
        self.assertFalse(
            SupportingDocument.objects.filter(pk=self.guest_document.pk).exists())

    def test_the_outbox_by_default(self):
        purge.purge()
        self.assertEqual(OutboundEmail.objects.count(), 0)

    def test_the_outbox_is_left_alone_when_asked(self):
        purge.purge(purge_outbox=False)
        self.assertEqual(OutboundEmail.objects.count(), 1)

    def test_audit_entries_about_an_application_rather_than_all_of_them(self):
        """SET_NULL would leave these as entries about nothing.

        The office's own history — a rate change, a staff account created — is
        not case data and stays.
        """
        purge.purge()

        self.assertEqual(AuditEntry.objects.count(), 1)
        self.assertTrue(AuditEntry.objects.filter(pk=self.office_audit.pk).exists())


class WhatSurvives(PurgeTestCase):

    def test_every_account_when_test_accounts_are_not_dropped(self):
        purge.purge()
        self.assertEqual(User.objects.count(), 3)

    def test_profiles_and_banking_of_a_kept_account(self):
        purge.purge()

        self.assertTrue(EnrolmentProfile.objects.filter(user=self.owner).exists())
        self.assertTrue(BankAccount.objects.filter(user=self.owner).exists())

    def test_the_office_configuration(self):
        purge.purge(drop_test_accounts=True)

        self.assertEqual(PolicySetting.objects.count(), 1)
        self.assertEqual(PolicyChange.objects.count(), 1)
        self.assertEqual(ApplicationDeadline.objects.count(), 1)
        self.assertEqual(RuleSet.objects.count(), 1)
        self.assertEqual(Rule.objects.count(), 1)
        self.assertEqual(ReportedCost.objects.count(), 1)

    def test_the_rate_is_still_the_rate(self):
        """A rate read as 0.00 is indistinguishable from a real $0 award."""
        purge.purge(drop_test_accounts=True)

        self.setting.refresh_from_db()
        self.assertEqual(self.setting.value, Decimal('5000.00'))


class DroppingTestAccounts(PurgeTestCase):

    def test_a_student_on_a_throwaway_domain_goes(self):
        purge.purge(drop_test_accounts=True)
        self.assertFalse(User.objects.filter(pk=self.test_student.pk).exists())

    def test_a_real_address_stays(self):
        purge.purge(drop_test_accounts=True)
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())

    def test_an_administrator_on_a_throwaway_domain_stays(self):
        """admin@dgg.test matches the domain and administers the site."""
        purge.purge(drop_test_accounts=True)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_their_profile_and_banking_go_with_them(self):
        purge.purge(drop_test_accounts=True)

        self.assertEqual(EnrolmentProfile.objects.count(), 1)
        self.assertEqual(BankAccount.objects.count(), 1)
        self.assertEqual(EnrolmentProfile.objects.get().user, self.owner)

    def test_domains_can_be_overridden(self):
        purge.purge(drop_test_accounts=True, test_domains=('gmail.com',))

        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.test_student.pk).exists())


class SurveyWritesNothing(PurgeTestCase):

    def test_counts_without_deleting(self):
        report = purge.survey(drop_test_accounts=True)

        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(OutboundEmail.objects.count(), 1)
        self.assertEqual(User.objects.count(), 3)
        self.assertTrue(report.dry_run)

    def test_it_reports_what_purge_would_remove(self):
        report = purge.survey(drop_test_accounts=True)

        self.assertEqual(report.counts['Application'], 1)
        self.assertEqual(report.counts['Award'], 1)
        self.assertEqual(report.counts['SupportingDocument'], 2)
        self.assertEqual(report.counts['AuditEntry (application-scoped)'], 1)
        self.assertEqual(report.counts['User (test accounts)'], 1)
        self.assertEqual(report.users_deleted, ['surface.0817194227@example.com'])
        self.assertEqual(report.users_kept, ['admin@dgg.test', 'owner@gmail.com'])


class TheCommand(PurgeTestCase):

    def run_command(self, *args):
        out = StringIO()
        call_command('purge_applications', *args, stdout=out)
        return out.getvalue()

    def test_without_yes_it_reports_and_writes_nothing(self):
        output = self.run_command('--drop-test-accounts')

        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(User.objects.count(), 3)
        self.assertIn('Would delete', output)
        self.assertIn('Re-run with --yes', output)

    def test_with_yes_it_deletes(self):
        output = self.run_command('--drop-test-accounts', '--yes')

        self.assertEqual(Application.objects.count(), 0)
        self.assertFalse(User.objects.filter(pk=self.test_student.pk).exists())
        self.assertIn('Deleted', output)

    def test_it_names_the_database_it_is_pointed_at(self):
        """Run twice against two databases; the difference is an env var."""
        output = self.run_command()
        self.assertIn('Target:', output)
        self.assertIn('Database:', output)

    def test_it_warns_that_the_files_stay(self):
        output = self.run_command()
        self.assertIn('never the files', output)

    def test_keep_outbox_is_honoured(self):
        self.run_command('--keep-outbox', '--yes')
        self.assertEqual(OutboundEmail.objects.count(), 1)


class KeepListTestCase(PurgeTestCase):
    """The office with a full complement of staff. Fixture only, no tests.

    Split out so the four classes below inherit a database and not each
    other's assertions — subclassing a class that carries tests re-runs every
    one of them per subclass, which is a suite that grows fast and proves
    nothing extra.
    """

    def setUp(self):
        super().setUp()
        self.director = User.objects.create_user(
            email='director@dgg.test', password='x', first_name='The', last_name='Director')
        self.director.role = Role.DIRECTOR
        self.director.is_staff = True
        self.director.save()
        self.worker = User.objects.create_user(
            email='worker@dgg.test', password='x', first_name='Support', last_name='Worker')
        self.worker.role = Role.SUPPORT_WORKER
        self.worker.is_staff = True
        self.worker.save()
        self.keep = ('admin@dgg.test', 'director@dgg.test')


class KeepingOnlyNamedAccounts(KeepListTestCase):
    """`keep_emails` deletes everyone unnamed, staff included.

    The blunt instrument, for the cut-over: a database that has been tested
    against becoming the one the office signs into. `drop_test_accounts`
    reasons about which addresses are throwaway and protects staff on
    principle; this does neither, so the guards around it are the tests that
    matter most here.
    """

    def test_staff_who_are_not_named_are_deleted(self):
        """The whole point, and the thing `drop_test_accounts` refuses to do."""
        purge.purge(keep_emails=self.keep)
        self.assertFalse(User.objects.filter(email='worker@dgg.test').exists())

    def test_a_real_student_who_is_not_named_is_deleted(self):
        """`owner@gmail.com` is on no throwaway domain and still goes."""
        purge.purge(keep_emails=self.keep)
        self.assertFalse(User.objects.filter(email='owner@gmail.com').exists())

    def test_exactly_the_named_accounts_survive(self):
        purge.purge(keep_emails=self.keep)
        self.assertEqual(
            sorted(User.objects.values_list('email', flat=True)),
            ['admin@dgg.test', 'director@dgg.test'],
        )

    def test_the_address_is_matched_without_regard_to_case(self):
        """Deleting the administrator over a capital letter is not defensible."""
        purge.purge(keep_emails=('ADMIN@DGG.TEST', 'Director@DGG.test'))
        self.assertEqual(User.objects.count(), 2)

    def test_profiles_and_banking_of_a_deleted_account_go_with_them(self):
        purge.purge(keep_emails=self.keep)
        self.assertEqual(EnrolmentProfile.objects.count(), 0)
        self.assertEqual(BankAccount.objects.count(), 0)

    def test_the_office_configuration_still_survives(self):
        """The keep list is about people. It must not reach the rates."""
        purge.purge(keep_emails=self.keep)
        self.assertEqual(PolicySetting.objects.count(), 1)
        self.assertEqual(PolicyChange.objects.count(), 1)
        self.assertEqual(RuleSet.objects.count(), 1)
        self.assertEqual(Rule.objects.count(), 1)
        self.assertEqual(ReportedCost.objects.count(), 1)
        self.assertEqual(ApplicationDeadline.objects.count(), 1)


class TheKeepListRefusals(KeepListTestCase):
    """Every refusal, and that nothing was deleted on the way to raising it."""

    def test_an_address_matching_nothing_is_refused(self):
        """A typo matches no row and would quietly delete what it meant to keep."""
        with self.assertRaises(purge.PurgeRefused) as caught:
            purge.purge(keep_emails=('admin@dgg.test', 'directer@dgg.test'))
        self.assertIn('directer@dgg.test', str(caught.exception))

    def test_a_refused_keep_list_deletes_nothing(self):
        """The guard runs in `survey`, before the first delete rather than partway through."""
        with self.assertRaises(purge.PurgeRefused):
            purge.purge(keep_emails=('nobody@nowhere.test',))
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(Notification.objects.count(), 1)

    def test_an_empty_keep_list_is_refused(self):
        """Not read as 'keep nobody': that empties the portal in one flag."""
        with self.assertRaises(purge.PurgeRefused):
            purge.purge(keep_emails=('', '   '))

    def test_a_keep_list_with_no_administrator_is_refused(self):
        """Nothing inside the portal can create the next administrator."""
        with self.assertRaises(purge.PurgeRefused) as caught:
            purge.purge(keep_emails=('director@dgg.test',))
        self.assertIn('administrator', str(caught.exception))

    def test_a_superuser_counts_as_an_administrator(self):
        """The check is on the surviving row, not on the role name alone."""
        root = User.objects.create_user(email='root@dgg.test', password='x')
        root.is_superuser = True
        root.save()
        purge.purge(keep_emails=('root@dgg.test',))
        self.assertEqual(sorted(User.objects.values_list('email', flat=True)),
                         ['root@dgg.test'])

    def test_an_inactive_administrator_does_not_count(self):
        """A deactivated account cannot sign in to make the next one."""
        self.admin.is_active = False
        self.admin.save()
        with self.assertRaises(purge.PurgeRefused):
            purge.purge(keep_emails=self.keep)

    def test_asking_for_both_mechanisms_is_refused(self):
        """One protects staff on principle, the other deletes them. Not both."""
        with self.assertRaises(purge.PurgeRefused):
            purge.purge(keep_emails=self.keep, drop_test_accounts=True)


class AttributionOnKeptHistory(KeepListTestCase):
    """Office history survives the account that made it, and says so."""

    def setUp(self):
        super().setUp()
        # The worker is about to be deleted, and their name is on office
        # history the purge keeps.
        PolicyChange.objects.update(changed_by=self.worker)
        RuleSet.objects.update(created_by=self.worker)
        ReportedCost.objects.update(recorded_by=self.worker)
        AuditEntry.objects.filter(pk=self.office_audit.pk).update(actor=self.worker)

    def test_the_history_row_survives_with_nobody_on_it(self):
        purge.purge(keep_emails=self.keep)
        change = PolicyChange.objects.get()
        self.assertIsNone(change.changed_by)
        self.assertEqual(change.new_value, Decimal('5000.00'))

    def test_the_office_audit_entry_survives_its_actor(self):
        purge.purge(keep_emails=self.keep)
        entry = AuditEntry.objects.get(pk=self.office_audit.pk)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.action, 'policy.rate_changed')

    def test_the_loss_is_counted_rather_than_silent(self):
        """A SET_NULL that nobody reports is a column quietly emptying itself."""
        report = purge.survey(keep_emails=self.keep)
        self.assertEqual(report.attributions_cleared['PolicyChange.changed_by'], 1)
        self.assertEqual(report.attributions_cleared['RuleSet.created_by'], 1)
        self.assertEqual(report.attributions_cleared['ReportedCost.recorded_by'], 1)
        self.assertEqual(
            report.attributions_cleared['AuditEntry.actor (not about an application)'], 1)

    def test_a_kept_accounts_attribution_is_not_counted(self):
        """Only the accounts actually going. The admin stays and keeps their name."""
        AuditEntry.objects.filter(pk=self.office_audit.pk).update(actor=self.admin)
        report = purge.survey(keep_emails=self.keep)
        self.assertEqual(
            report.attributions_cleared['AuditEntry.actor (not about an application)'], 0)


class TheKeepOnlyFlag(KeepListTestCase):
    """The command surface: reports first, refuses loudly, names every account."""

    def run_command(self, *args):
        out = StringIO()
        call_command('purge_applications', *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_without_yes_it_writes_nothing(self):
        self.run_command('--keep-only=admin@dgg.test,director@dgg.test')
        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(Application.objects.count(), 1)

    def test_with_yes_it_deletes(self):
        self.run_command('--keep-only=admin@dgg.test,director@dgg.test', '--yes')
        self.assertEqual(sorted(User.objects.values_list('email', flat=True)),
                         ['admin@dgg.test', 'director@dgg.test'])

    def test_it_names_every_account_it_would_delete(self):
        """Truncating at twenty would hide the staff account somebody wanted to see."""
        output = self.run_command('--keep-only=admin@dgg.test,director@dgg.test')
        self.assertIn('delete  worker@dgg.test', output)
        self.assertIn('delete  owner@gmail.com', output)
        self.assertIn('keep    admin@dgg.test', output)

    def test_a_refusal_is_a_command_error_and_not_a_traceback(self):
        with self.assertRaises(CommandError) as caught:
            self.run_command('--keep-only=directer@dgg.test', '--yes')
        self.assertIn('directer@dgg.test', str(caught.exception))
        self.assertEqual(User.objects.count(), 5)

    def test_it_reports_the_attribution_it_would_clear(self):
        AuditEntry.objects.filter(pk=self.office_audit.pk).update(actor=self.worker)
        output = self.run_command('--keep-only=admin@dgg.test,director@dgg.test')
        self.assertIn('loses whose name is on it', output)
        self.assertIn('AuditEntry.actor', output)
