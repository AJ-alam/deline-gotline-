"""Where bank details go, now that they no longer go into `answers`.

The forms still ask for them — they have to, an award has to be paid to
something. What changed is where the answers land. Two things were wrong at
once, and neither failed a test:

  an account number sat in `Application.answers`, which the detail endpoint
  returns whole, the printable form renders, and the enrolment verification
  copies from;

  and nothing ever created the `BankAccount` that `finance.preview` pays from,
  so a student who filled the section in was still reported as having no
  account on file and their award was held.
"""

import itertools
import json

from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import BankAccount, Role, User
from funding.models import ApplicantIdentifier, Application, ApplicationType
from funding.schemas import get_schema
from funding.services import banking, finance, identifiers
from funding.test_fixtures import admission_answers, answers_for, confirm_enrolment
from funding.test_rules import seed_rates

_counter = itertools.count(1)

ACCOUNT = {
    'account_holder': 'Majid Khan',
    'transit_number': '12345',
    'institution_number': '001',
    'account_number': '9876543210',
}


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'b{next(_counter)}@test.com', 'pw12345678',
        first_name='Majid', last_name='Khan', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class WhereTheDetailsGoTests(APITestCase):
    """Asked on the form, absent from the answers, present on the account."""

    def setUp(self):
        self.student = make_user()
        self.client.force_authenticate(self.student)

    def submit(self, **overrides):
        return self.client.post('/api/applications/', {
            'type': 'admission', 'answers': admission_answers(**{**ACCOUNT, **overrides}),
        }, format='json')

    def test_the_form_still_asks_for_them(self):
        keys = set(get_schema('admission').keys)
        self.assertTrue(set(banking.KEYS) <= keys)

    def test_no_bank_detail_reaches_the_answers_column(self):
        response = self.submit()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        stored = Application.objects.get(pk=response.data['id']).answers
        for key in banking.KEYS:
            self.assertNotIn(key, stored, key)
        self.assertNotIn('9876543210', json.dumps(stored))

    def test_nor_the_detail_endpoint_that_returns_answers_whole(self):
        created = self.submit()
        detail = self.client.get(f'/api/applications/{created.data["id"]}/')
        self.assertNotIn('9876543210', json.dumps(detail.data, default=str))

    def test_they_become_the_account_the_student_is_paid_to(self):
        self.submit()
        account = self.student.bank_accounts.get(is_current=True)
        for key, value in ACCOUNT.items():
            self.assertEqual(getattr(account, key), value, key)

    def test_resubmitting_the_same_details_does_not_churn_the_record(self):
        """A returning student gives the same account every semester."""
        self.submit()
        self.submit()
        self.assertEqual(self.student.bank_accounts.count(), 1)

    def test_changed_details_retire_the_old_account_rather_than_editing_it(self):
        """A payment already sent must stay traceable to what was in force."""
        self.submit()
        self.submit(account_number='1111111111')

        self.assertEqual(self.student.bank_accounts.count(), 2)
        current = self.student.bank_accounts.get(is_current=True)
        self.assertEqual(current.account_number, '1111111111')
        retired = self.student.bank_accounts.get(is_current=False)
        self.assertEqual(retired.account_number, '9876543210')
        self.assertIsNotNone(retired.retired_at)

    def test_a_half_filled_section_is_not_recorded_as_an_account(self):
        """An account that cannot be paid should not look like one on file."""
        answers = admission_answers(**ACCOUNT)
        answers.pop('account_number')
        response = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': answers}, format='json')

        # account_number is required on this form, so the form itself refuses.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.student.bank_accounts.exists())

    def test_a_partial_account_never_reaches_the_record(self):
        """The service is the last line: forms differ on what they require."""
        application = Application.objects.create(
            student=self.student, type=ApplicationType.TRAVEL,
            stream='psssp', schema_slug='travel', answers={})
        banking.record(application, {'account_holder': 'Majid Khan',
                                     'transit_number': '12345'})
        self.assertFalse(self.student.bank_accounts.exists())


class PaymentRunTests(APITestCase):
    """The point of collecting them at all."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.student = make_user()
        self.client.force_authenticate(self.student)

    def test_a_student_who_filled_the_form_in_is_payable(self):
        """This was the whole failure: they gave an account and finance was
        told they had none, because nothing carried it across."""
        from funding.models import ApplicationEvent
        from funding.services.decisions import record_decision
        from funding.services import workflow

        created = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': admission_answers(**ACCOUNT),
        }, format='json')
        application = Application.objects.get(pk=created.data['id'])

        staff, director = make_user(Role.SUPPORT_WORKER), make_user(Role.DIRECTOR)
        workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
        confirm_enrolment(application)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, staff)
        workflow.record(application, ApplicationEvent.Action.APPROVED, director)
        record_decision(application, actor=director)

        ready, blocked = finance.preview()
        self.assertEqual(blocked, [], 'a student who gave an account was blocked')
        self.assertIn(application.pk,
                      {row['award'].application_id for row in ready})

    def test_the_file_carries_the_account_they_gave(self):
        from funding.models import ApplicationEvent
        from funding.services.decisions import record_decision
        from funding.services import workflow

        created = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': admission_answers(**ACCOUNT),
        }, format='json')
        application = Application.objects.get(pk=created.data['id'])
        staff, director = make_user(Role.SUPPORT_WORKER), make_user(Role.DIRECTOR)
        workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
        confirm_enrolment(application)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, staff)
        workflow.record(application, ApplicationEvent.Action.APPROVED, director)
        record_decision(application, actor=director)

        self.assertIn('9876543210', finance.dispatch(actor=director)['csv'])


class GuestTests(APITestCase):
    """A practicum claimed without an account still asks for bank details."""

    def guest_application(self):
        """Returns the created Application.

        The endpoint answers with a reference number and nothing else — it is
        public, and deliberately cannot be used to read anything back.
        """
        answers = answers_for('practicum', **{
            **ACCOUNT,
            'placement_start': '2026-09-01', 'placement_end': '2026-12-15',
        })
        response = self.client.post('/api/guest-applications/', {
            'type': 'practicum', 'answers': answers}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         str(response.data)[:300])
        return Application.objects.get(
            pk=int(response.data['reference'].removeprefix('DGG-')))

    def test_a_guest_form_asks_for_them(self):
        self.assertTrue(set(banking.KEYS) <= set(get_schema('practicum').keys))

    def test_they_do_not_land_in_a_guest_application_s_answers(self):
        application = self.guest_application()
        self.assertNotIn('9876543210', json.dumps(application.answers))
        for key in banking.KEYS:
            self.assertNotIn(key, application.answers, key)

    def test_they_are_held_encrypted_against_the_application(self):
        """There is no account to attach them to yet, and losing them means
        the applicant is asked for them again."""
        application = self.guest_application()

        held = ApplicantIdentifier.objects.get(
            application=application, kind=ApplicantIdentifier.Kind.BANK_ACCOUNT)
        self.assertNotIn('9876543210', held.ciphertext)
        self.assertEqual(held.last_three, '210')
        self.assertEqual(json.loads(identifiers.decrypt(held))['account_number'],
                         '9876543210')

    def test_attaching_the_application_gives_the_details_to_the_account(self):
        application = self.guest_application()
        student = make_user()
        staff = make_user(Role.SUPPORT_WORKER)
        self.client.force_authenticate(staff)

        response = self.client.post(f'/api/applications/{application.pk}/attach/',
                                    {'student_id': student.pk}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK,
                         str(response.data)[:300])

        account = student.bank_accounts.get(is_current=True)
        self.assertEqual(account.account_number, '9876543210')

    def test_attaching_never_redirects_money_the_student_already_directed(self):
        """Their own account wins over one typed on a guest form months ago."""
        application = self.guest_application()
        student = make_user()
        BankAccount.objects.create(user=student, account_holder='Majid Khan',
                                   transit_number='00000', institution_number='002',
                                   account_number='5555555555')
        staff = make_user(Role.SUPPORT_WORKER)
        self.client.force_authenticate(staff)
        self.client.post(f'/api/applications/{application.pk}/attach/',
                         {'student_id': student.pk}, format='json')

        self.assertEqual(student.bank_accounts.get(is_current=True).account_number,
                         '5555555555')


class ReviewScreenTests(APITestCase):
    """What a reviewer is told instead of the account number."""

    def setUp(self):
        self.student = make_user()
        self.client.force_authenticate(self.student)

    def test_it_reports_that_an_account_is_on_file_without_the_number(self):
        created = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': admission_answers(**ACCOUNT),
        }, format='json')
        detail = self.client.get(f'/api/applications/{created.data["id"]}/')

        banking_state = detail.data['banking']
        self.assertTrue(banking_state['on_file'])
        self.assertEqual(banking_state['account'], '••••3210')
        self.assertNotIn('9876543210', json.dumps(banking_state, default=str))

    def test_a_missing_account_is_reported_because_it_holds_the_award(self):
        answers = admission_answers()
        for key in banking.KEYS:
            answers.pop(key, None)
        # Travel does not require the section, so one can be filed without it.
        application = Application.objects.create(
            student=self.student, type=ApplicationType.TRAVEL, stream='psssp',
            schema_slug='travel', answers={})

        detail = self.client.get(f'/api/applications/{application.pk}/')
        self.assertFalse(detail.data['banking']['on_file'])
        self.assertEqual(detail.data['banking']['account'], '')


class PurgeCommandTests(APITestCase):
    """Rows written before the answers were routed still carry the details."""

    def legacy_application(self, student=None, **overrides):
        """An application as it was written before banking was split off."""
        return Application.objects.create(
            student=student, type=ApplicationType.TRAVEL, stream='dggr',
            schema_slug='travel',
            answers={'travel_from': 'Délı̨nę', **{**ACCOUNT, **overrides}},
        )

    def test_it_strips_the_details_and_records_the_account(self):
        student = make_user()
        application = self.legacy_application(student)

        call_command('purge_banking_answers', verbosity=0)

        application.refresh_from_db()
        for key in banking.KEYS:
            self.assertNotIn(key, application.answers, key)
        self.assertEqual(application.answers['travel_from'], 'Délı̨nę')
        self.assertEqual(student.bank_accounts.get(is_current=True).account_number,
                         '9876543210')

    def test_a_dry_run_changes_nothing(self):
        student = make_user()
        application = self.legacy_application(student)

        call_command('purge_banking_answers', '--dry-run', verbosity=0)

        application.refresh_from_db()
        self.assertIn('account_number', application.answers)
        self.assertFalse(student.bank_accounts.exists())

    def test_the_newest_application_becomes_the_current_account(self):
        """Walked oldest first, so the latest details are the ones in force."""
        student = make_user()
        self.legacy_application(student, account_number='1111111111')
        self.legacy_application(student, account_number='2222222222')

        call_command('purge_banking_answers', verbosity=0)

        self.assertEqual(student.bank_accounts.get(is_current=True).account_number,
                         '2222222222')

    def test_a_guest_application_keeps_its_details_encrypted(self):
        application = self.legacy_application(student=None)

        call_command('purge_banking_answers', verbosity=0)

        application.refresh_from_db()
        self.assertNotIn('account_number', application.answers)
        held = ApplicantIdentifier.objects.get(
            application=application, kind=ApplicantIdentifier.Kind.BANK_ACCOUNT)
        self.assertEqual(json.loads(identifiers.decrypt(held))['account_number'],
                         '9876543210')

    def test_a_partial_section_is_stripped_without_inventing_an_account(self):
        student = make_user()
        application = Application.objects.create(
            student=student, type=ApplicationType.TRAVEL, stream='dggr',
            schema_slug='travel',
            answers={'account_holder': 'Majid Khan', 'transit_number': '12345'},
        )

        call_command('purge_banking_answers', verbosity=0)

        application.refresh_from_db()
        self.assertEqual(application.answers, {})
        self.assertFalse(student.bank_accounts.exists())

    def test_running_it_twice_is_harmless(self):
        student = make_user()
        self.legacy_application(student)
        call_command('purge_banking_answers', verbosity=0)
        call_command('purge_banking_answers', verbosity=0)
        self.assertEqual(student.bank_accounts.count(), 1)


class RegistrarTests(APITestCase):
    """The institution is sent a copy of the student's answers."""

    def test_no_bank_detail_can_reach_an_institution(self):
        from funding.services import verification

        student = make_user()
        self.client.force_authenticate(student)
        created = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': admission_answers(**ACCOUNT),
        }, format='json')
        application = Application.objects.get(pk=created.data['id'])

        prefilled = verification.prefill_for(application)
        for key in banking.KEYS:
            self.assertNotIn(key, prefilled, key)
        self.assertNotIn('9876543210', json.dumps(prefilled))
