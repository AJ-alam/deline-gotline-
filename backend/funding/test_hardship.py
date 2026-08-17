"""The emergency hardship bursary — a last resort.

Three things carry weight here:

  * the amount is itemised and added up by the server, exactly as a travel claim
    is. `capped_request` pays `amount_requested` up to the published maximum, so
    a total asked for separately can disagree with the lines and the figure
    nobody itemised is the one that gets paid;
  * the cap is the office's, published as a rate it can move without a deploy.
    The office's own screen prints "$500 limit" while the seeded rate says
    $3,000 — which is exactly why the figure is not written into the form;
  * two attestations, both `CONFIRM`. "No, I am not active in my programme" and
    "no, this is not accurate" are not answers this bursary can be filed with,
    and a required BOOLEAN accepts False because False is not empty.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.api.serializers import jsonable
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    FundingStream, PolicySetting, RuleSet,
)
from funding.rules.engine import price
from funding.schemas import FieldType, ValidationError, get_schema
from funding.services import workflow
from funding.services.policy import PolicyBook
from funding.test_fixtures import answers_for

SCHEMA = get_schema('hardship_bursary')
CAP = Decimal('3000')

LINES = [
    {'purpose': 'Overdue rent', 'amount': '400.00'},
    {'purpose': 'Groceries for the month', 'amount': '180.50'},
    {'purpose': 'Bus pass', 'amount': '60.00'},
]
TOTAL = Decimal('640.50')


def request_bursary(**overrides) -> dict:
    defaults = dict(
        full_name='Majid Khan',
        institution_name='Aurora College',
        active_and_compliant='true',
        hardship_reason='My hours were cut and rent is two weeks overdue.',
        other_supports_attempted='The food bank, and my aunt, who has none to spare.',
        fund_breakdown=LINES,
        signature='Majid Khan',
    )
    defaults.update(overrides)
    return answers_for('hardship_bursary', **defaults)


class FormContentTests(SimpleTestCase):

    def test_it_asks_exactly_what_the_office_asked_for(self):
        self.assertEqual(
            set(SCHEMA.keys),
            {
                'full_name', 'beneficiary_number', 'institution_name',
                'active_and_compliant',
                'hardship_reason', 'other_supports_attempted',
                'fund_breakdown', 'amount_requested',
                'declaration_confirmed', 'signature', 'signed_on',
            },
        )

    def test_it_falls_into_the_four_steps_the_screens_show(self):
        self.assertEqual(
            SCHEMA.sections,
            ('Student information', 'The emergency', 'Fund breakdown', 'Declaration'),
        )

    def test_the_office_s_own_name_for_it_is_the_one_shown(self):
        self.assertEqual(ApplicationType.HARDSHIP_BURSARY.label,
                         'Emergency Hardship Bursary (Last Resort)')

    def test_it_asks_what_else_was_tried_first(self):
        """The question that makes this a last resort rather than a first one."""
        field = SCHEMA.field('other_supports_attempted')
        self.assertEqual(field.type, FieldType.LONG_TEXT)
        self.assertTrue(field.required)
        self.assertIn('food banks', field.help_text)

    def test_no_bank_details_are_asked_for(self):
        """This cannot be claimed without an account, so finance already has
        somewhere to pay. A second set is a second set that can disagree."""
        for key in ('account_holder', 'transit_number',
                    'institution_number', 'account_number'):
            self.assertNotIn(key, SCHEMA.keys)

    def test_no_documents_are_asked_for(self):
        """The office's screen has no upload. Recorded rather than assumed:
        every neighbouring form has one, so its absence looks like an
        oversight until it is asserted."""
        self.assertNotIn('doc_supporting', SCHEMA.keys)

    def test_the_cap_is_not_written_into_the_form(self):
        """The screen prints '$500 limit'; the seeded rate says $3,000. Two
        figures that agree only by habit is how a display string came to decide
        what somebody was paid."""
        text = ' '.join(field.help_text for field in SCHEMA.fields)
        for amount in ('$500', '500', '$3,000', '$3000'):
            self.assertNotIn(amount, text)


class AttestationTests(SimpleTestCase):
    """Both boxes are things you cannot file this without."""

    def test_being_active_in_the_programme_is_a_confirmation(self):
        self.assertEqual(SCHEMA.field('active_and_compliant').type,
                         FieldType.CONFIRM)

    def test_it_cannot_be_filed_by_someone_who_says_they_are_not(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(request_bursary(active_and_compliant='false'))
        self.assertIn('active_and_compliant', caught.exception.errors)

    def test_nor_left_unanswered(self):
        answers = {k: v for k, v in request_bursary().items()
                   if k != 'active_and_compliant'}
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(answers)
        self.assertIn('active_and_compliant', caught.exception.errors)

    def test_the_declaration_is_worded_as_the_office_words_it(self):
        self.assertEqual(
            SCHEMA.field('declaration_confirmed').help_text,
            'I confirm that the information provided is accurate and complete. '
            'I understand that hardship support is discretionary and considered '
            'a last resort.',
        )

    def test_the_declaration_cannot_be_filed_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(request_bursary(declaration_confirmed='false'))

    def test_the_date_signed_opens_on_today(self):
        self.assertTrue(SCHEMA.field('signed_on').defaults_to_today)


class FundBreakdownTests(SimpleTestCase):
    """The amount is the lines, added up."""

    def test_the_breakdown_is_a_table_with_a_purpose_and_an_amount(self):
        field = SCHEMA.field('fund_breakdown')
        self.assertEqual(field.type, FieldType.TABLE)
        self.assertEqual([column.key for column in field.columns],
                         ['purpose', 'amount'])
        self.assertTrue(field.required)

    def test_the_total_is_the_lines_added_up(self):
        self.assertEqual(SCHEMA.clean(request_bursary())['amount_requested'], TOTAL)

    def test_the_total_is_not_a_question_anyone_is_asked(self):
        field = SCHEMA.field('amount_requested')
        self.assertTrue(field.computed)
        self.assertFalse(field.required)

    def test_a_total_sent_by_the_client_is_discarded(self):
        cleaned = SCHEMA.clean(request_bursary(amount_requested='99999'))
        self.assertEqual(cleaned['amount_requested'], TOTAL)

    def test_a_total_that_does_not_parse_is_not_even_an_error(self):
        """Discarded before validation, not overwritten after it. A client that
        echoed back a formatted total would otherwise have the whole submission
        refused over a figure the server itself produced."""
        cleaned = SCHEMA.clean(request_bursary(amount_requested='not a number'))
        self.assertEqual(cleaned['amount_requested'], TOTAL)

    def test_blank_lines_are_dropped(self):
        cleaned = SCHEMA.clean(request_bursary(fund_breakdown=[
            LINES[0], {'purpose': '', 'amount': ''}, LINES[1], LINES[2]]))
        self.assertEqual(len(cleaned['fund_breakdown']), 3)
        self.assertEqual(cleaned['amount_requested'], TOTAL)

    def test_a_breakdown_of_nothing_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(request_bursary(fund_breakdown=[]))
        self.assertIn('fund_breakdown', caught.exception.errors)

    def test_a_line_with_an_amount_and_no_purpose_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(request_bursary(
                fund_breakdown=[{'purpose': '', 'amount': '40'}]))
        self.assertIn('Row 1', caught.exception.errors['fund_breakdown'])

    def test_a_line_whose_amount_is_not_an_amount_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(request_bursary(fund_breakdown=[
                LINES[0], {'purpose': 'Rent', 'amount': 'about four hundred'}]))
        self.assertIn('Row 2', caught.exception.errors['fund_breakdown'])

    def test_more_lines_than_the_cap_are_refused(self):
        limit = SCHEMA.field('fund_breakdown').max_items
        with self.assertRaises(ValidationError):
            SCHEMA.clean(request_bursary(fund_breakdown=[
                {'purpose': f'Item {n}', 'amount': '1'} for n in range(limit + 1)]))


class PricingTests(TestCase):
    """`capped_request` against the rate the office publishes."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        self.set_cap(CAP)
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def set_cap(self, value):
        PolicySetting.objects.update_or_create(
            section='hardship_bursary', key='max_per_student',
            defaults=dict(label='max_per_student', value=Decimal(value), unit='$'))

    def priced(self, **overrides):
        cleaned = SCHEMA.clean(request_bursary(**overrides))
        application = Application.objects.create(
            student=None, type=ApplicationType.HARDSHIP_BURSARY,
            stream=FundingStream.DGGR, schema_slug='hardship_bursary',
            answers=jsonable(cleaned))
        decision = price(application, self.rule_set,
                         PolicyBook.for_application(application))
        amounts = {o.code: o.amount for o in decision.applied}
        return amounts.get('hardship_bursary', Decimal('0'))

    def test_a_breakdown_under_the_cap_is_paid_at_its_itemised_total(self):
        self.assertEqual(self.priced(), TOTAL)

    def test_a_breakdown_over_the_cap_is_paid_at_the_cap(self):
        self.assertEqual(
            self.priced(fund_breakdown=[{'purpose': 'Rent arrears', 'amount': '9000'}]),
            CAP)

    def test_moving_the_cap_moves_what_is_paid(self):
        """The figure the office's screen prints as $500 is a rate, and this is
        what makes it one."""
        self.set_cap('500')
        self.assertEqual(
            self.priced(fund_breakdown=[{'purpose': 'Rent arrears', 'amount': '9000'}]),
            Decimal('500'))


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@hardship.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class ThroughTheOfficeTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='hardship_bursary', key='max_per_student',
            defaults=dict(label='max_per_student', value=CAP, unit='$'))
        self.student = make_user(email='applicant@hardship.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@hardship.test')
        self.director = make_user(Role.DIRECTOR, 'director@hardship.test')
        self.client = APIClient()

    def file_one(self, **overrides):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            '/api/applications/',
            {'type': 'hardship_bursary', 'answers': request_bursary(**overrides)},
            format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(pk=response.data['id'])

    def test_a_student_can_file_one(self):
        self.assertEqual(self.file_one().status, ApplicationStatus.SUBMITTED)

    def test_the_breakdown_is_stored_as_rows(self):
        stored = self.file_one().answers['fund_breakdown']
        self.assertIsInstance(stored, list)
        self.assertEqual(stored[0]['purpose'], 'Overdue rent')
        self.assertEqual(stored[0]['amount'], '400.00')

    def test_the_stored_total_is_the_sum_of_the_stored_lines(self):
        application = self.file_one()
        lines = sum(Decimal(row['amount'])
                    for row in application.answers['fund_breakdown'])
        self.assertEqual(Decimal(application.answers['amount_requested']), lines)

    def test_the_director_prices_it_at_the_itemised_total(self):
        application = self.file_one()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)

        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data['total'])), TOTAL)

    def test_a_worker_cannot_price_it(self):
        application = self.file_one()
        self.client.force_authenticate(self.worker)
        self.assertEqual(
            self.client.post(f'/api/applications/{application.pk}/price/').status_code,
            403)

    def test_a_reviewer_reads_back_the_lines_and_what_was_tried(self):
        application = self.file_one()
        self.client.force_authenticate(self.worker)
        response = self.client.get(f'/api/applications/{application.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['answers']['fund_breakdown']), 3)
        self.assertIn('food bank',
                      response.data['answers']['other_supports_attempted'])

    def test_another_student_cannot_read_it(self):
        application = self.file_one()
        self.client.force_authenticate(make_user(email='other@hardship.test'))
        self.assertIn(
            self.client.get(f'/api/applications/{application.pk}/').status_code,
            (403, 404))
