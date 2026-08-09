"""Rules engine.

The engine must reproduce the amounts the original service produced — the rules
are the same policy, expressed as data — while removing the failure modes that
made the original unsafe.
"""

import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from funding.models import (
    Application, ApplicationType, Award, FundingStream, PolicySetting, Rule, RuleSet,
)
from funding.rules import conditions
from funding.rules.effects import EffectError, available_kinds, validate_effect
from funding.rules.engine import price
from funding.services.policy import PolicyBook

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
    ('academic_scholarship', 'high_achievement_award', '2000'),
    ('academic_scholarship', 'mid_achievement_award', '1000'),
    ('hardship_bursary', 'max_per_student', '3000'),
]


def seed_rates():
    for section, key, value in RATES:
        PolicySetting.objects.update_or_create(
            section=section, key=key,
            defaults=dict(label=key, value=Decimal(value), unit='$'),
        )


def make_application(**kwargs):
    student = User.objects.create_user(
        email=f'r{next(_counter)}@test.com', password='pw123456',
        first_name='Test', last_name='Student', role='student',
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
        schema_slug='admission', answers=answers,
    )
    defaults.update(kwargs)
    return Application.objects.create(student=student, **defaults)


class ConditionTests(SimpleTestCase):

    def test_operators(self):
        ctx = {'course_load': 'full_time', 'gpa': '82', 'sfa': False, 'note': ''}
        cases = [
            ({'field': 'course_load', 'op': 'eq', 'value': 'full_time'}, True),
            ({'field': 'course_load', 'op': 'ne', 'value': 'part_time'}, True),
            ({'field': 'gpa', 'op': 'gte', 'value': 80}, True),
            ({'field': 'gpa', 'op': 'lt', 'value': 80}, False),
            ({'field': 'sfa', 'op': 'ne', 'value': True}, True),
            ({'field': 'note', 'op': 'is_empty'}, True),
            ({'field': 'gpa', 'op': 'is_set'}, True),
            ({'field': 'course_load', 'op': 'in', 'value': ['full_time', 'part_time']}, True),
        ]
        for condition, expected in cases:
            self.assertIs(conditions.evaluate(condition, ctx), expected, condition)

    def test_combinators(self):
        ctx = {'a': 1, 'b': 2}
        self.assertTrue(conditions.evaluate(
            {'all': [{'field': 'a', 'op': 'eq', 'value': 1},
                     {'field': 'b', 'op': 'eq', 'value': 2}]}, ctx))
        self.assertFalse(conditions.evaluate(
            {'all': [{'field': 'a', 'op': 'eq', 'value': 1},
                     {'field': 'b', 'op': 'eq', 'value': 9}]}, ctx))
        self.assertTrue(conditions.evaluate(
            {'any': [{'field': 'a', 'op': 'eq', 'value': 9},
                     {'field': 'b', 'op': 'eq', 'value': 2}]}, ctx))
        self.assertTrue(conditions.evaluate(
            {'not': {'field': 'a', 'op': 'eq', 'value': 9}}, ctx))

    def test_an_empty_condition_always_holds(self):
        self.assertTrue(conditions.evaluate(None, {}))
        self.assertTrue(conditions.evaluate({}, {}))

    def test_a_missing_answer_fails_to_match_rather_than_erroring(self):
        """A blank answer must not abort pricing the whole application."""
        self.assertFalse(conditions.evaluate({'field': 'absent', 'op': 'gte', 'value': 5}, {}))

    def test_malformed_conditions_are_rejected_when_written(self):
        for bad in [
            {'field': 'x'},                                  # no operator
            {'field': 'x', 'op': 'wat', 'value': 1},          # unknown operator
            {'field': 'x', 'op': 'in', 'value': 'not a list'},
            {'all': []},
        ]:
            with self.assertRaises(conditions.ConditionError, msg=bad):
                conditions.validate(bad)

    def test_referenced_fields_are_discoverable(self):
        condition = {'all': [{'field': 'a', 'op': 'eq', 'value': 1},
                             {'not': {'field': 'b', 'op': 'is_set'}}]}
        self.assertEqual(conditions.referenced_fields(condition), {'a', 'b'})


class EffectRegistryTests(SimpleTestCase):

    def test_every_way_of_producing_money_is_enumerable(self):
        kinds = available_kinds()
        for expected in ('flat_rate', 'rate_per_month', 'capped_tuition',
                         'percentage_relief', 'tiered', 'capped_request'):
            self.assertIn(expected, kinds)

    def test_an_unknown_effect_kind_is_refused(self):
        with self.assertRaises(EffectError):
            validate_effect({'kind': 'transfer_everything'})

    def test_missing_parameters_are_refused(self):
        with self.assertRaises(EffectError):
            validate_effect({'kind': 'flat_rate'})       # no section/key


class BaselineRuleSetTests(TestCase):
    """The seeded rules must produce the amounts the old service produced."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', verbosity=0)

    def setUp(self):
        seed_rates()
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def _price(self, app):
        return price(app, self.rule_set, PolicyBook.for_application(app))

    def test_tuition_capped_living_by_month_and_books(self):
        decision = self._price(make_application())
        amounts = {o.code: o.amount for o in decision.applied}
        self.assertEqual(amounts['psssp_tuition'], Decimal('6000'))
        self.assertEqual(amounts['psssp_living'], Decimal('1800') * 4)
        self.assertEqual(amounts['book_allowance'], Decimal('500'))

    def test_streams_stack_without_funding_the_same_dollar(self):
        app = make_application(answers={'confirmed_tuition': '9000',
                                        'funding_stream': 'dggr'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['psssp_tuition'], Decimal('7000'))
        self.assertEqual(amounts['dggr_tuition_top_up'], Decimal('2000'))
        self.assertEqual(amounts['dggr_living'], Decimal('600') * 4)

    def test_sfa_recipients_receive_nothing_from_cdfn(self):
        decision = self._price(make_application(answers={'receives_sfa': True}))
        self.assertEqual(decision.total, Decimal('0.00'))

    def test_extra_relief_is_inclusive_and_bounded_by_the_bill(self):
        app = make_application(answers={'confirmed_tuition': '20000',
                                        'funding_stream': 'dggr'})
        decision = self._price(app)
        amounts = {o.code: o.amount for o in decision.applied}
        self.assertEqual(amounts['dggr_extra_tuition_relief'], Decimal('10000'))
        tuition = sum(o.amount for o in decision.applied
                      if o.category == Award.Category.TUITION)
        self.assertEqual(tuition, Decimal('20000'))     # exactly the bill, never more

    def test_part_time_selects_a_different_living_rate(self):
        app = make_application(answers={'course_load': 'part_time'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['psssp_living'], Decimal('900') * 4)

    def test_graduation_bursary_follows_the_credential(self):
        app = make_application(type=ApplicationType.GRADUATION_BURSARY,
                               stream=FundingStream.DGGR,
                               answers={'credential': 'bachelors_degree'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['graduation_bursary'], Decimal('4000'))

    def test_scholarship_tiers_pick_the_best_band_reached(self):
        for gpa, expected in (('85', '2000'), ('75', '1000')):
            app = make_application(type=ApplicationType.ACADEMIC_SCHOLARSHIP,
                                   stream=FundingStream.DGGR,
                                   answers={'gpa_achieved': gpa})
            amounts = {o.code: o.amount for o in self._price(app).applied}
            self.assertEqual(amounts['academic_scholarship'], Decimal(expected), gpa)

    def test_no_tier_reached_awards_nothing_rather_than_the_cheapest(self):
        app = make_application(type=ApplicationType.ACADEMIC_SCHOLARSHIP,
                               stream=FundingStream.DGGR,
                               answers={'gpa_achieved': '55'})
        self.assertEqual(self._price(app).total, Decimal('0.00'))

    def test_hardship_is_capped_at_the_policy_maximum(self):
        app = make_application(type=ApplicationType.HARDSHIP_BURSARY,
                               stream=FundingStream.DGGR,
                               answers={'amount_requested': '5000'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['hardship_bursary'], Decimal('3000'))


class DecisionTraceTests(TestCase):
    """The trace is the product: a funding body must explain any award."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', verbosity=0)

    def setUp(self):
        seed_rates()
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def test_every_rule_is_recorded_whether_or_not_it_fired(self):
        decision = price(make_application(), self.rule_set,
                         PolicyBook.for_application(make_application()))
        self.assertEqual(len(decision.outcomes), self.rule_set.rules.count())
        self.assertTrue(any(not o.applied for o in decision.outcomes))

    def test_skipped_rules_say_why(self):
        decision = price(make_application(), self.rule_set,
                         PolicyBook.for_application(make_application()))
        for outcome in decision.outcomes:
            self.assertTrue(outcome.explanation, outcome.code)

    def test_the_trace_names_the_rule_set_version(self):
        app = make_application()
        trace = price(app, self.rule_set, PolicyBook.for_application(app)).as_trace()
        self.assertIn('v1', trace['rule_set'])
        self.assertEqual(len(trace['rules']), self.rule_set.rules.count())

    def test_missing_rates_are_reported_and_the_decision_is_incomplete(self):
        PolicySetting.objects.all().delete()
        app = make_application()
        decision = price(app, self.rule_set, PolicyBook.for_application(app))
        self.assertFalse(decision.is_complete)
        self.assertTrue(decision.missing_rates)

    def test_a_malformed_rule_does_not_stop_the_others(self):
        Rule.objects.create(
            rule_set=self.rule_set, code='broken', description='Malformed',
            category=Award.Category.BURSARY, order=5,
            condition={'field': 'x', 'op': 'nonsense', 'value': 1},
            effect={'kind': 'flat_rate', 'section': 'system_config', 'key': 'book_allowance'},
        )
        app = make_application()
        decision = price(app, self.rule_set, PolicyBook.for_application(app))
        broken = next(o for o in decision.outcomes if o.code == 'broken')
        self.assertFalse(broken.applied)
        self.assertIn('malformed', broken.explanation.lower())
        # The rest still priced normally.
        self.assertGreater(decision.total, Decimal('0'))


class RuleSetVersioningTests(TestCase):
    """A decision must be replayable exactly as it was made."""

    def test_the_set_in_force_on_a_date_is_the_one_that_applied(self):
        old = RuleSet.objects.create(
            name='P', version=1, status=RuleSet.Status.PUBLISHED,
            effective_from=date(2024, 1, 1), effective_to=date(2025, 12, 31),
        )
        new = RuleSet.objects.create(
            name='P', version=2, status=RuleSet.Status.PUBLISHED,
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(RuleSet.in_force_on(date(2024, 6, 1)), old)
        self.assertEqual(RuleSet.in_force_on(date(2026, 6, 1)), new)

    def test_a_superseded_set_still_governs_the_period_it_covered(self):
        """'Superseded' means no longer current, not never applied.

        Excluding superseded sets made every application submitted before the
        latest policy change unpriceable, which defeats the point of versioning.
        """
        old = RuleSet.objects.create(
            name='P', version=1, status=RuleSet.Status.SUPERSEDED,
            effective_from=date(2020, 1, 1), effective_to=date(2026, 1, 1),
        )
        RuleSet.objects.create(
            name='P', version=2, status=RuleSet.Status.PUBLISHED,
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(RuleSet.in_force_on(date(2024, 6, 1)), old)

    def test_draft_rule_sets_never_price_anything(self):
        RuleSet.objects.create(
            name='P', version=1, status=RuleSet.Status.DRAFT,
            effective_from=date(2020, 1, 1),
        )
        self.assertIsNone(RuleSet.in_force_on(date(2026, 6, 1)))

    def test_publishing_closes_the_previous_version(self):
        call_command('seed_rules', '--publish', verbosity=0)
        call_command('seed_rules', '--publish', verbosity=0)
        published = RuleSet.objects.filter(status=RuleSet.Status.PUBLISHED)
        self.assertEqual(published.count(), 1)
        self.assertEqual(published.get().version, 2)
        superseded = RuleSet.objects.get(version=1)
        self.assertEqual(superseded.status, RuleSet.Status.SUPERSEDED)
        self.assertIsNotNone(superseded.effective_to)


class EveryAwardingTypeHasRulesTests(TestCase):
    """No application type may be silently unpriceable."""

    NO_AWARD = {'enrollment_verification', 'appeal'}

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', verbosity=0)

    def test_every_type_that_pays_has_at_least_one_rule(self):
        rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)
        covered = set()
        for rule in rule_set.rules.all():
            covered |= set(rule.applies_to_types or ApplicationType.values)

        for value in ApplicationType.values:
            if value in self.NO_AWARD:
                continue
            self.assertIn(value, covered, f'{value} can never be awarded anything')

    def test_types_that_pay_nothing_have_no_rules(self):
        """An appeal asks for reconsideration; it does not disburse."""
        rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)
        for rule in rule_set.rules.all():
            for value in rule.applies_to_types:
                self.assertNotIn(value, self.NO_AWARD, rule.code)

    def test_every_rule_declares_a_valid_effect(self):
        rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)
        for rule in rule_set.rules.all():
            validate_effect(rule.effect)          # raises if malformed

    def test_every_rule_declares_a_valid_condition(self):
        rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)
        for rule in rule_set.rules.all():
            conditions.validate(rule.condition)   # raises if malformed


class RequestCappedAwardTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', verbosity=0)

    def setUp(self):
        seed_rates()
        for section, key, value in [
            ('travel', 'max_graduation', '1200'),
            ('practicum', 'max_allowance', '2500'),
            ('emergency_relief', 'max_per_student', '1500'),
        ]:
            PolicySetting.objects.update_or_create(
                section=section, key=key,
                defaults=dict(label=key, value=Decimal(value), unit='$'),
            )
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def _price(self, app):
        return price(app, self.rule_set, PolicyBook.for_application(app))

    def test_travel_cap_varies_with_the_purpose_of_travel(self):
        app = make_application(
            type=ApplicationType.TRAVEL, stream=FundingStream.DGGR,
            answers={'amount_requested': '2000', 'travel_purpose': 'graduation'},
        )
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['travel_assistance'], Decimal('1200'))

    def test_a_claim_below_the_cap_is_paid_in_full(self):
        app = make_application(
            type=ApplicationType.TRAVEL, stream=FundingStream.DGGR,
            answers={'amount_requested': '400', 'travel_purpose': 'graduation'},
        )
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['travel_assistance'], Decimal('400'))

    def test_practicum_and_emergency_relief_are_capped(self):
        for app_type, code, requested, expected in (
            (ApplicationType.PRACTICUM, 'practicum_allowance', '9000', '2500'),
            (ApplicationType.EMERGENCY_RELIEF, 'emergency_relief', '9000', '1500'),
        ):
            app = make_application(type=app_type, stream=FundingStream.DGGR,
                                   answers={'amount_requested': requested})
            amounts = {o.code: o.amount for o in self._price(app).applied}
            self.assertEqual(amounts[code], Decimal(expected), app_type)

    def test_an_appeal_is_awarded_nothing(self):
        app = make_application(type=ApplicationType.APPEAL, stream=FundingStream.DGGR,
                               answers={'appeal_reason': 'Circumstances changed'})
        self.assertEqual(self._price(app).total, Decimal('0.00'))
