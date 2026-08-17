"""The academic achievement scholarship.

The GPA decides the amount, which makes this the form where a display string is
most dangerous: an answer that matches no expected band silently pays the
cheapest one, and a threshold written in two places pays against whichever copy
the engine happens to read.

So the things tested here are the ones that carry money:

  * the grade is a validated percentage, not free text;
  * the bands are the *rates* — both the amounts and the thresholds — so an
    administrator moving a threshold on the policy screen moves what is paid;
  * a missing rate awards nothing and says so, rather than paying the top band
    to everybody.
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
from funding.rules.effects import EffectError, get_effect
from funding.rules.engine import price
from funding.schemas import FieldType, ValidationError, get_schema
from funding.services import workflow
from funding.services.policy import PolicyBook
from funding.test_fixtures import answers_for

SCHEMA = get_schema('academic_scholarship')

BANDS = (
    ('high_achievement_award', '1000'),
    ('mid_achievement_award', '500'),
    ('high_threshold_percent', '80'),
    ('mid_threshold_percent', '70'),
)


def claim(**overrides) -> dict:
    defaults = dict(
        full_name='Majid Khan',
        institution_name='Aurora College',
        semester='fall',
        academic_year='2026-2027',
        gpa_achieved='85',
        transcripts_status='uploading_now',
        doc_transcript='provided',
        signature='Majid Khan',
    )
    defaults.update(overrides)
    return answers_for('academic_scholarship', **defaults)


class FormContentTests(SimpleTestCase):
    """The questions the office's form asks."""

    def test_it_asks_exactly_what_the_office_asked_for(self):
        self.assertEqual(
            set(SCHEMA.keys),
            {
                'full_name', 'beneficiary_number', 'institution_name',
                'semester', 'academic_year',
                'gpa_achieved', 'transcripts_status', 'doc_transcript',
                'declaration_confirmed', 'signature', 'signed_on',
            },
        )

    def test_it_falls_into_the_three_steps_the_screens_show(self):
        self.assertEqual(
            SCHEMA.sections,
            ('Program information', 'Achievements', 'Declaration'),
        )

    def test_the_declaration_is_worded_as_the_office_words_it(self):
        field = SCHEMA.field('declaration_confirmed')
        self.assertEqual(field.type, FieldType.CONFIRM)
        self.assertEqual(
            field.help_text,
            'I confirm that the information provided is accurate. I understand '
            'that eligibility for the scholarship is subject to enrollment '
            'verification and meeting the DGG Education Policy requirements.',
        )

    def test_the_declaration_cannot_be_filed_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(claim(declaration_confirmed='false'))

    def test_the_date_signed_opens_on_today(self):
        self.assertTrue(SCHEMA.field('signed_on').defaults_to_today)

    def test_no_bank_details_are_asked_for(self):
        """This cannot be claimed without an account, so finance already has
        somewhere to pay. A second set of details is a second set that can
        disagree with the first."""
        for key in ('account_holder', 'transit_number',
                    'institution_number', 'account_number'):
            self.assertNotIn(key, SCHEMA.keys)

    def test_the_award_amounts_are_not_written_into_the_form(self):
        """They are policy rates the office edits without a deploy.

        Quoting them in help text puts the same figure in two places that agree
        only by habit — and the office's own mock-up already disagreed with the
        seeded rates, which is exactly how that goes wrong.
        """
        text = ' '.join(field.help_text for field in SCHEMA.fields)
        for amount in ('$1,000', '$500', '$1000'):
            self.assertNotIn(amount, text)


class GradeTests(SimpleTestCase):
    """The answer that decides the amount."""

    def test_the_grade_is_a_bounded_percentage(self):
        field = SCHEMA.field('gpa_achieved')
        self.assertEqual(field.type, FieldType.PERCENT)
        self.assertTrue(field.required)

    def test_a_grade_over_a_hundred_is_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(claim(gpa_achieved='160'))

    def test_a_grade_that_is_not_a_number_is_refused(self):
        """Free text is what silently paid a graduating Bachelor at the
        certificate rate on the neighbouring form."""
        with self.assertRaises(ValidationError):
            SCHEMA.clean(claim(gpa_achieved='A minus'))

    def test_a_percent_sign_is_accepted_and_stripped(self):
        """The placeholder on the screen reads 'e.g. 85%'."""
        self.assertEqual(SCHEMA.clean(claim(gpa_achieved='85%'))['gpa_achieved'],
                         Decimal('85'))

    def test_the_transcript_is_required_whatever_its_status(self):
        field = SCHEMA.field('doc_transcript')
        self.assertTrue(field.required)
        for status in SCHEMA.field('transcripts_status').choice_values:
            with self.subTest(status=status):
                with self.assertRaises(ValidationError):
                    SCHEMA.clean({k: v for k, v in claim(transcripts_status=status).items()
                                  if k != 'doc_transcript'})


class ThresholdTests(TestCase):
    """The bands are policy, not literals in the rule.

    `high_threshold_percent` and `mid_threshold_percent` were published as
    editable rates while the rule carried 80 and 70 written into it. An
    administrator could change 'High achievement threshold' on the policy
    screen, watch it save with a history entry, and change nothing — the same
    defect as a dashboard count that can only ever be zero, except that it
    looked like it worked.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        self.set_bands(*BANDS)
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def set_bands(self, *pairs):
        for key, value in pairs:
            PolicySetting.objects.update_or_create(
                section='academic_scholarship', key=key,
                defaults=dict(label=key, value=Decimal(value), unit='$'))

    def priced(self, gpa):
        application = Application.objects.create(
            student=None, type=ApplicationType.ACADEMIC_SCHOLARSHIP,
            stream=FundingStream.DGGR, schema_slug='academic_scholarship',
            answers={'gpa_achieved': str(gpa)})
        decision = price(application, self.rule_set,
                         PolicyBook.for_application(application))
        amounts = {o.code: o.amount for o in decision.applied}
        return amounts.get('academic_scholarship', Decimal('0')), decision

    def test_a_grade_at_the_top_threshold_takes_the_top_band(self):
        self.assertEqual(self.priced(80)[0], Decimal('1000'))

    def test_a_grade_in_the_middle_band_takes_the_middle_one(self):
        """Distinct amounts, or the test above passes for any band at all."""
        self.assertEqual(self.priced(75)[0], Decimal('500'))

    def test_a_grade_under_every_threshold_is_awarded_nothing(self):
        self.assertEqual(self.priced(69)[0], Decimal('0'))

    def test_moving_the_threshold_moves_what_is_paid(self):
        """The point of the whole change. At 75 the student is mid-band; drop
        the top threshold to 75 and the same grade takes the top band."""
        self.assertEqual(self.priced(75)[0], Decimal('500'))
        self.set_bands(('high_threshold_percent', '75'))
        self.assertEqual(self.priced(75)[0], Decimal('1000'))

    def test_raising_the_threshold_moves_it_back(self):
        self.set_bands(('high_threshold_percent', '90'))
        self.assertEqual(self.priced(85)[0], Decimal('500'))

    def test_a_missing_threshold_awards_nothing_and_says_so(self):
        """Not the top band to everybody. A deleted rate must fail loudly."""
        PolicySetting.objects.filter(section='academic_scholarship',
                                     key='high_threshold_percent').delete()
        amount, decision = self.priced(95)
        self.assertEqual(amount, Decimal('500'), 'it fell through to the mid band')
        self.assertIn('academic_scholarship:high_threshold_percent',
                      decision.missing_rates)

    def test_with_no_thresholds_at_all_nothing_is_awarded(self):
        PolicySetting.objects.filter(
            section='academic_scholarship',
            key__in=('high_threshold_percent', 'mid_threshold_percent')).delete()
        amount, decision = self.priced(95)
        self.assertEqual(amount, Decimal('0'))
        self.assertFalse(decision.is_complete, 'a missing rate was not reported')


class TieredEffectTests(SimpleTestCase):
    """A tier has to say when it applies."""

    def test_a_tier_with_neither_threshold_is_refused_at_import(self):
        effect = get_effect('tiered')
        with self.assertRaises(EffectError):
            effect.validate({
                'kind': 'tiered', 'value_field': 'gpa_achieved',
                'tiers': [{'section': 'academic_scholarship', 'key': 'x'}],
            })

    def test_a_literal_threshold_is_still_accepted(self):
        """Nothing else was migrated, and a rule set already in the database
        carries the old shape."""
        effect = get_effect('tiered')
        effect.validate({
            'kind': 'tiered', 'value_field': 'gpa_achieved',
            'tiers': [{'at_least': 80, 'section': 's', 'key': 'k'}],
        })


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@scholarship.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class ThroughTheOfficeTests(TestCase):
    """Student files, worker reviews, director decides and prices."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        for key, value in BANDS:
            PolicySetting.objects.update_or_create(
                section='academic_scholarship', key=key,
                defaults=dict(label=key, value=Decimal(value), unit='$'))
        self.student = make_user(email='scholar@scholarship.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@scholarship.test')
        self.director = make_user(Role.DIRECTOR, 'director@scholarship.test')
        self.client = APIClient()

    def file_one(self, **overrides):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            '/api/applications/',
            {'type': 'academic_scholarship', 'answers': claim(**overrides)},
            format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(pk=response.data['id'])

    def test_a_student_can_file_one(self):
        self.assertEqual(self.file_one().status, ApplicationStatus.SUBMITTED)

    def test_the_grade_is_stored_as_a_number_not_the_text_that_was_typed(self):
        application = self.file_one(gpa_achieved='85%')
        self.assertEqual(Decimal(str(application.answers['gpa_achieved'])),
                         Decimal('85'))

    def test_it_carries_no_enrolment_gate(self):
        application = self.file_one()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.AWAITING_DECISION)

    def test_a_worker_cannot_price_it(self):
        application = self.file_one()
        self.client.force_authenticate(self.worker)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(response.status_code, 403)

    def test_the_director_prices_it_at_the_band_the_grade_reaches(self):
        application = self.file_one(gpa_achieved='85')
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)

        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data['total'])), Decimal('1000'))

    def test_the_trace_says_which_band_and_why(self):
        """A funding body has to explain an award years later."""
        application = self.file_one(gpa_achieved='75')
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)

        self.client.force_authenticate(self.director)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        rule = next(row for row in response.data['trace']['rules']
                    if row['code'] == 'academic_scholarship')
        self.assertTrue(rule['applied'])
        self.assertIn('70', rule['reason'])

    def test_a_student_cannot_price_their_own(self):
        application = self.file_one()
        self.client.force_authenticate(self.student)
        response = self.client.post(f'/api/applications/{application.pk}/price/')
        self.assertEqual(response.status_code, 403)

    def test_another_student_cannot_read_it(self):
        application = self.file_one()
        self.client.force_authenticate(make_user(email='other@scholarship.test'))
        response = self.client.get(f'/api/applications/{application.pk}/')
        self.assertIn(response.status_code, (403, 404))
