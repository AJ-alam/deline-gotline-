"""Managing who can do what.

Changing a role grants or removes the power to decide funding and release money.
The guards here exist because the failure modes are not recoverable through the
portal: an office with nobody able to grant access has to go to a database
console.
"""

import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from accounts.services import administration
from funding.models import AuditEntry

_counter = itertools.count(1)


def make_user(role=Role.STUDENT, **kwargs):
    return User.objects.create_user(
        f'u{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name=f'P{next(_counter)}', role=role, **kwargs,is_deline_beneficiary=True, is_indian_act_registered=True)


class LockoutGuardTests(TestCase):
    """Each of these leaves the office unable to administer itself."""

    def setUp(self):
        self.admin = make_user(Role.ADMIN)

    def test_an_administrator_cannot_demote_themselves(self):
        with self.assertRaises(administration.AdministrationError) as ctx:
            administration.change_role(self.admin, Role.STUDENT, actor=self.admin)

        self.assertIn('another administrator', str(ctx.exception))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, Role.ADMIN)

    def test_an_administrator_cannot_deactivate_themselves(self):
        with self.assertRaises(administration.AdministrationError):
            administration.set_active(self.admin, False, actor=self.admin)

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_the_last_administrator_cannot_be_demoted(self):
        other = make_user(Role.ADMIN)
        # The actor is not an administrator: the view restricts who may call
        # this, the service enforces what the system can survive. Creating a
        # fresh administrator to act would itself supply the cover being tested.
        director = make_user(Role.DIRECTOR)

        # Removing one is fine while another remains.
        administration.change_role(self.admin, Role.STUDENT, actor=director)

        with self.assertRaises(administration.AdministrationError) as ctx:
            administration.change_role(other, Role.STUDENT, actor=director)
        self.assertIn('only administrator', str(ctx.exception).lower())

    def test_the_last_administrator_cannot_be_deactivated(self):
        other = make_user(Role.ADMIN)
        director = make_user(Role.DIRECTOR)

        administration.set_active(self.admin, False, actor=director)
        with self.assertRaises(administration.AdministrationError):
            administration.set_active(other, False, actor=director)

    def test_a_deactivated_administrator_does_not_count_as_cover(self):
        """Someone who cannot sign in cannot administer anything."""
        other = make_user(Role.ADMIN)
        director = make_user(Role.DIRECTOR)
        administration.set_active(other, False, actor=self.admin)

        with self.assertRaises(administration.AdministrationError):
            administration.change_role(self.admin, Role.STUDENT, actor=director)


class RoleChangeTests(TestCase):

    def setUp(self):
        self.admin = make_user(Role.ADMIN)

    def test_a_role_can_be_changed(self):
        person = make_user()
        updated = administration.change_role(person, Role.SUPPORT_WORKER,
                                             actor=self.admin)
        self.assertEqual(updated.role, Role.SUPPORT_WORKER)
        self.assertTrue(updated.reviews_applications)

    def test_admin_site_access_follows_the_role(self):
        """The two must not be able to disagree about who is privileged."""
        person = make_user()
        administration.change_role(person, Role.ADMIN, actor=self.admin)
        person.refresh_from_db()
        self.assertTrue(person.is_staff)

        administration.change_role(person, Role.FINANCE, actor=self.admin)
        person.refresh_from_db()
        self.assertFalse(person.is_staff)

    def test_an_unknown_role_is_refused(self):
        with self.assertRaises(administration.AdministrationError):
            administration.change_role(make_user(), 'superuser', actor=self.admin)

    def test_every_change_is_audited(self):
        person = make_user()
        administration.change_role(person, Role.DIRECTOR, actor=self.admin)

        entry = AuditEntry.objects.get(action='account.role_changed')
        self.assertEqual(entry.actor, self.admin)
        self.assertIn(person.email, entry.detail)
        self.assertIn('director', entry.detail)

    def test_setting_the_same_role_changes_nothing(self):
        person = make_user(Role.FINANCE)
        administration.change_role(person, Role.FINANCE, actor=self.admin)
        self.assertFalse(AuditEntry.objects.filter(action='account.role_changed').exists())


class DeactivationTests(TestCase):

    def setUp(self):
        self.admin = make_user(Role.ADMIN)

    def test_an_account_is_deactivated_rather_than_deleted(self):
        """Decisions name the person who made them; the row has to survive."""
        person = make_user(Role.SUPPORT_WORKER)
        administration.set_active(person, False, actor=self.admin)

        person.refresh_from_db()
        self.assertFalse(person.is_active)
        self.assertTrue(User.objects.filter(pk=person.pk).exists())

    def test_an_account_can_be_restored(self):
        person = make_user()
        administration.set_active(person, False, actor=self.admin)
        administration.set_active(person, True, actor=self.admin)

        person.refresh_from_db()
        self.assertTrue(person.is_active)
        self.assertTrue(AuditEntry.objects.filter(action='account.activated').exists())

    def test_deactivation_is_audited(self):
        administration.set_active(make_user(), False, actor=self.admin)
        self.assertTrue(AuditEntry.objects.filter(action='account.deactivated').exists())


class DirectoryTests(TestCase):

    def setUp(self):
        self.admin = make_user(Role.ADMIN)

    def test_inactive_accounts_are_hidden_unless_asked_for(self):
        gone = make_user()
        administration.set_active(gone, False, actor=self.admin)

        self.assertNotIn(gone, administration.directory())
        self.assertIn(gone, administration.directory(include_inactive=True))

    def test_people_can_be_found_by_name_email_or_beneficiary_number(self):
        person = make_user()
        person.first_name = 'Rosalie'
        person.beneficiary_number = 'B-9911'
        person.save()

        self.assertIn(person, administration.directory(search='rosal'))
        self.assertIn(person, administration.directory(search='B-99'))
        self.assertIn(person, administration.directory(search=person.email[:6]))

    def test_the_directory_can_be_narrowed_to_one_role(self):
        worker = make_user(Role.SUPPORT_WORKER)
        student = make_user()

        results = administration.directory(role=Role.SUPPORT_WORKER)
        self.assertIn(worker, results)
        self.assertNotIn(student, results)


class EndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.admin = make_user(Role.ADMIN)
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.student = make_user()

    def test_staff_can_search_the_directory(self):
        self.client.force_authenticate(self.worker)
        response = self.client.get('/api/people/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['results'])
        self.assertTrue(response.data['roles'])

    def test_a_student_cannot_read_the_directory(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/people/').status_code, 403)

    def test_the_directory_does_not_expose_addresses_or_banking(self):
        self.client.force_authenticate(self.worker)
        row = self.client.get('/api/people/').data['results'][0]

        for field in ('street_address', 'account_number', 'treaty_number',
                      'date_of_birth'):
            self.assertNotIn(field, row)

    def test_an_administrator_can_change_a_role(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f'/api/people/{self.student.id}/',
                                     {'role': Role.FINANCE}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['role'], Role.FINANCE)

    def test_a_support_worker_cannot_change_a_role(self):
        self.client.force_authenticate(self.worker)
        response = self.client.patch(f'/api/people/{self.student.id}/',
                                     {'role': Role.ADMIN}, format='json')

        self.assertEqual(response.status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, Role.STUDENT)

    def test_a_refused_change_explains_itself(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f'/api/people/{self.admin.id}/',
                                     {'role': Role.STUDENT}, format='json')

        self.assertEqual(response.status_code, 409)
        self.assertIn('another administrator', response.data['detail'])

    def test_an_unknown_account_is_a_404(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.patch('/api/people/999999/', {'role': Role.STUDENT},
                              format='json').status_code, 404)
