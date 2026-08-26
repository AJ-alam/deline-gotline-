"""Migration 0016, run for real against rows that predate it.

`continuing_funding` gained a required `registrar_email`. Every renewal already
in a database was filed without one, and `amend` re-cleans the whole answer set
— so without this migration an administrator opening an older renewal to fix a
typo is told the registrar email is missing, on a question the student was
never asked.

Tested by actually migrating: backwards to 0015, rows created there, then
forwards. Calling the function with today's model registry would test the
arithmetic and not the migration, and the failure mode being guarded against is
a migration that does not run or runs against the wrong historical models.

The database is thrown away and rebuilt around this, so it is slow. It is worth
it once: this is the only thing standing between the production database's
existing renewals and an office that cannot edit them.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = ('funding', '0015_awardrepayment_reportedcost')
AFTER = ('funding', '0016_renewals_carry_their_registrar')

# Held at its latest alongside whichever funding state is being asked for.
#
# `project_state` for a funding target alone gives the accounts models as they
# were when funding last depended on them, and the *table* is still the current
# one — so `User` came back without `eligible_streams` while the column was
# there and NOT NULL, and every insert failed on a column the historical model
# could not name.
ACCOUNTS = ('accounts', '0003_enrolmentprofile')

# What a renewal's answers looked like before the field existed. Written out
# rather than built from the schema on purpose: the schema is today's, and the
# point of this test is a row shaped the way yesterday's schema shaped it.
OLD_RENEWAL = {
    'full_name': 'Majid Khan',
    'beneficiary_number': 'DGG-2026-0041',
    'email': 'majid@example.com',
    'institution_name': 'Aurora College',
    'program': 'Environmental Science',
    'course_load': 'full_time',
    'dependent_count': 0,
    'semester': 'fall',
    'receives_sfa': False,
    'declaration_confirmed': True,
    'signature': 'Majid Khan',
}


class RegistrarBackfillTests(TransactionTestCase):
    # The migrations under test are the point, so they must not be skipped.
    available_apps = None

    def migrate_to(self, target):
        targets = [target, ACCOUNTS]
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        executor.loader.build_graph()
        return executor.loader.project_state(targets).apps

    def setUp(self):
        self.apps_before = self.migrate_to(BEFORE)

    def tearDown(self):
        # Leave the database where every other test expects to find it.
        self.migrate_to(AFTER)

    def make_student(self, apps, email):
        User = apps.get_model('accounts', 'User')
        # A historical model has no manager methods and no field defaults
        # applied by `create_user`, so every non-nullable column is named here.
        return User.objects.create(
            email=email, password='!', first_name='Majid', last_name='Khan',
            role='student', eligible_streams=[],
        )

    def make_application(self, apps, student, kind, answers, submitted=None):
        from django.utils import timezone

        Application = apps.get_model('funding', 'Application')
        return Application.objects.create(
            student=student, type=kind, schema_slug=kind, answers=answers,
            stream='psssp',
            submitted_at=submitted or timezone.now(),
        )

    def answers_of(self, pk):
        from funding.models import Application
        return Application.objects.get(pk=pk).answers

    def test_the_address_on_the_profile_is_carried_across(self):
        apps = self.apps_before
        student = self.make_student(apps, 'profile@example.com')
        apps.get_model('accounts', 'EnrolmentProfile').objects.create(
            user=student, registrar_email='onfile@aurora.ca')
        renewal = self.make_application(
            apps, student, 'continuing_funding', dict(OLD_RENEWAL))

        self.migrate_to(AFTER)

        self.assertEqual(self.answers_of(renewal.pk)['registrar_email'],
                         'onfile@aurora.ca')

    def test_otherwise_the_last_application_that_named_one(self):
        apps = self.apps_before
        student = self.make_student(apps, 'history@example.com')
        self.make_application(
            apps, student, 'admission',
            {'registrar_email': 'admissions@aurora.ca'})
        renewal = self.make_application(
            apps, student, 'continuing_funding', dict(OLD_RENEWAL))

        self.migrate_to(AFTER)

        self.assertEqual(self.answers_of(renewal.pk)['registrar_email'],
                         'admissions@aurora.ca')

    def test_the_profile_wins_over_the_older_application(self):
        """Same order the send-time lookup used, and for the same reason: what
        a student maintains on purpose beats what is inferred from a form they
        filled in last February."""
        apps = self.apps_before
        student = self.make_student(apps, 'both@example.com')
        apps.get_model('accounts', 'EnrolmentProfile').objects.create(
            user=student, registrar_email='current@aurora.ca')
        self.make_application(
            apps, student, 'admission', {'registrar_email': 'stale@aurora.ca'})
        renewal = self.make_application(
            apps, student, 'continuing_funding', dict(OLD_RENEWAL))

        self.migrate_to(AFTER)

        self.assertEqual(self.answers_of(renewal.pk)['registrar_email'],
                         'current@aurora.ca')

    def test_a_renewal_with_nothing_to_carry_is_left_alone(self):
        """Not filled with a placeholder.

        An invented address is a request to the wrong institution, and a blank
        one at least shows on the screen as `not_requested` for staff to act
        on. This is the row the office has to chase either way.
        """
        apps = self.apps_before
        student = self.make_student(apps, 'nothing@example.com')
        renewal = self.make_application(
            apps, student, 'continuing_funding', dict(OLD_RENEWAL))

        self.migrate_to(AFTER)

        self.assertNotIn('registrar_email', self.answers_of(renewal.pk))

    def test_an_address_already_on_the_renewal_is_not_overwritten(self):
        """A renewal filed after the field existed says who the student named.
        Replacing it with the profile's would rewrite an answer somebody gave.
        """
        apps = self.apps_before
        student = self.make_student(apps, 'answered@example.com')
        apps.get_model('accounts', 'EnrolmentProfile').objects.create(
            user=student, registrar_email='profile@aurora.ca')
        renewal = self.make_application(
            apps, student, 'continuing_funding',
            {**OLD_RENEWAL, 'registrar_email': 'named@aurora.ca'})

        self.migrate_to(AFTER)

        self.assertEqual(self.answers_of(renewal.pk)['registrar_email'],
                         'named@aurora.ca')

    def test_one_student_s_registrar_never_reaches_another(self):
        """The lookup is per student. A query missing its filter would carry
        the first address in the table onto everybody's renewal, and every
        assertion above would still pass."""
        apps = self.apps_before
        theirs = self.make_student(apps, 'theirs@example.com')
        self.make_application(
            apps, theirs, 'admission', {'registrar_email': 'theirs@aurora.ca'})

        mine = self.make_student(apps, 'mine@example.com')
        renewal = self.make_application(
            apps, mine, 'continuing_funding', dict(OLD_RENEWAL))

        self.migrate_to(AFTER)

        self.assertNotIn('registrar_email', self.answers_of(renewal.pk))

    def test_other_application_types_are_untouched(self):
        apps = self.apps_before
        student = self.make_student(apps, 'appeal@example.com')
        apps.get_model('accounts', 'EnrolmentProfile').objects.create(
            user=student, registrar_email='onfile@aurora.ca')
        appeal = self.make_application(
            apps, student, 'appeal', {'full_name': 'Majid Khan'})

        self.migrate_to(AFTER)

        self.assertNotIn('registrar_email', self.answers_of(appeal.pk))

    def test_a_backfilled_renewal_can_then_be_amended(self):
        """The reason the migration exists, asserted as the office experiences
        it rather than as a value in a column.

        Banking has to be supplied alongside, and that is not this migration's
        job: the renewal did not ask for it either, and unlike a registrar
        address there is nothing anywhere to carry across — a bank account
        cannot be inferred from an old form, and inventing one sends money to
        the wrong place. Either the student has a `BankAccount` on file, in
        which case `private_on_file` accepts blanks, or the office types it
        while it has the application open. Both are exercised below.
        """
        from funding.schemas import get_schema
        from funding.services import banking as banking_service

        apps = self.apps_before
        student = self.make_student(apps, 'amend@example.com')
        apps.get_model('accounts', 'EnrolmentProfile').objects.create(
            user=student, registrar_email='onfile@aurora.ca')
        renewal = self.make_application(
            apps, student, 'continuing_funding', dict(OLD_RENEWAL))

        self.migrate_to(AFTER)

        answers = dict(self.answers_of(renewal.pk))
        # Documents are the one thing the migration cannot supply and the
        # office would not retype; they are private to this assertion.
        answers['doc_transcript'] = 'document:1'
        answers['doc_enrollment_confirmation'] = 'document:2'

        # The office typing the banking in while it has the form open.
        cleaned = get_schema('continuing_funding').clean({
            **answers,
            'account_holder': 'Majid Khan',
            'transit_number': '12345',
            'institution_number': '003',
            'account_number': '7654321',
        })
        self.assertEqual(cleaned['registrar_email'], 'onfile@aurora.ca')

    def test_a_backfilled_renewal_amends_on_the_account_already_held(self):
        """The common case: the student has banking on file from an earlier
        form, so the office is not asked to retype a number the portal
        deliberately never shows them."""
        from accounts.models import BankAccount, User
        from funding.schemas import get_schema
        from funding.services import banking as banking_service

        apps = self.apps_before
        student = self.make_student(apps, 'held@example.com')
        renewal = self.make_application(
            apps, student, 'continuing_funding',
            {**OLD_RENEWAL, 'registrar_email': 'named@aurora.ca'})

        self.migrate_to(AFTER)

        BankAccount.objects.create(
            user=User.objects.get(pk=student.pk), account_holder='Majid Khan',
            transit_number='12345', institution_number='003',
            account_number='7654321', is_current=True)

        answers = dict(self.answers_of(renewal.pk))
        answers['doc_transcript'] = 'document:1'
        answers['doc_enrollment_confirmation'] = 'document:2'

        on_file = banking_service.on_file_for(User.objects.get(pk=student.pk))
        self.assertTrue(on_file, 'the account was just created')

        cleaned = get_schema('continuing_funding').clean(
            answers, private_on_file=on_file)
        self.assertEqual(cleaned['registrar_email'], 'named@aurora.ca')
