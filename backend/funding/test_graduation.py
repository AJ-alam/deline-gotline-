"""The graduation award.

Three things carry money or a regulated identifier, and each is tested against
the path it actually travels rather than against the schema alone:

  * the credential decides the amount, so its stored values have to be the rate
    keys the rule prices from — a label reworded must not move anybody's award;
  * the SIN this form now asks for must reach the encrypted table on the *guest*
    path, which did not store one at all until this form needed it;
  * "pay someone else" must keep the award out of the payment file, because
    nothing in the run can redirect it and paying the student anyway is the one
    outcome the applicant asked against.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    ApplicantIdentifier, Application, ApplicationEvent, ApplicationStatus,
    ApplicationType, FundingStream, PolicySetting, RuleSet,
)
from funding.rules.engine import price
from funding.schemas import FieldType, ValidationError, get_schema
from funding.services import finance, workflow
from funding.services.decisions import record_decision
from funding.services.policy import PolicyBook
from funding.test_fixtures import TEST_SIN, answers_for

SCHEMA = get_schema('graduation_bursary')
URL = '/api/guest-applications/'


def claim(**overrides) -> dict:
    defaults = dict(
        full_name='Grace Graduate',
        email='grace.graduate@example.com',
        institution_name='Aurora College',
        program='Environmental Science',
        credential='bachelors_degree',
        graduation_date='2026-05-30',
        signature='Grace Graduate',
        doc_proof_of_completion='provided',
    )
    defaults.update(overrides)
    return answers_for('graduation_bursary', **defaults)


class FormContentTests(SimpleTestCase):
    """The questions the office's form asks."""

    def test_it_asks_everything_on_the_office_s_form(self):
        expected = {
            'full_name', 'date_of_birth', 'treaty_number', 'sin', 'phone', 'email',
            'city', 'province', 'postal_code',
            'institution_name', 'program', 'graduation_date', 'credential',
            'doc_proof_of_completion',
            'account_holder', 'transit_number', 'institution_number', 'account_number',
            'release_to_other',
            'declaration_confirmed', 'signature', 'signed_on',
        }
        self.assertTrue(expected <= set(SCHEMA.keys), expected - set(SCHEMA.keys))

    def test_it_falls_into_the_four_steps_the_office_asked_for(self):
        """Section names are what the client groups steps by, so a rename here
        without one in Apply.tsx renders as a step that lost its questions."""
        self.assertEqual(
            SCHEMA.sections,
            ('Student information', 'Current mailing address', 'Graduation details',
             'Documents', 'Payment', 'Release of funds', 'Declaration'),
        )

    def test_the_declaration_is_worded_as_the_office_words_it(self):
        field = SCHEMA.field('declaration_confirmed')
        self.assertEqual(field.type, FieldType.CONFIRM)
        self.assertEqual(
            field.help_text,
            'I declare that the information provided is true and complete. I '
            'understand that any false information will result in the '
            'suspension of my graduation award.',
        )

    def test_the_declaration_cannot_be_filed_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(claim(declaration_confirmed='false'))

    def test_the_date_signed_opens_on_today(self):
        self.assertTrue(SCHEMA.field('signed_on').defaults_to_today)

    def test_bank_details_are_required_here_unlike_everywhere_else(self):
        """There is no account behind a guest claim to fall back on."""
        for key in ('account_holder', 'transit_number',
                    'institution_number', 'account_number'):
            with self.subTest(key=key):
                self.assertTrue(SCHEMA.field(key).required, key)
                self.assertTrue(SCHEMA.field(key).private, key)

    def test_the_sin_is_optional_and_is_a_sin(self):
        """Refusing a bursary from the government's own funds for want of a
        federal reporting number would withhold money over a number nothing
        here spends."""
        field = SCHEMA.field('sin')
        self.assertEqual(field.type, FieldType.SIN)
        self.assertFalse(field.required)

    def test_the_sin_is_never_an_ordinary_answer(self):
        self.assertIn('sin', SCHEMA.private_keys)
        self.assertIn('sin', SCHEMA.sensitive_keys)


class CredentialTests(SimpleTestCase):
    """The answer that decides the amount."""

    def test_every_credential_is_a_rate_key_the_rule_can_price(self):
        """`graduation_bursary` is a flat_rate rule keyed on `{credential}`.

        A value with no matching rate prices at nothing and reports a missing
        rate — so the stored values are not free to drift from the rate keys,
        whatever the labels say.
        """
        # §9(E)'s table, entry for entry. Red Seal, Juris Doctor and
        # MD/DDS were missing, so a graduate holding one of them had to claim
        # under a credential that was not theirs and was paid accordingly.
        expected = {
            'high_school_diploma', 'certificate', 'trades_certificate',
            'trades_journeyperson', 'diploma', 'pilot_licence', 'red_seal',
            'bachelors_degree', 'masters_degree', 'doctorate', 'juris_doctor',
            'md_dds',
        }
        self.assertEqual(set(SCHEMA.field('credential').choice_values), expected)

    def test_a_credential_outside_the_list_is_refused(self):
        """Free text here is what silently paid a graduating Bachelor at the
        certificate rate."""
        with self.assertRaises(ValidationError):
            SCHEMA.clean(claim(credential='BSc'))


class GuestIdentifierTests(TestCase):
    """A regulated identifier on a claim filed by someone with no account.

    The guest path split the SIN out of `answers` — so it could be stored
    somewhere safer — and then stored it nowhere. The applicant typed a number
    that was never recorded, and nothing said so.
    """

    def setUp(self):
        self.client = APIClient()

    def submit(self, **overrides):
        """The guest endpoint answers with a reference number, not an id.

        Deliberately: it must not confirm whether an address is known to the
        office. The application is found by that reference.
        """
        response = self.client.post(
            URL, {'type': 'graduation_bursary', 'answers': claim(**overrides)},
            format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(
            pk=int(str(response.data['reference']).removeprefix('DGG-')))

    def test_the_sin_is_stored_encrypted_rather_than_dropped(self):
        application = self.submit(sin=TEST_SIN)
        stored = ApplicantIdentifier.objects.filter(application=application, kind='sin')
        self.assertTrue(stored.exists(), 'the SIN was validated and then discarded')

    def test_the_sin_is_not_in_the_answers(self):
        application = self.submit(sin=TEST_SIN)
        self.assertNotIn('sin', application.answers)

    def test_the_stored_value_is_not_the_number_in_plain_text(self):
        application = self.submit(sin=TEST_SIN)
        held = ApplicantIdentifier.objects.get(application=application, kind='sin')
        self.assertNotIn(TEST_SIN, held.ciphertext)
        # What a client is allowed to see, and the whole of it.
        self.assertEqual(held.last_three, TEST_SIN[-3:])

    def test_a_claim_without_a_sin_is_still_accepted(self):
        application = self.submit()
        self.assertFalse(ApplicantIdentifier.objects
                         .filter(application=application, kind='sin').exists())

    def test_the_bank_details_do_not_reach_the_answers_either(self):
        application = self.submit()
        for key in ('account_number', 'transit_number', 'institution_number'):
            self.assertNotIn(key, application.answers)


class ReleaseOfFundsTests(TestCase):
    """"Pay someone else" has to keep the award out of the automatic file.

    Nothing in the payment run can redirect a payment — that is an
    authorisation the office grants. So the only safe reading of the tick is
    that this one does not go out with the batch. Paying the student's own
    account regardless is the single outcome the applicant asked against.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        PolicySetting.objects.update_or_create(
            section='graduation_bursary', key='bachelors_degree',
            defaults=dict(label='bachelors_degree', value=Decimal('4000'), unit='$'))
        self.student = User.objects.create_user(
            'grace@test.com', 'pw12345678', first_name='Grace', last_name='Graduate',
            role=Role.STUDENT, is_deline_beneficiary=True, is_indian_act_registered=True)
        self.student.bank_accounts.create(
            account_holder='Grace Graduate', transit_number='12345',
            institution_number='001', account_number='9876543210')
        self.director = User.objects.create_user(
            'dir@test.com', 'pw12345678', first_name='D', last_name='Irector',
            role=Role.DIRECTOR)

    def approved_award(self, **answers):
        """An award carried through the real workflow and priced by the engine.

        Built by hand, this would prove only that `preview` filters a row
        somebody constructed — not that a claim a person actually filed reaches
        or misses the payment file.
        """
        application = Application.objects.create(
            student=self.student, type=ApplicationType.GRADUATION_BURSARY,
            stream=FundingStream.DGGR, schema_slug='graduation_bursary',
            status=ApplicationStatus.SUBMITTED,
            answers={'credential': 'bachelors_degree', **answers})
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.director)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.director)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)
        record_decision(application, actor=self.director)
        application.refresh_from_db()
        return application.awards.get()

    def test_an_ordinary_award_is_ready_to_pay(self):
        award = self.approved_award()
        ready, blocked = finance.preview()
        self.assertIn(award.pk, [row['award'].pk for row in ready])
        self.assertNotIn(award.pk, [row['award'].pk for row in blocked])

    def test_a_released_award_is_held_out_of_the_file(self):
        award = self.approved_award(release_to_other=True)
        ready, blocked = finance.preview()
        self.assertNotIn(award.pk, [row['award'].pk for row in ready],
                         'it would have been paid into the student\'s own account')
        self.assertIn(award.pk, [row['award'].pk for row in blocked])

    def test_the_reason_names_who_was_asked_for(self):
        """Blocked with no name is a phone call for every claim."""
        award = self.approved_award(release_to_other=True,
                                    release_recipient='Marie Graduate (mother)')
        _, blocked = finance.preview()
        reason = next(row['reason'] for row in blocked if row['award'].pk == award.pk)
        self.assertIn('Marie Graduate', reason)

    def test_an_untidied_false_does_not_hold_the_payment(self):
        """An unticked box is an answer, and it is not a release."""
        award = self.approved_award(release_to_other=False)
        ready, _ = finance.preview()
        self.assertIn(award.pk, [row['award'].pk for row in ready])


class PricingTests(TestCase):
    """The award is the published rate for the credential."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', verbosity=0)

    def setUp(self):
        for key, value in (('bachelors_degree', '4000'), ('certificate', '1000')):
            PolicySetting.objects.update_or_create(
                section='graduation_bursary', key=key,
                defaults=dict(label=key, value=Decimal(value), unit='$'))
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def priced(self, credential):
        application = Application.objects.create(
            student=None, type=ApplicationType.GRADUATION_BURSARY,
            stream=FundingStream.DGGR, schema_slug='graduation_bursary',
            answers={'credential': credential})
        decision = price(application, self.rule_set,
                         PolicyBook.for_application(application))
        return {outcome.code: outcome.amount for outcome in decision.applied}

    def test_a_degree_is_paid_at_the_degree_rate(self):
        self.assertEqual(self.priced('bachelors_degree')['graduation_bursary'],
                         Decimal('4000'))

    def test_a_certificate_is_paid_at_the_certificate_rate(self):
        """The two must differ, or the test above passes for any rate at all."""
        self.assertEqual(self.priced('certificate')['graduation_bursary'],
                         Decimal('1000'))
