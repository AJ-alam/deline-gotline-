"""The consolidated user model."""

from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import BankAccount, Role, User


class UserCreationTests(TestCase):

    def test_a_user_is_created_with_an_email_and_password(self):
        user = User.objects.create_user('jane@example.com', 'pw12345678',
                                        first_name='Jane', last_name='Doe')
        self.assertEqual(user.email, 'jane@example.com')
        self.assertTrue(user.check_password('pw12345678'))
        self.assertEqual(user.role, Role.STUDENT)
        self.assertFalse(user.is_staff)

    def test_the_whole_email_is_normalised_not_just_the_domain(self):
        user = User.objects.create_user('Jane@EXAMPLE.COM', 'pw12345678',
                                        first_name='Jane', last_name='Doe')
        self.assertEqual(user.email, 'jane@example.com')

    def test_the_same_address_in_different_case_cannot_register_twice(self):
        User.objects.create_user('jane@example.com', 'pw12345678',
                                 first_name='Jane', last_name='Doe')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(email='JANE@example.com', first_name='J',
                                    last_name='D')

    def test_sign_in_finds_the_account_whatever_case_was_typed(self):
        User.objects.create_user('jane@example.com', 'pw12345678',
                                 first_name='Jane', last_name='Doe')
        self.assertEqual(
            User.objects.get_by_natural_key('JANE@Example.COM').email,
            'jane@example.com',
        )

    def test_an_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user('', 'pw12345678')

    def test_emails_are_unique(self):
        User.objects.create_user('jane@example.com', 'pw12345678',
                                 first_name='Jane', last_name='Doe')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user('jane@example.com', 'pw12345678',
                                         first_name='Other', last_name='Person')

    def test_a_superuser_has_admin_access(self):
        user = User.objects.create_superuser('root@example.com', 'pw12345678',
                                             first_name='Root', last_name='User')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, Role.ADMIN)

    def test_a_superuser_cannot_be_created_without_staff_access(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser('root@example.com', 'pw12345678',
                                          first_name='Root', last_name='User',
                                          is_staff=False)

    def test_the_password_is_never_stored_in_the_clear(self):
        user = User.objects.create_user('jane@example.com', 'pw12345678',
                                        first_name='Jane', last_name='Doe')
        self.assertNotEqual(user.password, 'pw12345678')
        self.assertIn('$', user.password)


class NameTests(TestCase):

    def _user(self, **kwargs):
        return User.objects.create_user(
            'jane@example.com', 'pw12345678',
            first_name=kwargs.pop('first_name', 'Jane'),
            last_name=kwargs.pop('last_name', 'Doe'), **kwargs,
        )

    def test_full_name_joins_the_parts(self):
        self.assertEqual(self._user().full_name, 'Jane Doe')

    def test_display_name_prefers_what_someone_asks_to_be_called(self):
        self.assertEqual(self._user(preferred_name='Janey').display_name, 'Janey')

    def test_display_name_falls_back_to_the_first_name(self):
        self.assertEqual(self._user().display_name, 'Jane')

    def test_display_name_falls_back_to_the_email_when_no_name_is_known(self):
        user = User.objects.create_user('anon@example.com', 'pw12345678',
                                        first_name='', last_name='')
        self.assertEqual(user.display_name, 'anon@example.com')


class RoleTests(TestCase):
    """Role questions asked in one place rather than rewritten at each call site."""

    def _user(self, role):
        return User.objects.create_user(
            f'{role}@example.com', 'pw12345678',
            first_name='Test', last_name='User', role=role,
        )

    def test_students_neither_review_nor_decide(self):
        student = self._user(Role.STUDENT)
        self.assertTrue(student.is_student)
        self.assertFalse(student.reviews_applications)
        self.assertFalse(student.decides_applications)
        self.assertFalse(student.handles_payments)

    def test_support_workers_review_but_do_not_decide(self):
        staff = self._user(Role.SUPPORT_WORKER)
        self.assertTrue(staff.reviews_applications)
        self.assertFalse(staff.decides_applications)

    def test_directors_decide_but_do_not_review(self):
        director = self._user(Role.DIRECTOR)
        self.assertTrue(director.decides_applications)
        self.assertFalse(director.reviews_applications)

    def test_finance_handles_payments_only(self):
        finance = self._user(Role.FINANCE)
        self.assertTrue(finance.handles_payments)
        self.assertFalse(finance.decides_applications)

    def test_an_administrator_can_do_everything(self):
        admin = self._user(Role.ADMIN)
        self.assertTrue(admin.reviews_applications)
        self.assertTrue(admin.decides_applications)
        self.assertTrue(admin.handles_payments)


class PerApplicationDataTests(TestCase):
    """Facts about a term belong to the application that claims them."""

    def test_the_user_holds_nothing_that_changes_each_semester(self):
        held = {f.name for f in User._meta.get_fields()}
        for leaked in (
            'institution_name', 'program_credential', 'current_semester',
            'enrollment_status', 'course_load', 'program_type', 'years_in_program',
            'expected_graduation_date', 'institution_location', 'num_dependents',
            'financial_assistance_status',
        ):
            self.assertNotIn(leaked, held, f'{leaked} varies per application')

    def test_the_user_holds_what_stays_true_between_applications(self):
        held = {f.name for f in User._meta.get_fields()}
        for kept in ('email', 'first_name', 'last_name', 'date_of_birth',
                     'beneficiary_number', 'treaty_number', 'role'):
            self.assertIn(kept, held)


class BankAccountTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('jane@example.com', 'pw12345678',
                                             first_name='Jane', last_name='Doe')

    def _account(self, **kwargs):
        defaults = dict(
            account_holder='Jane Doe', transit_number='12345',
            institution_number='001', account_number='9876543210',
        )
        defaults.update(kwargs)
        return BankAccount.objects.create(user=self.user, **defaults)

    def test_an_account_number_is_masked_for_display(self):
        self.assertEqual(self._account().masked_account_number, '****3210')

    def test_the_string_form_never_exposes_the_full_number(self):
        account = self._account()
        self.assertNotIn('9876543210', str(account))

    def test_only_one_account_can_be_current(self):
        self._account()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._account(account_number='1111222233')

    def test_a_previous_account_is_retired_not_deleted(self):
        """A payment must remain traceable to the details in force when issued."""
        old = self._account()
        old.is_current = False
        old.save(update_fields=['is_current'])
        new = self._account(account_number='1111222233')

        self.assertEqual(self.user.bank_accounts.count(), 2)
        self.assertEqual(
            self.user.bank_accounts.filter(is_current=True).get(), new,
        )
