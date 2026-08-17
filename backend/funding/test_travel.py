"""The travel claim: an itemised reimbursement.

What has to hold, in the order it matters:

  * the amount that gets paid is the sum of the lines the applicant itemised,
    and there is no second place for a total to come from;
  * a receipt is a file, several of them, and each one survives the round trip
    as something a reviewer can open;
  * the two list-shaped field types this form introduced — a table of rows and
    a many-file question — are stored as lists and not as the text of a Python
    repr.

The last one is not hypothetical. `jsonable` stringified anything that was not
a JSON scalar, which for a list of rows produced the literal answer
"[{'amount': Decimal('812.50')}]".
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.api.serializers import jsonable
from funding.models import (
    Application, ApplicationType, FundingStream, PolicySetting, RuleSet,
)
from funding.rules.engine import price
from funding.schemas import (
    ApplicationSchema, Field, FieldType, SchemaError, ValidationError,
    get_schema,
)
from funding.services.policy import PolicyBook
from funding.test_fixtures import answers_for
from funding.test_rules import rate_of, seed_rates

SCHEMA = get_schema('travel')

# A real trip: a flight, a night in a hotel and the cab from the airport.
EXPENSES = [
    {'description': 'Air North YZF–YEG', 'amount': '812.50', 'receipt_attached': True},
    {'description': 'Hotel, one night', 'amount': '189.00', 'receipt_attached': True},
    {'description': 'Taxi from airport', 'amount': '48.25', 'receipt_attached': True},
]
TOTAL = Decimal('1049.75')


def claim(**overrides) -> dict:
    """A complete travel claim, built from the schema so it cannot go stale."""
    defaults = dict(
        expenses=EXPENSES,
        doc_receipts=['document:1', 'document:2', 'document:3'],
        departure_date='2026-09-01',
        travel_purpose='graduation',
    )
    defaults.update(overrides)
    return answers_for('travel', **defaults)


class TotalClaimedTests(SimpleTestCase):
    """The figure that gets paid, and where it is allowed to come from."""

    def test_the_total_is_the_expense_lines_added_up(self):
        self.assertEqual(SCHEMA.clean(claim())['amount_requested'], TOTAL)

    def test_a_total_sent_by_the_client_is_discarded(self):
        """The whole reason the total is not asked for.

        `travel_assistance` pays `amount_requested` up to the cap. If a client
        could supply it, the amount paid would be a figure that nothing on the
        form itemises — and the expense breakdown would be decoration.
        """
        cleaned = SCHEMA.clean(claim(amount_requested='99999.00'))
        self.assertEqual(cleaned['amount_requested'], TOTAL)

    def test_a_total_sent_by_the_client_is_not_even_validated(self):
        """Discarded before validation, not overwritten after it.

        A client that echoed back what the detail endpoint gave it — a total
        formatted for display, or an empty one on a claim with no lines yet —
        would otherwise have its whole submission refused because a figure the
        server itself produced did not parse. Deriving over the top would hide
        that: the answer would come out right and the submission would already
        have been rejected.
        """
        cleaned = SCHEMA.clean(claim(amount_requested='not a number'))
        self.assertEqual(cleaned['amount_requested'], TOTAL)

    def test_the_total_is_not_a_question_anyone_is_asked(self):
        self.assertTrue(SCHEMA.field('amount_requested').computed)
        self.assertFalse(SCHEMA.field('amount_requested').required)

    def test_blank_lines_do_not_reach_the_total(self):
        with_gaps = [
            EXPENSES[0],
            {'description': '', 'amount': '', 'receipt_attached': False},
            EXPENSES[1],
            {'description': '', 'amount': ''},
            EXPENSES[2],
        ]
        cleaned = SCHEMA.clean(claim(expenses=with_gaps))
        self.assertEqual(len(cleaned['expenses']), 3)
        self.assertEqual(cleaned['amount_requested'], TOTAL)

    def test_a_claim_of_nothing_but_blank_lines_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(claim(expenses=[{'description': '', 'amount': ''}]))
        self.assertIn('expenses', caught.exception.errors)


class ExpenseRowTests(SimpleTestCase):
    """Each line is cleaned by the same rules its type obeys anywhere else."""

    def test_an_amount_is_cleaned_like_any_other_money_field(self):
        cleaned = SCHEMA.clean(claim(expenses=[
            {'description': 'Flight', 'amount': '$1,200', 'receipt_attached': 'yes'},
        ]))
        self.assertEqual(cleaned['expenses'][0]['amount'], Decimal('1200.00'))
        self.assertIs(cleaned['expenses'][0]['receipt_attached'], True)

    def test_a_line_with_an_amount_and_no_description_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(claim(expenses=[{'description': '', 'amount': '40'}]))
        self.assertIn('Row 1', caught.exception.errors['expenses'])

    def test_the_message_says_which_line_is_wrong(self):
        """Three lines in, 'Amount must be an amount' is not enough to act on."""
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(claim(expenses=[
                EXPENSES[0],
                EXPENSES[1],
                {'description': 'Taxi', 'amount': 'about forty dollars'},
            ]))
        self.assertIn('Row 3', caught.exception.errors['expenses'])

    def test_a_column_no_form_asks_for_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(claim(expenses=[
                {'description': 'Flight', 'amount': '100', 'approved_by': 'me'},
            ]))
        self.assertIn('approved_by', caught.exception.errors['expenses'])

    def test_more_lines_than_the_cap_are_refused(self):
        limit = SCHEMA.field('expenses').max_items
        too_many = [{'description': f'Item {n}', 'amount': '1'} for n in range(limit + 1)]
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(claim(expenses=too_many))
        self.assertIn('expenses', caught.exception.errors)

    def test_exactly_the_cap_is_accepted(self):
        limit = SCHEMA.field('expenses').max_items
        rows = [{'description': f'Item {n}', 'amount': '1'} for n in range(limit)]
        self.assertEqual(len(SCHEMA.clean(claim(expenses=rows))['expenses']), limit)


class ReceiptTests(SimpleTestCase):
    """Receipts are mandatory, and there is never only one of them."""

    def test_every_attached_receipt_is_kept(self):
        cleaned = SCHEMA.clean(claim(
            doc_receipts=['document:7', 'document:8', 'document:9']))
        self.assertEqual(cleaned['doc_receipts'],
                         ['document:7', 'document:8', 'document:9'])

    def test_a_claim_with_no_receipts_is_refused(self):
        for empty in ([], '', None):
            with self.subTest(empty=empty):
                with self.assertRaises(ValidationError) as caught:
                    SCHEMA.clean(claim(doc_receipts=empty))
                self.assertIn('doc_receipts', caught.exception.errors)

    def test_the_same_receipt_attached_twice_is_counted_once(self):
        """A slip, not an error: it would be reviewed as two receipts."""
        cleaned = SCHEMA.clean(claim(
            doc_receipts=['document:7', 'document:8', 'document:7']))
        self.assertEqual(cleaned['doc_receipts'], ['document:7', 'document:8'])

    def test_one_receipt_sent_on_its_own_is_still_a_list(self):
        cleaned = SCHEMA.clean(claim(doc_receipts='document:7'))
        self.assertEqual(cleaned['doc_receipts'], ['document:7'])

    def test_more_receipts_than_the_cap_are_refused(self):
        limit = SCHEMA.field('doc_receipts').max_items
        with self.assertRaises(ValidationError) as caught:
            SCHEMA.clean(claim(
                doc_receipts=[f'document:{n}' for n in range(limit + 1)]))
        self.assertIn('doc_receipts', caught.exception.errors)


class StoredShapeTests(TestCase):
    """What the column actually holds after a submission.

    Through the API rather than through the schema, because the defect this
    guards against was in `jsonable` — between validation and the write.
    """

    def setUp(self):
        self.student = User.objects.create_user(
            'traveller@test.com', 'pw12345678', first_name='Test',
            last_name='Traveller', role=Role.STUDENT,
            is_deline_beneficiary=True, is_indian_act_registered=True)
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def submit(self, **overrides):
        response = self.client.post(
            '/api/applications/',
            {'type': 'travel', 'answers': claim(**overrides)}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(pk=response.data['id'])

    def test_the_expense_lines_are_stored_as_rows(self):
        stored = self.submit().answers['expenses']
        self.assertIsInstance(stored, list)
        self.assertEqual(stored[0]['description'], 'Air North YZF–YEG')
        # A string, because a Decimal cannot go through JSON without losing
        # cents — but the row itself is still a row.
        self.assertEqual(stored[0]['amount'], '812.50')

    def test_the_receipts_are_stored_as_a_list_of_references(self):
        stored = self.submit().answers['doc_receipts']
        self.assertEqual(stored, ['document:1', 'document:2', 'document:3'])

    def test_the_stored_total_is_the_sum_of_the_stored_lines(self):
        application = self.submit()
        lines = sum(Decimal(row['amount']) for row in application.answers['expenses'])
        self.assertEqual(Decimal(application.answers['amount_requested']), lines)

    def test_the_detail_endpoint_returns_the_lines_a_reviewer_needs(self):
        application = self.submit()
        response = self.client.get(f'/api/applications/{application.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['answers']['expenses']), 3)

    def test_bank_details_stay_out_of_the_answers_here_too(self):
        """The travel claim asks for them, so the same split has to apply."""
        application = self.submit(
            account_holder='Test Traveller', transit_number='12345',
            institution_number='001', account_number='1234567')
        self.assertNotIn('account_number', application.answers)


class PricingTests(TestCase):
    """The derived total is the figure the rule actually reads."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', verbosity=0)

    # The cap the fixture claim is priced against: a graduation trip for a
    # claimant with no dependants. Read from the office's list rather than
    # invented here, which is how this file came to assert a $1,200 cap against
    # a policy that says $5,000.
    CAP_KEY = ('travel', 'max_graduation_no_dependents')

    def setUp(self):
        seed_rates()
        self.cap = rate_of(*self.CAP_KEY)
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def price_claim(self, **overrides):
        # Written through `jsonable`, the same way a submission is, so what is
        # priced here is what the column would actually hold.
        cleaned = SCHEMA.clean(claim(**overrides))
        application = Application.objects.create(
            student=None, type=ApplicationType.TRAVEL, stream=FundingStream.DGGR,
            schema_slug='travel', answers=jsonable(cleaned),
        )
        decision = price(application, self.rule_set,
                         PolicyBook.for_application(application))
        return {outcome.code: outcome.amount for outcome in decision.applied}

    def test_a_claim_under_the_cap_is_paid_at_its_itemised_total(self):
        self.assertEqual(self.price_claim()['travel_assistance'], TOTAL)

    def test_a_claim_over_the_cap_is_paid_at_the_cap(self):
        big = [{'description': 'Charter flight',
                'amount': str(self.cap + Decimal('1000'))}]
        self.assertEqual(self.price_claim(expenses=big)['travel_assistance'],
                         self.cap)


class SchemaGuardTests(SimpleTestCase):
    """The mistakes a schema can make with the new field types.

    All raised at import, never at runtime: a malformed schema should stop the
    process starting rather than produce a strange answer to one applicant.
    """

    def test_a_computed_field_cannot_also_be_required(self):
        with self.assertRaises(SchemaError):
            Field('total', 'Total', FieldType.MONEY, required=True, computed=True)

    def test_a_table_must_declare_its_columns(self):
        with self.assertRaises(SchemaError):
            Field('rows', 'Rows', FieldType.TABLE)

    def test_columns_belong_only_to_a_table(self):
        with self.assertRaises(SchemaError):
            Field('name', 'Name', FieldType.TEXT,
                  columns=(Field('a', 'A', FieldType.TEXT),))

    def test_a_file_cannot_be_a_column(self):
        """An upload inside a repeating row is a different interaction."""
        with self.assertRaises(SchemaError):
            Field('rows', 'Rows', FieldType.TABLE,
                  columns=(Field('doc', 'Doc', FieldType.FILE),))

    def test_a_declaration_cannot_be_a_column(self):
        with self.assertRaises(SchemaError):
            Field('rows', 'Rows', FieldType.TABLE,
                  columns=(Field('ok', 'OK', FieldType.CONFIRM, required=True),))

    def test_a_computed_field_with_nothing_deriving_it_is_refused(self):
        with self.assertRaises(SchemaError):
            ApplicationSchema(
                slug='never_registered',
                fields=(Field('total', 'Total', FieldType.MONEY, computed=True),),
            )

    def test_deriving_a_key_no_field_declares_is_refused(self):
        schema = ApplicationSchema(
            slug='never_registered',
            fields=(
                Field('given', 'Given', FieldType.TEXT),
                Field('total', 'Total', FieldType.MONEY, computed=True),
            ),
            derive=lambda answers: {'invented': '1'},
        )
        with self.assertRaises(SchemaError):
            schema.clean({'given': 'x'})


class FormContentTests(SimpleTestCase):
    """The questions the office's paper form asks, and one it does not.

    Listed because they arrived from a screenshot rather than from the code,
    and a form that quietly loses a question fails silently — the claim is
    simply assessed without it.
    """

    def test_the_claim_asks_everything_the_paper_form_does(self):
        expected = {
            'first_name', 'last_name', 'date_of_birth', 'treaty_number',
            'travel_from', 'travel_to', 'departure_date', 'return_date',
            'travel_mode', 'total_km',
            'expenses', 'amount_requested', 'doc_receipts',
            'declaration_confirmed', 'signature',
        }
        self.assertTrue(expected <= set(SCHEMA.keys), expected - set(SCHEMA.keys))

    def test_the_purpose_of_travel_survives_although_the_paper_form_omits_it(self):
        """It is the cap.

        `seed_rules.travel_assistance` resolves the rate key
        `max_{travel_purpose}_{dependants}`, so dropping the question to match
        the screenshot would leave every claim uncapped.

        'compassionate' is gone: the policy funds travel to and from study
        (§7(C)) and travel to a graduation ceremony (§7(D)), and nothing else.
        Offered as a choice, it resolved a rate key that does not exist, so the
        claim priced at nothing and reported an unconfigured rate rather than an
        ineligible purpose.
        """
        field = SCHEMA.field('travel_purpose')
        self.assertTrue(field.required)
        self.assertEqual(
            set(field.choice_values),
            {'start_of_study', 'end_of_study', 'graduation'},
        )

    def test_the_declaration_is_worded_as_the_office_words_it(self):
        field = SCHEMA.field('declaration_confirmed')
        self.assertEqual(field.type, FieldType.CONFIRM)
        self.assertIn('false information', field.help_text)
        self.assertIn('denial of reimbursement', field.help_text)

    def test_the_declaration_cannot_be_filed_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(claim(declaration_confirmed='false'))

    def test_the_steps_a_student_walks_have_every_section(self):
        """The frontend groups sections into three steps by name.

        A section renamed here and not there renders as a step that lost its
        questions, so the names are asserted rather than left to agree by
        habit.
        """
        self.assertEqual(
            SCHEMA.sections,
            ('Student', 'Travel', 'Expenses', 'Receipts', 'Payment', 'Declaration'),
        )
