"""Awards as immutable decision records."""

import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from funding.models import (
    Application, ApplicationType, Award, AwardDecision, FundingStream,
    PolicySetting, RuleSet,
)
from funding.services.workflow import NEEDS_ENROLMENT_CONFIRMATION
from funding.services.decisions import (
    IncompletePolicyError, NoRuleSetInForce, current_decision, decision_history,
    preview, record_decision,
)
from funding.test_rules import RATES, seed_rates
from funding.test_fixtures import confirm_enrolment

User = get_user_model()
_counter = itertools.count(1)


def make_application(**kwargs):
    student = User.objects.create_user(
        email=f'd{next(_counter)}@test.com', password='pw123456',
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
    application = Application.objects.create(student=student, **defaults)
    # An admission application carrying a confirmed tuition is one the registrar
    # has already answered — that key is only ever written by the verification.
    # Built without one it was an application that could not exist, and pricing
    # it exercised a path the office cannot reach.
    if application.type in NEEDS_ENROLMENT_CONFIRMATION:
        confirm_enrolment(application)
    return application


class RecordingTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def test_pricing_records_a_decision_with_lines(self):
        app = make_application()
        decision = record_decision(app)

        self.assertTrue(decision.is_current)
        self.assertGreater(decision.total, Decimal('0'))
        self.assertTrue(decision.lines.exists())
        app.refresh_from_db()
        self.assertEqual(app.awarded_total, decision.total)

    def test_the_decision_records_which_rule_set_priced_it(self):
        app = make_application()
        decision = record_decision(app)
        self.assertEqual(decision.rule_set_version, 1)
        self.assertIn('v1', decision.trace['rule_set'])

    def test_each_line_names_the_rule_that_produced_it(self):
        app = make_application()
        decision = record_decision(app)
        for line in decision.lines.all():
            self.assertTrue(line.rule_code, 'a line with no rule cannot be explained')

    def test_inputs_are_snapshotted_so_later_edits_do_not_rewrite_history(self):
        app = make_application()
        # What the registrar actually confirmed, read off the application
        # rather than written out here: the figure is cleaned as money on its
        # way in, so it is '6000.00' and not the '6000' a fixture types.
        confirmed = app.answers['confirmed_tuition']
        decision = record_decision(app)

        app.answers['confirmed_tuition'] = '99999'
        app.save(update_fields=['answers'])

        decision.refresh_from_db()
        self.assertEqual(decision.inputs['confirmed_tuition'], confirmed)
        self.assertNotEqual(decision.inputs['confirmed_tuition'], '99999')

    def test_the_trace_is_stored_with_the_decision(self):
        app = make_application()
        decision = record_decision(app)
        self.assertTrue(decision.trace['rules'])
        self.assertTrue(all('reason' in r for r in decision.trace['rules']))


class SupersedingTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def test_repricing_supersedes_rather_than_overwrites(self):
        app = make_application()
        first = record_decision(app)
        second = record_decision(app)

        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(first.superseded_by, second)
        self.assertEqual(AwardDecision.objects.filter(application=app).count(), 2)

    def test_the_earlier_decision_keeps_its_own_numbers(self):
        app = make_application()
        first = record_decision(app)
        original_total = first.total

        app.answers['confirmed_tuition'] = '2000'
        app.save(update_fields=['answers'])
        second = record_decision(app)

        first.refresh_from_db()
        self.assertEqual(first.total, original_total)
        self.assertNotEqual(second.total, original_total)

    def test_only_one_decision_is_ever_current(self):
        app = make_application()
        for _ in range(3):
            record_decision(app)
        self.assertEqual(
            AwardDecision.objects.filter(application=app, is_current=True).count(), 1,
        )

    def test_the_database_refuses_a_second_current_decision(self):
        app = make_application()
        record_decision(app)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AwardDecision.objects.create(
                    application=app,
                    rule_set=RuleSet.objects.get(status=RuleSet.Status.PUBLISHED),
                    rule_set_version=1, total=Decimal('1'), is_current=True,
                )

    def test_history_is_ordered_newest_first(self):
        app = make_application()
        record_decision(app)
        record_decision(app)
        history = list(decision_history(app))
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0].created_at >= history[1].created_at)

    def test_current_decision_returns_the_live_one(self):
        app = make_application()
        record_decision(app)
        latest = record_decision(app)
        self.assertEqual(current_decision(app), latest)


class IncompletePolicyTests(TestCase):

    def setUp(self):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def test_recording_refuses_when_a_rate_is_missing(self):
        app = make_application()
        with self.assertRaises(IncompletePolicyError) as ctx:
            record_decision(app)
        self.assertTrue(ctx.exception.missing)

    def test_nothing_is_written_when_policy_is_incomplete(self):
        app = make_application()
        with self.assertRaises(IncompletePolicyError):
            record_decision(app)
        self.assertFalse(AwardDecision.objects.filter(application=app).exists())
        self.assertFalse(Award.objects.filter(application=app).exists())
        app.refresh_from_db()
        self.assertEqual(app.awarded_total, Decimal('0.00'))

    def test_preview_still_renders_and_reports_what_is_missing(self):
        app = make_application()
        result = preview(app)
        self.assertFalse(result.is_complete)
        self.assertTrue(result.missing_rates)

    def test_incomplete_can_be_recorded_deliberately(self):
        app = make_application()
        decision = record_decision(app, allow_incomplete=True)
        self.assertFalse(decision.is_complete)


class RuleSetSelectionTests(TestCase):

    def setUp(self):
        seed_rates()

    def test_an_application_is_priced_by_the_set_in_force_when_submitted(self):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        old_set = RuleSet.objects.get(version=1)

        # A newer policy is published today.
        call_command('seed_rules', '--publish', verbosity=0)

        old_application = make_application(
            submitted_at=timezone.now() - timedelta(days=400),
        )
        decision = record_decision(old_application)
        self.assertEqual(decision.rule_set, old_set)
        self.assertEqual(decision.rule_set_version, 1)

    def test_pricing_fails_loudly_when_no_rule_set_covers_the_date(self):
        call_command('seed_rules', '--publish', verbosity=0)
        ancient = make_application(
            submitted_at=timezone.now() - timedelta(days=5000),
        )
        with self.assertRaises(NoRuleSetInForce):
            record_decision(ancient)

    def test_a_rule_set_that_priced_something_cannot_be_deleted(self):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        app = make_application()
        decision = record_decision(app)
        with self.assertRaises(Exception):
            decision.rule_set.delete()
