"""The registrar's enrolment confirmation.

Public and unauthenticated, and it decides the figure tuition is funded against,
so the token is a security boundary and is tested as one.
"""

import itertools
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, EnrollmentVerification,
    FundingStream, PolicySetting,
)
from funding.services import verification
from funding.services.decisions import record_decision
from funding.test_rules import seed_rates
from funding.test_fixtures import confirm_enrolment, verification_answers

_counter = itertools.count(1)

STUDENT_ANSWERS = {
    'first_name': 'Jane', 'last_name': 'Doe', 'date_of_birth': '2001-05-04',
    'email': 'jane@example.com', 'street_address': '1 Main St', 'city': 'Deline',
    'province': 'NT', 'institution_name': 'Aurora College', 'program': 'Nursing',
    'registrar_email': 'registrar@aurora.ca', 'semester': 'fall',
    'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
    'course_load': 'full_time', 'signature': 'Jane Doe',
    'tuition_requested': '9999',
    # Deliberately no beneficiary number here; see the leakage test below.
    'account_number': '9876543210',
}

REGISTRAR_ANSWERS = verification_answers()


def make_application(**kwargs):
    student = User.objects.create_user(
        f'v{next(_counter)}@test.com', 'pw12345678',
        first_name='Jane', last_name='Doe',is_deline_beneficiary=True, is_indian_act_registered=True)
    defaults = dict(
        student=student, type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
        schema_slug='admission', answers=dict(STUDENT_ANSWERS),
        status=ApplicationStatus.SUBMITTED,
    )
    defaults.update(kwargs)
    return Application.objects.create(**defaults)


class IssuingTests(TestCase):

    def test_a_link_is_issued_for_the_registrar(self):
        application = make_application()
        issued = verification.issue(application, 'registrar@aurora.ca')

        self.assertEqual(issued.status, EnrollmentVerification.Status.REQUESTED)
        self.assertGreater(len(issued.token), 32)
        self.assertGreater(issued.expires_at, timezone.now())

    def test_tokens_are_unpredictable(self):
        tokens = {
            verification.issue(make_application(), 'r@a.ca').token for _ in range(20)
        }
        self.assertEqual(len(tokens), 20)

    def test_reissuing_invalidates_the_previous_link(self):
        """Two live links to the same application would be two chances to answer."""
        application = make_application()
        first = verification.issue(application, 'registrar@aurora.ca')
        verification.issue(application, 'newregistrar@aurora.ca')

        with self.assertRaises(verification.VerificationError):
            verification.resolve(first.token)

    def test_a_confirmed_enrolment_cannot_be_reissued(self):
        application = make_application()
        issued = verification.issue(application, 'registrar@aurora.ca')
        verification.complete(issued, REGISTRAR_ANSWERS)

        with self.assertRaises(verification.VerificationError):
            verification.issue(application, 'registrar@aurora.ca')


class TokenSecurityTests(TestCase):

    def test_an_unknown_token_is_refused(self):
        with self.assertRaises(verification.VerificationError):
            verification.resolve('not-a-real-token')

    def test_an_expired_link_is_refused_and_marked(self):
        issued = verification.issue(make_application(), 'r@a.ca',
                                    validity=timedelta(seconds=-1))
        with self.assertRaises(verification.VerificationError):
            verification.resolve(issued.token)
        issued.refresh_from_db()
        self.assertEqual(issued.status, EnrollmentVerification.Status.EXPIRED)

    def test_failures_are_indistinguishable_from_one_another(self):
        """Different messages would tell someone probing which guesses were close."""
        expired = verification.issue(make_application(), 'r@a.ca',
                                     validity=timedelta(seconds=-1))
        messages = set()
        for token in ('completely-unknown', expired.token):
            try:
                verification.resolve(token)
            except verification.VerificationError as exc:
                messages.add(str(exc).split(' ')[1])   # 'link'
        self.assertEqual(messages, {'link'})

    def test_the_registrar_sees_only_what_they_need_to_answer(self):
        issued = verification.issue(make_application(), 'r@a.ca')
        shown = verification.context_for(issued)

        self.assertEqual(shown['student_name'], 'Jane Doe')
        self.assertEqual(shown['institution_name'], 'Aurora College')
        # A registrar is answering one question, not reviewing a file.
        leaked = {'account_number', 'street_address', 'beneficiary_number', 'email'}
        self.assertEqual(leaked & set(shown), set())


class CompletionTests(TestCase):

    def test_the_confirmed_figures_are_copied_onto_the_application(self):
        application = make_application()
        issued = verification.issue(application, 'r@a.ca')
        verification.complete(issued, REGISTRAR_ANSWERS)

        application.refresh_from_db()
        self.assertEqual(application.answers['confirmed_tuition'], '6000.00')
        self.assertEqual(application.answers['course_load'], 'full_time')

    def test_a_registrar_cannot_rewrite_the_students_own_answers(self):
        """Only the confirmable keys cross over."""
        application = make_application()
        issued = verification.issue(application, 'r@a.ca')
        verification.complete(issued, {**REGISTRAR_ANSWERS, 'student_name': 'Someone Else'})

        application.refresh_from_db()
        self.assertEqual(application.answers['first_name'], 'Jane')
        self.assertEqual(application.answers['account_number'], '9876543210')

    def test_a_link_can_only_be_used_once(self):
        issued = verification.issue(make_application(), 'r@a.ca')
        verification.complete(issued, REGISTRAR_ANSWERS)

        with self.assertRaises(verification.VerificationError):
            verification.complete(issued, REGISTRAR_ANSWERS)

    def test_invalid_answers_are_rejected_per_field(self):
        from funding.schemas import ValidationError

        issued = verification.issue(make_application(), 'r@a.ca')
        with self.assertRaises(ValidationError) as ctx:
            verification.complete(issued, {**REGISTRAR_ANSWERS, 'course_load': 'sometimes'})
        self.assertIn('course_load', ctx.exception.errors)


class AwardEffectTests(TestCase):
    """Confirmation is what releases tuition."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def test_no_tuition_is_awarded_before_the_registrar_confirms(self):
        application = make_application()
        decision = record_decision(application)
        tuition = [line for line in decision.lines.all() if line.category == 'tuition']
        self.assertEqual(tuition, [])

    def test_tuition_is_awarded_against_the_confirmed_figure_not_the_estimate(self):
        application = make_application()          # student estimated 9999
        issued = verification.issue(application, 'r@a.ca')
        verification.complete(issued, REGISTRAR_ANSWERS)   # registrar says 6000

        application.refresh_from_db()
        decision = record_decision(application)
        tuition = sum(
            line.amount for line in decision.lines.all() if line.category == 'tuition'
        )
        self.assertEqual(tuition, Decimal('6000.00'))


class EndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.application = make_application()
        self.issued = verification.issue(self.application, 'registrar@aurora.ca')

    def test_the_form_is_reachable_without_an_account(self):
        response = self.client.get(f'/api/enrolment/{self.issued.token}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['application']['student_name'], 'Jane Doe')
        self.assertTrue(response.data['schema']['fields'])

    def test_an_unknown_token_is_a_404(self):
        response = self.client.get('/api/enrolment/nonsense/')
        self.assertEqual(response.status_code, 404)

    def test_the_registrar_can_submit(self):
        response = self.client.post(
            f'/api/enrolment/{self.issued.token}/',
            {'answers': REGISTRAR_ANSWERS}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['confirmed_tuition'], '6000.00')

    def test_submitting_twice_is_refused(self):
        self.client.post(f'/api/enrolment/{self.issued.token}/',
                         {'answers': REGISTRAR_ANSWERS}, format='json')
        response = self.client.post(f'/api/enrolment/{self.issued.token}/',
                                    {'answers': REGISTRAR_ANSWERS}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_bad_answers_are_reported_per_field(self):
        response = self.client.post(
            f'/api/enrolment/{self.issued.token}/',
            {'answers': {**REGISTRAR_ANSWERS, 'course_load': 'sometimes'}}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('course_load', response.data['answers'])
