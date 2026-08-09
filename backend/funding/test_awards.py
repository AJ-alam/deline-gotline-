"""Award calculation on the consolidated model.

Covers the rules the old service carried, plus the failure modes that made it
unsafe: shared state between concurrent calculations, silent $0 awards from
missing configuration, and award tiers chosen by substring-matching free text.
"""

import itertools
import threading
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from funding.models import (
    Application, ApplicationType, Award, FundingStream, PolicyChange, PolicySetting,
)
from funding.services.awards import apply_award, calculate
from funding.services.policy import MissingPolicyError, PolicyBook

User = get_user_model()
_counter = itertools.count(1)

RATES = [
    ('psssp_tuition', 'max_per_semester', '7000'),
    ('psssp_living', 'fulltime_no_dependents', '1800'),
    ('psssp_living', 'fulltime_with_dependents', '2400'),
    ('psssp_living', 'parttime_no_dependents', '900'),
    ('ucepp_tuition', 'max_per_semester', '5000'),
    ('ucepp_living', 'fulltime_no_dependents', '1500'),
    ('dggr_tuition', 'fulltime_per_semester', '3000'),
    ('dggr_living', 'fulltime_no_dependents', '600'),
    ('dggr_extra_tuition', 'threshold_per_semester', '10000'),
    ('dggr_extra_tuition', 'max_percent_covered', '80'),
    ('dggr_extra_tuition', 'max_per_semester', '15000'),
    ('system_config', 'book_allowance', '500'),
    ('graduation_bursary', 'certificate', '1000'),
    ('graduation_bursary', 'bachelors_degree', '4000'),
]


def seed_rates():
    for section, key, value in RATES:
        PolicySetting.objects.update_or_create(
            section=section, key=key,
            defaults=dict(label=key, value=Decimal(value), unit='$'),
        )


def make_application(**kwargs):
    student = User.objects.create_user(
        email=f'aw{next(_counter)}@test.com', password='pw123456',
        full_name='Student', role='student',
    )
    answers = {
        'course_load': 'full_time',
        'semester_start': '2026-09-01',
        'semester_end': '2026-12-31',
        'confirmed_tuition': '6000',
    }
    answers.update(kwargs.pop('answers', {}))
    defaults = dict(
        type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
        schema_slug='form-a', answers=answers,
    )
    defaults.update(kwargs)
    return Application.objects.create(student=student, **defaults)


class StandardFundingTests(TestCase):

    def setUp(self):
        seed_rates()

    def test_tuition_is_capped_and_living_scales_with_months(self):
        breakdown = calculate(make_application())
        amounts = {line.category: line.amount for line in breakdown.lines}
        self.assertEqual(amounts['Tuition (PSSSP)'], Decimal('6000'))     # billed < cap
        self.assertEqual(amounts['Living Allowance (PSSSP)'], Decimal('1800') * 4)
        self.assertEqual(amounts['Books & Supplies'], Decimal('500'))

    def test_tuition_never_exceeds_the_actual_bill(self):
        breakdown = calculate(make_application(answers={'confirmed_tuition': '2500'}))
        amounts = {line.category: line.amount for line in breakdown.lines}
        self.assertEqual(amounts['Tuition (PSSSP)'], Decimal('2500'))

    def test_nothing_is_awarded_for_tuition_until_it_is_confirmed(self):
        """Assuming the cap overpays every student whose real tuition is lower."""
        app = make_application(answers={'confirmed_tuition': '', 'tuition_requested': ''})
        breakdown = calculate(app)
        amounts = {line.category: line.amount for line in breakdown.lines}
        self.assertEqual(amounts['Tuition (PSSSP)'], Decimal('0.00'))
        self.assertGreater(amounts['Living Allowance (PSSSP)'], 0)   # living still paid

    def test_part_time_and_dependents_select_a_different_living_rate(self):
        app = make_application(answers={'course_load': 'part_time'})
        breakdown = calculate(app)
        amounts = {line.category: line.amount for line in breakdown.lines}
        self.assertEqual(amounts['Living Allowance (PSSSP)'], Decimal('900') * 4)

        app = make_application(answers={'has_dependents': True})
        amounts = {l.category: l.amount for l in calculate(app).lines}
        self.assertEqual(amounts['Living Allowance (PSSSP)'], Decimal('2400') * 4)

    def test_streams_stack_and_no_two_fund_the_same_dollar(self):
        """§4.1 — living is additive; tuition is allocated against the real bill."""
        app = make_application(answers={
            'confirmed_tuition': '9000', 'funding_stream': 'dggr',
        })
        breakdown = calculate(app)
        amounts = {line.category: line.amount for line in breakdown.lines}
        # PSSSP covers 7000 of the 9000 bill; DGGR tops up the remaining 2000
        # even though its own cap is 3000.
        self.assertEqual(amounts['Tuition (PSSSP)'], Decimal('7000'))
        self.assertEqual(amounts['Tuition Top-Up (DGGR)'], Decimal('2000'))
        # Living allowances are additive across streams.
        self.assertEqual(amounts['Living Allowance (DGGR)'], Decimal('600') * 4)

    def test_sfa_recipients_are_excluded_from_cdfn_funding(self):
        """§4.2 — and the exclusion must not be undone by a fallback."""
        app = make_application(answers={'receives_sfa': True})
        breakdown = calculate(app)
        self.assertEqual(breakdown.total, Decimal('0.00'))
        self.assertTrue(any('SFA' in note for note in breakdown.notes))

    def test_extra_relief_is_inclusive_of_the_dggr_top_up(self):
        """§4.3 — relief is the difference above the top-up, not an addition,
        and it can never exceed the tuition still owing."""
        app = make_application(answers={
            'confirmed_tuition': '20000', 'funding_stream': 'dggr',
        })
        amounts = {l.category: l.amount for l in calculate(app).lines}
        # 80% of 20000 = 16000, capped at 15000, less the 3000 DGGR top-up = 12000.
        # But PSSSP (7000) and the top-up (3000) already covered 10000 of the
        # bill, so only 10000 is still owed and relief stops there.
        self.assertEqual(amounts['Extra Tuition Relief'], Decimal('10000'))
        # The student is funded to exactly the bill, never beyond it.
        total_tuition = sum(
            line.amount for line in calculate(app).lines if 'Tuition' in line.category
        )
        self.assertEqual(total_tuition, Decimal('20000'))

    def test_no_relief_below_the_threshold(self):
        app = make_application(answers={
            'confirmed_tuition': '9000', 'funding_stream': 'dggr',
        })
        categories = {line.category for line in calculate(app).lines}
        self.assertNotIn('Extra Tuition Relief', categories)

    def test_every_line_carries_the_rule_that_produced_it(self):
        for line in calculate(make_application()).lines:
            self.assertTrue(line.rule, f'{line.category} has no explanation')


class CredentialTierTests(TestCase):
    """The 'BSc pays the certificate rate' bug class."""

    def setUp(self):
        seed_rates()

    def test_award_tier_follows_the_stored_credential(self):
        app = make_application(
            type=ApplicationType.GRADUATION_BURSARY, stream=FundingStream.DGGR,
            answers={'credential': 'bachelors_degree'},
        )
        amounts = {l.category: l.amount for l in calculate(app).lines}
        self.assertEqual(amounts['Graduation Bursary'], Decimal('4000'))

    def test_a_missing_credential_is_reported_not_defaulted_to_the_cheapest(self):
        app = make_application(
            type=ApplicationType.GRADUATION_BURSARY, stream=FundingStream.DGGR,
            answers={},
        )
        breakdown = calculate(app)
        self.assertEqual(breakdown.total, Decimal('0.00'))
        self.assertTrue(breakdown.notes)


class MissingPolicyTests(TestCase):

    def test_apply_refuses_to_write_an_award_from_absent_configuration(self):
        app = make_application()       # no rates seeded
        with self.assertRaises(MissingPolicyError) as ctx:
            apply_award(app)
        self.assertTrue(ctx.exception.missing)

    def test_no_awards_are_written_when_policy_is_incomplete(self):
        app = make_application()
        with self.assertRaises(MissingPolicyError):
            apply_award(app)
        self.assertFalse(app.awards.exists())
        app.refresh_from_db()
        self.assertEqual(app.awarded_total, Decimal('0.00'))

    def test_preview_still_renders_so_staff_can_see_why(self):
        app = make_application()
        policies = PolicyBook.for_application(app)
        calculate(app, policies)       # must not raise
        self.assertTrue(policies.missing)


class EffectiveDateTests(TestCase):
    """§7.5 — an application is priced with the rates in force when submitted."""

    def setUp(self):
        seed_rates()

    def test_a_later_rate_change_does_not_reprice_an_earlier_application(self):
        setting = PolicySetting.objects.get(section='psssp_living',
                                            key='fulltime_no_dependents')
        setting.value = Decimal('2500')
        setting.save()
        PolicyChange.objects.create(
            setting=setting, previous_value=Decimal('1800'),
            new_value=Decimal('2500'),
            effective_date=date.today() + timedelta(days=30),
        )
        app = make_application()
        amounts = {l.category: l.amount for l in calculate(app).lines}
        # The increase has not taken effect yet — the old rate applies.
        self.assertEqual(amounts['Living Allowance (PSSSP)'], Decimal('1800') * 4)


class ConcurrencyTests(TestCase):
    """Each calculation carries its own policy state.

    Previously the effective date lived in a class attribute, so two overlapping
    calculations overwrote each other and an application could be priced with
    another application's date.
    """

    def setUp(self):
        seed_rates()

    def test_two_concurrent_calculations_keep_their_own_effective_date(self):
        early = PolicyBook(as_of=date(2024, 1, 15))
        late = PolicyBook(as_of=date(2026, 8, 9))
        observed = {}
        both_ready = threading.Barrier(2)

        def run(name, book):
            both_ready.wait(timeout=5)
            observed[name] = book.as_of

        threads = [
            threading.Thread(target=run, args=('early', early)),
            threading.Thread(target=run, args=('late', late)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(observed['early'], date(2024, 1, 15))
        self.assertEqual(observed['late'], date(2026, 8, 9))


class PersistenceTests(TestCase):

    def setUp(self):
        seed_rates()

    def test_awards_are_written_and_total_recorded(self):
        app = make_application()
        breakdown = apply_award(app)
        app.refresh_from_db()
        self.assertEqual(app.awarded_total, breakdown.total)
        self.assertTrue(app.awards.exists())
        self.assertTrue(all(a.amount > 0 for a in app.awards.all()))

    def test_recalculating_replaces_pending_awards_rather_than_duplicating(self):
        app = make_application()
        apply_award(app)
        first = app.awards.count()
        apply_award(app)
        self.assertEqual(app.awards.count(), first)
