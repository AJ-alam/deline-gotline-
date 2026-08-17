"""Changing funding rates.

The rule that matters most: a rate change must never alter a decision already
made. Everything else here is bookkeeping around that.
"""

import itertools
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, AuditEntry, FundingStream,
    PolicyChange, PolicySetting, RuleSet,
)
from funding.services import policy_admin
from funding.services.decisions import record_decision
from funding.test_rules import rate_of, seed_rates

_counter = itertools.count(1)


def make_admin(role=Role.ADMIN):
    return User.objects.create_user(
        f'p{next(_counter)}@test.com', 'pw12345678',
        first_name='A', last_name='Dmin', role=role,is_deline_beneficiary=True, is_indian_act_registered=True)


def make_application(**kwargs):
    student = User.objects.create_user(
        f'ps{next(_counter)}@test.com', 'pw12345678', first_name='S', last_name='T',is_deline_beneficiary=True, is_indian_act_registered=True)
    defaults = dict(
        student=student, type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
        schema_slug='admission', status=ApplicationStatus.SUBMITTED,
        answers={
            'course_load': 'full_time', 'confirmed_tuition': '6000',
            'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
        },
    )
    defaults.update(kwargs)
    return Application.objects.create(**defaults)


class RateChangeTests(TestCase):

    def setUp(self):
        seed_rates()
        self.actor = make_admin()
        self.setting = PolicySetting.objects.get(
            section='psssp_living', key='fulltime_no_dependents')
        # What the office publishes today, not a figure written in here. This
        # file used to assert against $1,800, which had been the seeded rate
        # once and was still being asserted long after it was not.
        self.was = rate_of('psssp_living', 'fulltime_no_dependents')

    def test_a_change_records_what_the_value_was(self):
        change = policy_admin.change_rate(self.setting, '2000', actor=self.actor)

        self.assertEqual(change.previous_value, self.was)
        self.assertEqual(change.new_value, Decimal('2000.00'))
        self.assertEqual(change.changed_by, self.actor)
        self.setting.refresh_from_db()
        self.assertEqual(self.setting.value, Decimal('2000.00'))

    def test_a_change_is_written_to_the_audit_trail(self):
        policy_admin.change_rate(self.setting, '2000', actor=self.actor)
        entry = AuditEntry.objects.get(action='policy.rate_changed')
        self.assertEqual(entry.actor, self.actor)
        self.assertIn('psssp_living', entry.detail)
        self.assertIn(str(self.was), entry.detail)
        self.assertIn('2000', entry.detail)

    def test_amounts_are_accepted_the_way_people_type_them(self):
        change = policy_admin.change_rate(self.setting, '$2,000.50', actor=self.actor)
        self.assertEqual(change.new_value, Decimal('2000.50'))

    def test_nonsense_and_negatives_are_refused(self):
        for bad in ('not a number', '-50'):
            with self.assertRaises(policy_admin.PolicyEditError, msg=bad):
                policy_admin.change_rate(self.setting, bad, actor=self.actor)

    def test_setting_the_same_value_is_refused_rather_than_logged_as_a_change(self):
        with self.assertRaises(policy_admin.PolicyEditError):
            policy_admin.change_rate(self.setting, str(self.was), actor=self.actor)
        self.assertFalse(PolicyChange.objects.exists())

    def test_a_suspended_rate_is_recorded_as_a_deliberate_act(self):
        policy_admin.set_active(self.setting, False, actor=self.actor)
        self.setting.refresh_from_db()
        self.assertFalse(self.setting.is_active)
        self.assertTrue(AuditEntry.objects.filter(action='policy.rate_suspended').exists())

    def test_history_reads_newest_first(self):
        policy_admin.change_rate(self.setting, '1900', actor=self.actor)
        policy_admin.change_rate(self.setting, '2000', actor=self.actor,
                                 effective_from=timezone.now().date() + timedelta(days=10))
        history = list(policy_admin.history_for(self.setting))
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].new_value, Decimal('2000.00'))


class DecisionsAreNotRewrittenTests(TestCase):
    """The invariant the whole design exists to provide."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.actor = make_admin()
        self.setting = PolicySetting.objects.get(
            section='psssp_living', key='fulltime_no_dependents')

    def test_a_recorded_decision_keeps_its_amount_after_a_rate_rises(self):
        application = make_application()
        decision = record_decision(application)
        original = decision.total

        policy_admin.change_rate(self.setting, '5000', actor=self.actor)

        decision.refresh_from_db()
        self.assertEqual(decision.total, original)
        self.assertEqual(decision.trace['total'], str(original))

    def test_an_application_submitted_before_the_change_still_prices_at_the_old_rate(self):
        """A change dated in the future must not reach backwards."""
        application = make_application(
            submitted_at=timezone.now() - timedelta(days=30))
        policy_admin.change_rate(
            self.setting, '5000', actor=self.actor,
            effective_from=timezone.now().date() + timedelta(days=1),
        )

        decision = record_decision(application)
        living = [
            line for line in decision.trace['rules']
            if line['code'] == 'psssp_living' and line['applied']
        ]
        # The rate in force at submission, for four months — not the new 5000.
        was = rate_of('psssp_living', 'fulltime_no_dependents')
        self.assertEqual(living[0]['amount'], str(was * 4))

    def test_an_application_submitted_after_the_change_prices_at_the_new_rate(self):
        policy_admin.change_rate(
            self.setting, '2500', actor=self.actor,
            effective_from=timezone.now().date() - timedelta(days=1),
        )
        application = make_application()

        decision = record_decision(application)
        living = [
            line for line in decision.trace['rules']
            if line['code'] == 'psssp_living' and line['applied']
        ]
        self.assertEqual(living[0]['amount'], '10000.00')

    def test_repricing_after_a_change_supersedes_rather_than_edits(self):
        application = make_application()
        first = record_decision(application)
        original = first.total

        policy_admin.change_rate(
            self.setting, '2500', actor=self.actor,
            effective_from=timezone.now().date() - timedelta(days=1),
        )
        second = record_decision(application)

        first.refresh_from_db()
        self.assertEqual(first.total, original)     # the earlier decision stands
        self.assertNotEqual(second.total, original)
        self.assertFalse(first.is_current)


class RuleSetPublishingTests(TestCase):

    def setUp(self):
        self.actor = make_admin()

    def _draft(self, version=1, **kwargs):
        defaults = dict(
            name='P', version=version, status=RuleSet.Status.DRAFT,
            effective_from=timezone.now().date(),
        )
        defaults.update(kwargs)
        return RuleSet.objects.create(**defaults)

    def test_publishing_closes_the_previous_version(self):
        first = self._draft(1)
        policy_admin.publish_rule_set(first, actor=self.actor)
        second = self._draft(2)
        policy_admin.publish_rule_set(second, actor=self.actor)

        first.refresh_from_db()
        self.assertEqual(first.status, RuleSet.Status.SUPERSEDED)
        self.assertIsNotNone(first.effective_to)
        self.assertEqual(
            RuleSet.objects.filter(status=RuleSet.Status.PUBLISHED).count(), 1)

    def test_a_superseded_set_still_governs_the_period_it_covered(self):
        first = self._draft(1, effective_from=timezone.now().date() - timedelta(days=100))
        policy_admin.publish_rule_set(
            first, actor=self.actor,
            effective_from=timezone.now().date() - timedelta(days=100))
        policy_admin.publish_rule_set(self._draft(2), actor=self.actor)

        governed = RuleSet.in_force_on(timezone.now().date() - timedelta(days=50))
        self.assertEqual(governed, first)

    def test_publishing_twice_is_refused(self):
        published = self._draft(1)
        policy_admin.publish_rule_set(published, actor=self.actor)
        with self.assertRaises(policy_admin.PolicyEditError):
            policy_admin.publish_rule_set(published, actor=self.actor)

    def test_a_superseded_set_cannot_be_republished(self):
        first = self._draft(1)
        policy_admin.publish_rule_set(first, actor=self.actor)
        policy_admin.publish_rule_set(self._draft(2), actor=self.actor)

        first.refresh_from_db()
        with self.assertRaises(policy_admin.PolicyEditError):
            policy_admin.publish_rule_set(first, actor=self.actor)

    def test_publishing_is_audited(self):
        policy_admin.publish_rule_set(self._draft(1), actor=self.actor)
        self.assertTrue(
            AuditEntry.objects.filter(action='policy.rule_set_published').exists())


class PolicyEndpointTests(TestCase):
    """Who may read a rate, and who may change one."""

    def setUp(self):
        from rest_framework.test import APIClient

        seed_rates()
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.setting = PolicySetting.objects.get(
            section='psssp_living', key='fulltime_no_dependents')
        self.admin = make_admin()
        self.worker = make_admin(Role.SUPPORT_WORKER)
        self.student = make_admin(Role.STUDENT)

    def test_staff_can_read_the_rates_behind_an_award(self):
        self.client.force_authenticate(self.worker)
        response = self.client.get('/api/policy/rates/')

        self.assertEqual(response.status_code, 200)
        sections = {group['section'] for group in response.data}
        self.assertIn('psssp_living', sections)

    def test_a_student_cannot_read_the_rates(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/policy/rates/').status_code, 403)

    def test_an_administrator_can_change_a_rate(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/policy/rates/{self.setting.id}/', {'value': '2100'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['value'], '2100.00')
        self.assertTrue(PolicyChange.objects.filter(setting=self.setting).exists())

    def test_a_support_worker_cannot_change_a_rate(self):
        """Reading a rate to explain an award is not the same as setting it."""
        self.client.force_authenticate(self.worker)
        response = self.client.patch(
            f'/api/policy/rates/{self.setting.id}/', {'value': '9999'}, format='json')

        self.assertEqual(response.status_code, 403)
        self.setting.refresh_from_db()
        self.assertEqual(self.setting.value,
                         rate_of('psssp_living', 'fulltime_no_dependents'))

    def test_an_invalid_amount_is_reported_against_the_field(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/policy/rates/{self.setting.id}/', {'value': 'lots'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('value', response.data)

    def test_the_history_of_a_rate_is_readable(self):
        policy_admin.change_rate(self.setting, '1900', actor=self.admin)
        self.client.force_authenticate(self.worker)
        response = self.client.get(f'/api/policy/rates/{self.setting.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['history']), 1)
        self.assertEqual(response.data['history'][0]['changed_by'], self.admin.full_name)

    def test_a_rate_can_be_suspended_without_being_deleted(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/policy/rates/{self.setting.id}/', {'is_active': False}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_active'])

    def test_rule_sets_show_which_policy_governed_which_period(self):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.client.force_authenticate(self.worker)
        response = self.client.get('/api/policy/rule-sets/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['status'], 'published')
        self.assertGreater(response.data[0]['rule_count'], 0)

    def test_an_unknown_rate_is_a_404(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.patch('/api/policy/rates/999999/', {'value': '1'},
                              format='json').status_code, 404)


class RateUnitTests(TestCase):
    """A rate has to say what it is measured in.

    Every rate was seeded as '$' and the screen formatted all of them as money,
    so an 80% achievement threshold reached administrators as '$80.00'. The
    threshold decides which scholarship band a student is paid, and the screen
    that sets it was describing it as an amount of money.
    """

    def test_a_percentage_is_not_measured_in_dollars(self):
        self.assertEqual(policy_admin.unit_for('high_threshold_percent'), '%')
        self.assertEqual(policy_admin.unit_for('max_percent_covered'), '%')

    def test_an_amount_still_is(self):
        self.assertEqual(policy_admin.unit_for('high_achievement_award'), '$')
        self.assertEqual(policy_admin.unit_for('max_tuition'), '$')

    def test_no_seeded_percentage_claims_to_be_money(self):
        """Asserted over the seeded book rather than over the helper, because
        the helper being right is only interesting if the rates use it."""
        seed_rates()
        wrong = PolicySetting.objects.filter(key__contains='percent').exclude(unit='%')
        self.assertEqual(
            list(wrong.values_list('key', flat=True)), [],
            'a percentage rate is published as an amount of money',
        )
