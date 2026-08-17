"""Emergency relief.

The form somebody fills in on a bad day, which shapes what is worth testing:

  * the amount is an award input — `capped_request` pays it up to the published
    maximum — so it is a validated figure and the cap is the office's, not the
    applicant's;
  * documents are not required. Waiting for a letter from a landlord before
    asking for help is the opposite of what this is for;
  * a phone number is required here and nowhere else, because this is the one
    form where the office may need to reach somebody the same day;
  * it now carries a declaration. It had a signature and nothing above it to
    sign — a signature attesting to nothing.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    FundingStream, PolicySetting, RuleSet,
)
from funding.rules.engine import price
from funding.schemas import FieldType, ValidationError, get_schema
from funding.services import workflow
from funding.services.policy import PolicyBook
from funding.test_fixtures import answers_for

SCHEMA = get_schema('emergency_relief')
CAP = Decimal('1500')


def request_relief(**overrides) -> dict:
    defaults = dict(
        full_name='Majid Khan',
        email='majid.khan@example.com',
        phone='8675550143',
        emergency_type='housing',
        emergency_description='The furnace failed and the rental is uninhabitable.',
        amount_requested='900',
        signature='Majid Khan',
    )
    defaults.update(overrides)
    return answers_for('emergency_relief', **defaults)


class FormContentTests(SimpleTestCase):

    def test_it_asks_what_the_office_needs_and_no_more(self):
        self.assertEqual(
            set(SCHEMA.keys),
            {
                'full_name', 'email', 'phone', 'beneficiary_number',
                'emergency_type', 'emergency_description', 'amount_requested',
                'doc_supporting',
                'account_holder', 'transit_number', 'institution_number',
                'account_number',
                'declaration_confirmed', 'signature', 'signed_on',
            },
        )

    def test_it_falls_into_the_three_steps_the_client_builds(self):
        self.assertEqual(
            SCHEMA.sections,
            ('Your details', 'The emergency', 'Supporting documents',
             'Payment', 'Declaration'),
        )

    def test_a_phone_number_is_required_here_and_nowhere_else(self):
        """The one form where the office may need to reach somebody today. An
        email address is not a way to do that."""
        self.assertTrue(SCHEMA.field('phone').required)
        self.assertFalse(get_schema('travel').field('phone').required)

    def test_the_nature_of_the_emergency_is_a_closed_list(self):
        self.assertEqual(
            set(SCHEMA.field('emergency_type').choice_values),
            {'medical', 'bereavement', 'housing', 'travel', 'other'},
        )

    def test_an_emergency_outside_the_list_is_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(request_relief(emergency_type='car trouble'))

    def test_the_amount_is_money_because_it_is_what_gets_paid(self):
        field = SCHEMA.field('amount_requested')
        self.assertEqual(field.type, FieldType.MONEY)
        self.assertTrue(field.required)

    def test_a_negative_amount_is_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(request_relief(amount_requested='-500'))

    def test_documents_are_plural_and_not_required(self):
        """Waiting for a landlord's letter before asking for help is the
        opposite of what this form is for."""
        field = SCHEMA.field('doc_supporting')
        self.assertEqual(field.type, FieldType.FILES)
        self.assertFalse(field.required)

    def test_every_attached_document_is_kept(self):
        cleaned = SCHEMA.clean(request_relief(
            doc_supporting=['document:1', 'document:2', 'document:3']))
        self.assertEqual(len(cleaned['doc_supporting']), 3)


class DeclarationTests(SimpleTestCase):
    """It had a signature and nothing above it to sign."""

    def test_the_form_now_carries_a_declaration(self):
        self.assertEqual(SCHEMA.field('declaration_confirmed').type,
                         FieldType.CONFIRM)

    def test_it_cannot_be_filed_with_the_declaration_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(request_relief(declaration_confirmed='false'))

    def test_nor_with_it_left_unanswered(self):
        answers = {k: v for k, v in request_relief().items()
                   if k != 'declaration_confirmed'}
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(answers)
        self.assertIn('declaration_confirmed', caught.exception.errors)

    def test_the_date_signed_opens_on_today(self):
        self.assertTrue(SCHEMA.field('signed_on').defaults_to_today)


class BankingTests(SimpleTestCase):
    """The money has to reach somebody, and the details must not sit in
    `answers` where the detail endpoint returns them whole."""

    def test_bank_details_are_asked_for(self):
        self.assertIn('account_number', SCHEMA.keys)

    def test_and_never_stored_as_ordinary_answers(self):
        for key in ('account_holder', 'transit_number',
                    'institution_number', 'account_number'):
            with self.subTest(key=key):
                self.assertIn(key, SCHEMA.private_keys)


class PricingTests(TestCase):
    """`capped_request`: what was asked for, up to the office's maximum."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='emergency_relief', key='max_per_student',
            defaults=dict(label='max_per_student', value=CAP, unit='$'))
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def priced(self, amount):
        application = Application.objects.create(
            student=None, type=ApplicationType.EMERGENCY_RELIEF,
            stream=FundingStream.DGGR, schema_slug='emergency_relief',
            answers={'amount_requested': str(amount)})
        decision = price(application, self.rule_set,
                         PolicyBook.for_application(application))
        amounts = {o.code: o.amount for o in decision.applied}
        return amounts.get('emergency_relief', Decimal('0')), decision

    def test_a_request_under_the_cap_is_paid_in_full(self):
        self.assertEqual(self.priced('900')[0], Decimal('900'))

    def test_a_request_over_the_cap_is_paid_at_the_cap(self):
        self.assertEqual(self.priced('9000')[0], CAP)

    def test_moving_the_cap_moves_what_is_paid(self):
        """The cap is a policy rate the office edits without a deploy."""
        PolicySetting.objects.filter(section='emergency_relief',
                                     key='max_per_student').update(value=Decimal('500'))
        self.assertEqual(self.priced('9000')[0], Decimal('500'))

    def test_the_trace_says_what_it_was_capped_against(self):
        """A funding body has to explain an award years later."""
        _, decision = self.priced('9000')
        rule = next(row for row in decision.outcomes
                    if row.code == 'emergency_relief')
        self.assertIn('capped at', rule.explanation)


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@emergency.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class ThroughTheOfficeTests(TestCase):
    """Student files, worker reviews, director decides."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='emergency_relief', key='max_per_student',
            defaults=dict(label='max_per_student', value=CAP, unit='$'))
        self.student = make_user(email='applicant@emergency.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@emergency.test')
        self.director = make_user(Role.DIRECTOR, 'director@emergency.test')
        self.client = APIClient()

    def file_one(self, **overrides):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            '/api/applications/',
            {'type': 'emergency_relief', 'answers': request_relief(**overrides)},
            format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(pk=response.data['id'])

    def test_a_student_can_file_one(self):
        self.assertEqual(self.file_one().status, ApplicationStatus.SUBMITTED)

    def test_the_bank_details_do_not_reach_the_answers(self):
        application = self.file_one(
            account_holder='Majid Khan', transit_number='12345',
            institution_number='001', account_number='9876543210')
        self.assertNotIn('account_number', application.answers)

    def test_and_are_recorded_where_finance_reads_them(self):
        """Details typed into a form that does not route them do not exist:
        the student is reported to finance as having no account on file."""
        self.file_one(
            account_holder='Majid Khan', transit_number='12345',
            institution_number='001', account_number='9876543210')
        self.assertTrue(self.student.bank_accounts.filter(is_current=True).exists())

    def test_it_carries_no_enrolment_gate(self):
        """Tuition is funded against the registrar's figure, so admission and
        renewals wait for one. Making somebody in an emergency wait for their
        institution to answer an email would strand the request."""
        application = self.file_one()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.AWAITING_DECISION)

    def test_the_director_prices_it_at_what_was_asked_for(self):
        application = self.file_one(amount_requested='900')
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)

        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data['total'])), Decimal('900'))

    def test_an_inflated_request_cannot_beat_the_cap(self):
        application = self.file_one(amount_requested='9000')
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)

        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(Decimal(str(response.data['total'])), CAP)

    def test_a_worker_cannot_price_it(self):
        application = self.file_one()
        self.client.force_authenticate(self.worker)
        self.assertEqual(
            self.client.post(f'/api/applications/{application.pk}/price/').status_code,
            403)

    def test_a_student_cannot_price_their_own(self):
        application = self.file_one()
        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.post(f'/api/applications/{application.pk}/price/').status_code,
            403)

    def test_another_student_cannot_read_it(self):
        application = self.file_one()
        self.client.force_authenticate(make_user(email='other@emergency.test'))
        self.assertIn(
            self.client.get(f'/api/applications/{application.pk}/').status_code,
            (403, 404))

    def test_a_reviewer_reads_back_what_happened_and_the_evidence(self):
        application = self.file_one(
            doc_supporting=['document:1', 'document:2'])
        self.client.force_authenticate(self.worker)
        response = self.client.get(f'/api/applications/{application.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('furnace', response.data['answers']['emergency_description'])
        self.assertEqual(len(response.data['answers']['doc_supporting']), 2)
