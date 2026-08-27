"""Taking the seeded demo accounts out of a real deployment.

`seed_demo` invents six people sharing one password, and that password is in
this repository. §10 says it must not reach a public deployment; it did, and
stayed there, because `purge_applications` never touches staff on principle and
"by hand" turned out to mean "not at all".

What makes this worth testing rather than doing in a shell: the claim is that a
retired account *cannot sign in*. Deactivating a row and assuming the login path
honours it is exactly the sort of assumption this project keeps being caught by
— so the tests below ask the token endpoint rather than the database.
"""

from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO

from rest_framework.test import APITestCase

from accounts.models import Role, User
from funding.models import AuditEntry

PASSWORD = 'DemoPass123!'


def seeded(email, role):
    return User.objects.create_user(
        email, PASSWORD, first_name='Seeded', last_name='Demo', role=role)


class RetireDemoAccountsTests(APITestCase):
    def setUp(self):
        self.admin = seeded('admin@dgg.test', Role.ADMIN)
        self.director = seeded('director@dgg.test', Role.DIRECTOR)
        self.worker = seeded('worker@dgg.test', Role.SUPPORT_WORKER)
        self.finance = seeded('finance@dgg.test', Role.FINANCE)
        self.student = seeded('student@dgg.test', Role.STUDENT)
        # The office's own administrator, on a real address. Without one the
        # command refuses, which is its own test below.
        self.real = User.objects.create_user(
            'office@deline.ca', 'a-real-password-9134', first_name='Office',
            last_name='Administrator', role=Role.ADMIN)

    def run_command(self, *args):
        out = StringIO()
        call_command('retire_demo_accounts', *args, stdout=out)
        return out.getvalue()

    def can_sign_in(self, email, password=PASSWORD):
        response = self.client.post('/api/auth/token/',
                                    {'email': email, 'password': password},
                                    format='json')
        return response.status_code == 200

    # ── The thing it is for ─────────────────────────────────────────────────

    def test_the_published_password_works_before(self):
        """Establishes the fault. A test that only checked the 'after' state
        would pass on a database where these accounts never existed."""
        self.assertTrue(self.can_sign_in('admin@dgg.test'))

    def test_and_not_after(self):
        self.run_command('--yes')
        self.assertFalse(self.can_sign_in('admin@dgg.test'))

    def test_every_seeded_staff_account_is_shut_out(self):
        self.run_command('--yes')
        for email in ('admin@dgg.test', 'director@dgg.test',
                      'worker@dgg.test', 'finance@dgg.test'):
            with self.subTest(email=email):
                self.assertFalse(self.can_sign_in(email), email)

    def test_the_password_is_rotated_as_well_as_the_account_deactivated(self):
        """Reactivating an account is something a person does from the People
        screen without thinking about its password. If only `is_active` moved,
        the published credential would come back with it."""
        self.run_command('--yes')

        person = User.objects.get(email='admin@dgg.test')
        self.assertFalse(person.is_active)
        self.assertFalse(person.check_password(PASSWORD))

        # Reactivated by hand, as the People screen would.
        person.is_active = True
        person.save(update_fields=['is_active'])
        self.assertFalse(self.can_sign_in('admin@dgg.test'))

    def test_the_office_s_own_administrator_is_untouched(self):
        self.run_command('--yes')
        self.assertTrue(self.can_sign_in('office@deline.ca', 'a-real-password-9134'))

    def test_nothing_is_deleted(self):
        """Decisions, events and audit entries name the person who made them.
        Removing the row leaves a funding decision signed by nobody."""
        before = User.objects.count()
        self.run_command('--yes')
        self.assertEqual(User.objects.count(), before)

    # ── What it leaves behind ───────────────────────────────────────────────

    def test_it_is_written_down(self):
        self.run_command('--yes')
        entries = AuditEntry.objects.filter(action='account.deactivated')
        self.assertEqual(entries.count(), 4)
        self.assertIn('retired by', entries.first().detail)

    def test_running_it_twice_is_harmless(self):
        self.run_command('--yes')
        first = User.objects.get(email='admin@dgg.test').password
        self.run_command('--yes')
        self.assertFalse(self.can_sign_in('admin@dgg.test'))
        # Rotated again, which is harmless — nothing depends on the value.
        self.assertNotEqual(User.objects.get(email='admin@dgg.test').password, '')
        self.assertIsNotNone(first)

    # ── Students, and the refusal ───────────────────────────────────────────

    def test_students_are_left_alone_by_default(self):
        """`student@dgg.test` may be the account somebody is demonstrating the
        portal with, and it can read only its own file."""
        self.run_command('--yes')
        self.assertTrue(self.can_sign_in('student@dgg.test'))

    def test_but_can_be_included(self):
        self.run_command('--yes', '--include-students')
        self.assertFalse(self.can_sign_in('student@dgg.test'))

    def test_it_refuses_to_lock_the_only_administrator_out(self):
        """A deployment whose only administrator is the seeded one has a bigger
        problem than a published password, and locking it turns that into an
        outage nobody can undo from inside the portal."""
        self.real.delete()

        with self.assertRaises(CommandError) as caught:
            self.run_command('--yes')
        self.assertIn('createsuperuser', str(caught.exception))
        self.assertTrue(self.can_sign_in('admin@dgg.test'),
                        'the refusal must leave the account working')

    # ── Reporting ───────────────────────────────────────────────────────────

    def test_without_yes_it_only_reports(self):
        output = self.run_command()
        self.assertIn('Report only', output)
        self.assertTrue(self.can_sign_in('admin@dgg.test'))

    def test_it_names_what_it_found_and_what_remains(self):
        output = self.run_command()
        self.assertIn('admin@dgg.test', output)
        self.assertIn('office@deline.ca', output)

    def test_on_a_clean_database_it_says_so(self):
        for email in ('admin@dgg.test', 'director@dgg.test',
                      'worker@dgg.test', 'finance@dgg.test'):
            User.objects.get(email=email).delete()

        output = self.run_command('--yes')
        self.assertIn('Nothing to do', output)
