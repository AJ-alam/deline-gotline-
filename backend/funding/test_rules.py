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
from funding.management.commands import seed_demo, seed_rules
from funding.rules.engine import price
from funding.schemas import get_schema
from funding.services import policy_admin
from funding.services.policy import PolicyBook

User = get_user_model()
_counter = itertools.count(1)

# The rates the office publishes, not a second copy of them. This file used to
# carry its own list, so the two drifted: the tests went on asserting a $7,000
# PSSSP cap and an $80 achievement threshold long after neither was what a
# database would be seeded with, and every pricing assertion here was really an
# assertion about a table nothing else read.
#
# `rate_of` is how a test names an expected amount, so an expectation is always
# quoted against the figure actually in force.
RATES = [(section, key, value) for section, key, value, _label in seed_demo.RATES]

_BY_KEY = {(section, key): Decimal(value) for section, key, value in RATES}


def rate_of(section: str, key: str) -> Decimal:
    """The seeded value of one rate. Fails loudly if it is not seeded at all."""
    try:
        return _BY_KEY[(section, key)]
    except KeyError:
        raise AssertionError(f'no rate {section}:{key} is seeded')


def seed_rates():
    for section, key, value in RATES:
        PolicySetting.objects.update_or_create(
            section=section, key=key,
            defaults=dict(label=key, value=Decimal(value), unit=policy_admin.unit_for(key)),
        )


def make_application(**kwargs):
    student = User.objects.create_user(
        email=f'r{next(_counter)}@test.com', password='pw123456',
        first_name='Test', last_name='Student', role='student',is_deline_beneficiary=True, is_indian_act_registered=True)
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

    def test_tuition_capped_and_living_paid_by_the_month(self):
        """The default application: a $6,000 bill against the PSSSP cap.

        There is no book allowance line to assert any more. The policy funds
        mandatory books and supplies out of the same per-semester tuition cap as
        the tuition itself, so a flat amount on top would be paying an award the
        policy does not describe.
        """
        decision = self._price(make_application())
        amounts = {o.code: o.amount for o in decision.applied}

        cap = rate_of('psssp_tuition', 'max_per_semester')
        self.assertEqual(amounts['psssp_tuition'], min(Decimal('6000'), cap))
        self.assertEqual(amounts['psssp_living'],
                         rate_of('psssp_living', 'fulltime_no_dependents') * 4)
        self.assertNotIn('book_allowance', amounts)

    def test_a_capped_tuition_award_says_what_is_actually_left_owing(self):
        """The sentence a decision is justified by, and an appeal argues against.

        It used to report the amount *awarded* as the amount outstanding: a bill
        over the cap told the director that the whole cap remained unfunded,
        when only the overspill did. Nothing failed — the money was right and
        only the explanation lied, which is why no test caught it.
        """
        cap = rate_of('psssp_tuition', 'max_per_semester')
        app = make_application(answers={'confirmed_tuition': str(cap + Decimal('431.55'))})
        outcome = next(o for o in self._price(app).applied if o.code == 'psssp_tuition')

        self.assertEqual(outcome.amount, cap)
        self.assertIn('431.55', outcome.explanation)
        self.assertNotIn(f'${cap} of the bill left unfunded', outcome.explanation)

    def test_a_fully_funded_bill_reports_nothing_left_owing(self):
        cap = rate_of('psssp_tuition', 'max_per_semester')
        app = make_application(answers={'confirmed_tuition': str(cap)})
        outcome = next(o for o in self._price(app).applied if o.code == 'psssp_tuition')
        self.assertEqual(outcome.amount, cap)
        self.assertIn('$0.00 of the bill left unfunded', outcome.explanation)

    def test_streams_stack_without_funding_the_same_dollar(self):
        """A bill bigger than any one stream's cap is split between them.

        Expectations are computed from the rates rather than written out, so
        this asserts the *allocation* — PSSSP first, DGGR topping up what it
        left, and never twice on the same dollar — rather than restating three
        figures that change whenever the office moves a rate.
        """
        psssp_cap = rate_of('psssp_tuition', 'max_per_semester')
        dggr_cap = rate_of('dggr_tuition', 'fulltime_per_semester')
        bill = psssp_cap + dggr_cap + Decimal('2500')

        app = make_application(answers={'confirmed_tuition': str(bill),
                                        'funding_stream': 'dggr'})
        amounts = {o.code: o.amount for o in self._price(app).applied}

        self.assertEqual(amounts['psssp_tuition'], psssp_cap)
        self.assertEqual(amounts['dggr_tuition_top_up'], dggr_cap)
        self.assertEqual(amounts['dggr_living'],
                         rate_of('dggr_living', 'fulltime_no_dependents') * 4)

        tuition_paid = sum(
            amount for code, amount in amounts.items()
            if code in ('psssp_tuition', 'dggr_tuition_top_up',
                        'dggr_extra_tuition_relief')
        )
        self.assertLessEqual(tuition_paid, bill)

    def test_sfa_recipients_receive_nothing_from_cdfn(self):
        """C-DFN is PSSSP and UCEPP. DGGR is not C-DFN.

        This asserted a total of zero, which was true only because the
        application carried a single stream: the applicant is a beneficiary, so
        the DGGR rules were written for them and were skipped anyway. The
        office's rule is the one the sign-up screening states — SFA blocks the
        federal programmes and does not touch the bursary — so what must be zero
        is the C-DFN money, not the award.
        """
        decision = self._price(make_application(answers={'receives_sfa': True}))
        applied = {o.code: o.amount for o in decision.applied}

        self.assertEqual(
            [code for code in applied if code.startswith(('psssp', 'ucepp'))], [],
            'somebody on SFA was funded from a federal programme')
        self.assertGreater(decision.total, Decimal('0.00'),
                           'a beneficiary on SFA still qualifies for DGGR')

    def test_a_beneficiary_is_funded_from_every_stream_they_qualify_for(self):
        """PSSSP pays the tuition and the living allowance; DGGR tops up.

        Both rule sets are written for a student who is registered under the
        Indian Act *and* an enrolled beneficiary — but the gate compared each
        rule against `application.stream`, one value, so whichever stream the
        column held was the only one that could pay. The other pot was closed to
        somebody the office had already decided qualified for it.
        """
        decision = self._price(make_application(answers={'confirmed_tuition': '9000'}))
        applied = {o.code: o.amount for o in decision.applied}

        self.assertIn('psssp_tuition', applied)
        self.assertTrue([code for code in applied if code.startswith('dggr')],
                        f'nothing from DGGR: {sorted(applied)}')

    def test_somebody_who_qualifies_for_one_stream_is_paid_from_one(self):
        """The counterpart. Widening the gate must not hand a person money from
        a pot they do not qualify for."""
        application = make_application()
        application.student.is_deline_beneficiary = False
        application.student.save(update_fields=['is_deline_beneficiary'])

        applied = {o.code for o in self._price(application).applied}

        self.assertIn('psssp_tuition', applied)
        self.assertEqual([code for code in applied if code.startswith('dggr')], [])

    def test_extra_relief_is_inclusive_and_bounded_by_the_bill(self):
        """A bill far above every cap. The relief is what the percentage and the
        cap allow, less the top-up already paid, and never more than is owed."""
        percent = rate_of('dggr_extra_tuition', 'max_percent_covered')
        relief_cap = rate_of('dggr_extra_tuition', 'max_per_semester')
        top_up = rate_of('dggr_tuition', 'fulltime_per_semester')
        bill = Decimal('20000')

        app = make_application(answers={'confirmed_tuition': str(bill),
                                        'funding_stream': 'dggr'})
        decision = self._price(app)
        amounts = {o.code: o.amount for o in decision.applied}

        inclusive = min(bill * percent / Decimal(100), relief_cap)
        self.assertEqual(amounts['dggr_extra_tuition_relief'], inclusive - top_up)

        tuition = sum(o.amount for o in decision.applied
                      if o.category == Award.Category.TUITION)
        self.assertLessEqual(tuition, bill)     # never more than the bill
        self.assertEqual(
            tuition,
            rate_of('psssp_tuition', 'max_per_semester') + inclusive)

    def test_part_time_selects_a_different_living_rate(self):
        app = make_application(answers={'course_load': 'part_time'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['psssp_living'],
                         rate_of('psssp_living', 'parttime_no_dependents') * 4)
        # And it is genuinely a different rate, not the same one relabelled.
        self.assertNotEqual(rate_of('psssp_living', 'parttime_no_dependents'),
                            rate_of('psssp_living', 'fulltime_no_dependents'))

    def test_graduation_bursary_follows_the_credential(self):
        for credential in ('bachelors_degree', 'red_seal', 'md_dds'):
            with self.subTest(credential=credential):
                app = make_application(type=ApplicationType.GRADUATION_BURSARY,
                                       stream=FundingStream.DGGR,
                                       answers={'credential': credential})
                amounts = {o.code: o.amount for o in self._price(app).applied}
                self.assertEqual(amounts['graduation_bursary'],
                                 rate_of('graduation_bursary', credential))

    def test_scholarship_tiers_pick_the_best_band_reached(self):
        high = rate_of('academic_scholarship', 'high_threshold_percent')
        mid = rate_of('academic_scholarship', 'mid_threshold_percent')
        bands = (
            (high + 5, rate_of('academic_scholarship', 'high_achievement_award')),
            (mid + 5, rate_of('academic_scholarship', 'mid_achievement_award')),
        )
        for gpa, expected in bands:
            app = make_application(type=ApplicationType.ACADEMIC_SCHOLARSHIP,
                                   stream=FundingStream.DGGR,
                                   answers={'gpa_achieved': str(gpa)})
            amounts = {o.code: o.amount for o in self._price(app).applied}
            self.assertEqual(amounts['academic_scholarship'], expected, gpa)

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
        self.assertEqual(amounts['hardship_bursary'],
                         rate_of('hardship_bursary', 'max_per_student'))


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
            effect={'kind': 'flat_rate', 'section': 'practicum', 'key': 'allowance'},
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
        # `seed_rates` is the office's whole list now, so the three that used to
        # be added by hand here — with figures of their own, which is how the
        # travel cap came to be tested against $1,200 while the policy says
        # $2,000 — come from the same place as everything else.
        seed_rates()
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def _price(self, app):
        return price(app, self.rule_set, PolicyBook.for_application(app))

    def test_travel_cap_varies_with_the_purpose_of_travel(self):
        for purpose in get_schema('travel').field('travel_purpose').choice_values:
            with self.subTest(purpose=purpose):
                cap = rate_of('travel', f'max_{purpose}_no_dependents')
                app = make_application(
                    type=ApplicationType.TRAVEL, stream=FundingStream.DGGR,
                    answers={'amount_requested': str(cap + Decimal('1000')),
                             'travel_purpose': purpose},
                )
                amounts = {o.code: o.amount for o in self._price(app).applied}
                self.assertEqual(amounts['travel_assistance'], cap)

    def test_travel_cap_is_higher_for_a_student_with_dependants(self):
        """§7(C): $2,000 a trip without dependants, $3,500 with them.

        Keyed on the purpose alone, both students were capped identically and
        the policy's own distinction had nowhere to live. Asserted as an
        inequality against the rates rather than against two figures, so it
        still means something after the office moves either one.
        """
        alone = rate_of('travel', 'max_start_of_study_no_dependents')
        supporting = rate_of('travel', 'max_start_of_study_with_dependents')
        self.assertGreater(supporting, alone)

        asked = str(supporting + Decimal('1000'))
        for has_dependents, expected in ((False, alone), (True, supporting)):
            with self.subTest(has_dependents=has_dependents):
                app = make_application(
                    type=ApplicationType.TRAVEL, stream=FundingStream.DGGR,
                    answers={'amount_requested': asked,
                             'travel_purpose': 'start_of_study',
                             'has_dependents': has_dependents},
                )
                amounts = {o.code: o.amount for o in self._price(app).applied}
                self.assertEqual(amounts['travel_assistance'], expected)

    def test_a_claim_below_the_cap_is_paid_in_full(self):
        app = make_application(
            type=ApplicationType.TRAVEL, stream=FundingStream.DGGR,
            answers={'amount_requested': '400', 'travel_purpose': 'graduation'},
        )
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['travel_assistance'], Decimal('400'))

    def test_emergency_relief_is_capped(self):
        app = make_application(type=ApplicationType.EMERGENCY_RELIEF,
                               stream=FundingStream.DGGR,
                               answers={'amount_requested': '9000'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['emergency_relief'],
                         rate_of('emergency_relief', 'max_per_student'))

    def test_the_practicum_award_is_the_published_rate_and_asks_for_nothing(self):
        """The form collects the employer's report, never a figure.

        Priced as a flat rate for that reason. While it was a `capped_request`
        against an `amount_requested` the form had stopped collecting, it paid
        zero on every claim and explained itself as 'No amount requested'.
        """
        app = make_application(
            type=ApplicationType.PRACTICUM, stream=FundingStream.DGGR,
            answers={'employer_name': 'Deline Health Centre',
                     'performance_summary': 'No absences.'},
        )
        outcomes = {o.code: o for o in self._price(app).applied}
        self.assertEqual(outcomes['practicum_allowance'].amount,
                         rate_of('practicum', 'allowance'))

    def test_an_inflated_request_cannot_raise_the_practicum_award(self):
        """Nothing on the form asks for one, so a posted figure buys nothing."""
        app = make_application(type=ApplicationType.PRACTICUM,
                               stream=FundingStream.DGGR,
                               answers={'amount_requested': '9000'})
        amounts = {o.code: o.amount for o in self._price(app).applied}
        self.assertEqual(amounts['practicum_allowance'],
                         rate_of('practicum', 'allowance'))

    def test_an_appeal_is_awarded_nothing(self):
        app = make_application(type=ApplicationType.APPEAL, stream=FundingStream.DGGR,
                               answers={'appeal_reason': 'Circumstances changed'})
        self.assertEqual(self._price(app).total, Decimal('0.00'))


class RateReferenceTests(SimpleTestCase):
    """Every rate a rule reads must be a rate the office actually has.

    A rule naming a rate nobody seeded prices at zero and reports the gap — the
    engine is careful about it — but the gap is only ever discovered by pricing
    a real application. `academic_scholarship` published two threshold rates
    that no rule read, which is the same failure from the other end: policy and
    rules agreeing only by habit.

    So both directions are checked against `seed_demo`, which is what a fresh
    database is filled from.
    """

    def rate_keys_used(self):
        """Every (section, key) the baseline rules resolve, templates aside."""
        used = set()
        for spec in seed_rules.RULES:
            effect = spec['effect']
            for section, key in self._pairs(effect):
                used.add((section, key))
        return used

    @staticmethod
    def _pairs(effect):
        section = effect.get('section')
        for name in ('key', 'at_least_key', 'percent_key', 'threshold_key'):
            value = effect.get(name)
            if section and value:
                yield section, value
        for tier in effect.get('tiers', ()):
            for name in ('key', 'at_least_key'):
                if tier.get('section') and tier.get(name):
                    yield tier['section'], tier[name]

    def test_every_rate_a_rule_reads_is_seeded(self):
        seeded = {(section, key) for section, key, _value, _label in seed_demo.RATES}
        missing = {
            (section, key) for section, key in self.rate_keys_used()
            # A templated key is resolved from an answer at pricing time — see
            # `max_{travel_purpose}` — so it is checked by its expansions below.
            if '{' not in key and (section, key) not in seeded
        }
        self.assertEqual(missing, set(),
                         f'rules read rates nothing seeds: {sorted(missing)}')

    def test_every_templated_rate_key_has_a_rate_for_each_answer(self):
        """`max_{travel_purpose}_{dependants}` is one key in the rule and six
        rates in the office's list. A combination with no matching rate prices
        at nothing — which reads as an unconfigured rate rather than as a claim
        the policy does not fund."""
        seeded = {(section, key) for section, key, _value, _label in seed_demo.RATES}
        purposes = get_schema('travel').field('travel_purpose').choice_values
        for purpose in purposes:
            for dependants in ('no_dependents', 'with_dependents'):
                with self.subTest(purpose=purpose, dependants=dependants):
                    self.assertIn(('travel', f'max_{purpose}_{dependants}'), seeded)

    def test_every_graduation_credential_has_a_rate(self):
        """The credential *is* the amount: a value with no rate pays nothing."""
        seeded = {(section, key) for section, key, _value, _label in seed_demo.RATES}
        for credential in get_schema('graduation_bursary').field('credential').choice_values:
            with self.subTest(credential=credential):
                self.assertIn(('graduation_bursary', credential), seeded)

    def test_the_templates_expand_to_rates_that_exist(self):
        """The keys a rule builds at pricing time rather than naming outright.

        `{load}_{dependants}` is one key in the rule and four rates in the
        office's list; `{load}_per_semester` is two. An expansion with no rate
        behind it prices at nothing.
        """
        seeded = {(section, key) for section, key, _value, _label in seed_demo.RATES}
        loads = ('fulltime', 'parttime')
        dependants = ('no_dependents', 'with_dependents')
        for section in ('psssp_living', 'ucepp_living', 'dggr_living'):
            for load in loads:
                for who in dependants:
                    with self.subTest(section=section, key=f'{load}_{who}'):
                        self.assertIn((section, f'{load}_{who}'), seeded)
        for load in loads:
            with self.subTest(section='dggr_tuition', key=f'{load}_per_semester'):
                self.assertIn(('dggr_tuition', f'{load}_per_semester'), seeded)


class NoUnreadRateTests(TestCase):
    """No rate is published to the office that nothing ever reads.

    A rate on the policy screen that no rule consults is a control an
    administrator can move to no effect — `residency_flag` with a currency
    symbol in front of it. `academic_scholarship` shipped two of them.

    Worked out by watching, not by parsing: every rate key `PolicyBook` resolves
    while pricing a representative application of each type, across both course
    loads, both dependant states and all three streams, is recorded. Reading the
    rule definitions instead means re-implementing the template expansion, and a
    second implementation of that is the thing being guarded against.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        seed_rates()
        for section, key, value in (
            ('academic_scholarship', 'high_threshold_percent', '80'),
            ('academic_scholarship', 'mid_threshold_percent', '70'),
        ):
            PolicySetting.objects.update_or_create(
                section=section, key=key,
                defaults=dict(label=key, value=Decimal(value), unit=policy_admin.unit_for(key)))
        self.rule_set = RuleSet.objects.get(status=RuleSet.Status.PUBLISHED)

    def consulted(self) -> set:
        """Every (section, key) pricing looks up across the whole matrix."""
        seen = set()
        original = PolicyBook.rate

        def watched(book, section, key):
            seen.add((section, key))
            return original(book, section, key)

        credentials = get_schema('graduation_bursary').field('credential').choice_values
        purposes = get_schema('travel').field('travel_purpose').choice_values

        cases = [
            (ApplicationType.ADMISSION, {}),
            (ApplicationType.CONTINUING_FUNDING, {}),
            (ApplicationType.ACADEMIC_SCHOLARSHIP, {'gpa_achieved': '85'}),
            (ApplicationType.ACADEMIC_SCHOLARSHIP, {'gpa_achieved': '75'}),
            (ApplicationType.PRACTICUM, {}),
            (ApplicationType.EMERGENCY_RELIEF, {'amount_requested': '9000'}),
            (ApplicationType.HARDSHIP_BURSARY, {'amount_requested': '9000'}),
            (ApplicationType.APPEAL, {}),
        ]
        cases += [(ApplicationType.GRADUATION_BURSARY, {'credential': credential})
                  for credential in credentials]
        cases += [(ApplicationType.TRAVEL,
                   {'amount_requested': '5000', 'travel_purpose': purpose})
                  for purpose in purposes]

        PolicyBook.rate = watched
        try:
            for app_type, answers in cases:
                for stream in FundingStream.values:
                    for load in ('full_time', 'part_time'):
                        for dependants in ('0', '2'):
                            application = make_application(
                                type=app_type, stream=stream,
                                answers={'course_load': load,
                                         'dependent_count': dependants,
                                         'confirmed_tuition': '20000',
                                         **answers})
                            price(application, self.rule_set,
                                  PolicyBook.for_application(application))
        finally:
            PolicyBook.rate = original
        return seen

    def test_every_seeded_rate_is_read_by_something(self):
        seeded = {(section, key) for section, key, _value in RATES}
        unread = seeded - self.consulted()
        self.assertEqual(
            unread, set(),
            'these rates are offered to the office and nothing reads them, so '
            f'changing them does nothing: {sorted(unread)}')
