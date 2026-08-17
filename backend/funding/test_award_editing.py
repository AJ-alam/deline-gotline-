"""Setting the funding breakdown by hand, and telling the office whose turn it is.

The rules price the ordinary case. They cannot know that an institution charges
a fee no rate covers, or that the office agreed something at the counter. Until
this existed the only ways to express that were to edit a policy rate — which
changes what *everyone* is paid — or to pay the wrong amount.

A hand-set award is a decision like any other: it supersedes rather than
overwrites, every line records who entered it, and an appeal argues against it
the same way. Re-pricing from the rules replaces it, which is the behaviour the
office asked for and the reason the screen warns first.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    AuditEntry, Award, AwardDecision, FundingStream,
)
from funding.services import workflow
from funding.services.decisions import record_decision
from funding.test_fixtures import confirm_enrolment
from funding.test_rules import seed_rates
from notifications.models import Notification


def make_user(role=Role.STUDENT, email=None, beneficiary=True):
    return User.objects.create_user(
        email or f'{role}@award.test', 'pw12345678',
        first_name='Test', last_name=str(role).title(), role=role,
        is_deline_beneficiary=beneficiary, is_indian_act_registered=True)


class ManualAwardTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.student = make_user(email='student@award.test')
        self.admin = make_user(Role.ADMIN, 'admin@award.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@award.test')
        self.director = make_user(Role.DIRECTOR, 'director@award.test')
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            status=ApplicationStatus.SUBMITTED,
            answers={'course_load': 'full_time', 'confirmed_tuition': '6000',
                     'semester_start': '2026-09-01', 'semester_end': '2026-12-31'},
        )
        self.client = APIClient()

    def set_award(self, actor=None, **overrides):
        self.client.force_authenticate(actor or self.admin)
        payload = {
            'lines': [
                {'category': 'tuition', 'amount': '6000.00',
                 'description': 'Tuition as billed'},
                {'category': 'travel', 'amount': '1200.00',
                 'description': 'Flight home at term end'},
            ],
            'note': 'Travel agreed at the counter.',
        }
        payload.update(overrides)
        return self.client.post(f'/api/applications/{self.application.pk}/award/',
                                payload, format='json')

    def test_an_administrator_can_set_the_breakdown(self):
        response = self.set_award()

        self.assertEqual(response.status_code, 201, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.awarded_total, Decimal('7200.00'))

    def test_a_line_the_rules_have_no_concept_of_can_be_added(self):
        """The point of it. Nothing in the rule set awards travel on an
        admission application; the office does, sometimes."""
        self.set_award()

        categories = set(Award.objects.current()
                         .filter(application=self.application)
                         .values_list('category', flat=True))
        self.assertIn('travel', categories)

    def test_every_line_says_a_person_entered_it(self):
        self.set_award()

        decision = AwardDecision.objects.get(application=self.application,
                                             is_current=True)
        self.assertTrue(decision.trace['set_by_hand'])
        self.assertEqual(decision.trace['set_by'], self.admin.full_name)
        for rule in decision.trace['rules']:
            self.assertIn('Entered by', rule['reason'])
            self.assertIn('Travel agreed at the counter', rule['reason'])

    def test_it_supersedes_rather_than_overwrites(self):
        priced = record_decision(self.application)
        self.set_award()

        priced.refresh_from_db()
        self.assertFalse(priced.is_current)
        self.assertEqual(
            AwardDecision.objects.filter(application=self.application,
                                         is_current=True).count(), 1)
        self.assertEqual(
            Award.objects.filter(decision=priced, status=Award.Status.CANCELLED).count(),
            priced.lines.count())

    def test_re_pricing_replaces_the_hand_set_figures(self):
        """What the office asked for: the rules win again the moment somebody
        asks them to. The screen warns before doing it."""
        self.set_award()
        record_decision(self.application, actor=self.director)

        decision = AwardDecision.objects.get(application=self.application,
                                             is_current=True)
        self.assertNotIn('set_by_hand', decision.trace)

    def test_nobody_but_an_administrator_may_set_one(self):
        for actor in (self.worker, self.director, self.student):
            response = self.set_award(actor=actor)
            self.assertEqual(response.status_code, 403, actor.role)
        self.assertFalse(
            AwardDecision.objects.filter(application=self.application).exists())

    def test_an_award_that_has_been_paid_is_not_editable(self):
        record_decision(self.application)
        Award.objects.filter(application=self.application).update(
            status=Award.Status.PAID)

        response = self.set_award()

        self.assertEqual(response.status_code, 400)
        self.assertIn('already been paid', str(response.data))

    def test_a_category_that_does_not_exist_is_refused(self):
        response = self.set_award(lines=[{'category': 'holiday', 'amount': '100'}])
        self.assertEqual(response.status_code, 400)

    def test_an_amount_that_is_not_a_number_is_refused(self):
        response = self.set_award(lines=[{'category': 'tuition', 'amount': 'lots'}])
        self.assertEqual(response.status_code, 400)

    def test_a_negative_line_is_refused(self):
        response = self.set_award(lines=[{'category': 'tuition', 'amount': '-500'}])
        self.assertEqual(response.status_code, 400)

    def test_an_empty_breakdown_is_refused(self):
        response = self.set_award(lines=[])
        self.assertEqual(response.status_code, 400)

    def test_it_is_recorded_who_set_it(self):
        self.set_award()
        entry = AuditEntry.objects.get(action='application.award_set_by_hand')
        self.assertEqual(entry.actor, self.admin)
        self.assertIn('7200', entry.detail)


class TellingTheOfficeTests(TestCase):
    """Everything told the applicant. Nothing told the office."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.student = make_user(email='student2@award.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker2@award.test')
        self.director = make_user(Role.DIRECTOR, 'director2@award.test')
        self.admin = make_user(Role.ADMIN, 'admin2@award.test')
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.APPEAL,
            stream=FundingStream.DGGR, schema_slug='appeal',
            status=ApplicationStatus.SUBMITTED, answers={},
        )
        Notification.objects.all().delete()

    def test_the_director_is_told_when_something_is_forwarded(self):
        """A director had no way to know an application was waiting for them
        except by opening the queue and looking."""
        workflow.record(self.application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.FORWARDED, self.worker)

        notice = Notification.objects.filter(user=self.director).first()
        self.assertIsNotNone(notice)
        self.assertIn('waiting for a decision', notice.title.lower())
        self.assertEqual(notice.link, f'/applications/{self.application.pk}')

    def test_the_reviewers_are_told_when_a_student_answers(self):
        workflow.record(self.application, ApplicationEvent.Action.INFO_REQUESTED,
                        self.worker, note='Send the transcript.')
        Notification.objects.filter(user=self.worker).delete()

        workflow.record(self.application, ApplicationEvent.Action.INFO_PROVIDED,
                        self.student)

        notice = Notification.objects.filter(user=self.worker).first()
        self.assertIsNotNone(notice)
        self.assertIn('answered', notice.title.lower())

    def test_the_director_is_told_when_an_administrator_decides_alone(self):
        """The office asked that an administrator be able to approve rather
        than forward. The director does not make that decision but still
        answers for it."""
        workflow.record(self.application, ApplicationEvent.Action.REVIEWED, self.admin)
        workflow.record(self.application, ApplicationEvent.Action.FORWARDED, self.admin)
        Notification.objects.filter(user=self.director).delete()

        workflow.record(self.application, ApplicationEvent.Action.APPROVED, self.admin)

        notice = Notification.objects.filter(user=self.director).first()
        self.assertIsNotNone(notice)
        self.assertIn('approved by', notice.title.lower())

    def test_a_directors_own_decision_does_not_notify_them(self):
        """They were there. A notice telling somebody what they just did is
        noise, and noise is what stops the useful ones being read."""
        workflow.record(self.application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.FORWARDED, self.worker)
        Notification.objects.filter(user=self.director).delete()

        workflow.record(self.application, ApplicationEvent.Action.APPROVED, self.director)

        self.assertFalse(Notification.objects.filter(
            user=self.director, title__icontains='approved by').exists())

    def test_the_applicant_is_still_told_everything(self):
        workflow.record(self.application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.APPROVED, self.director)

        self.assertTrue(Notification.objects.filter(user=self.student).exists())
