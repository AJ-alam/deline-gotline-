"""End-to-end checks over the real URL routing and middleware stack.

Everything else in the suite runs with TESTING set, which switches off
SECURE_SSL_REDIRECT, HSTS, secure cookies and the proxy header. That means the
production security configuration is exercised by nothing at all unless it is
exercised here.

These tests drive a whole application lifecycle the way a client does, and they
override the security settings back on so the deployed configuration is what
gets checked.
"""

import itertools
from decimal import Decimal

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from accounts.test_eligibility import ELIGIBLE_BOTH
from funding.models import Application, PolicySetting
from funding.test_fixtures import (
    admission_answers, confirm_enrolment, verification_answers,
)

_counter = itertools.count(1)

# What Vercel sends after terminating TLS.
PROXY = {'HTTP_X_FORWARDED_PROTO': 'https'}

PRODUCTION_TRANSPORT = dict(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)

# Only the PSSSP rates, so the applicant below is deliberately PSSSP-only.
# An applicant who qualifies for DGGR as well is priced against the DGGR rules
# too — correctly, since the bursary tops up rather than replaces — and pricing
# then refuses until those rates exist, naming them. That is its own subject;
# this file is about the path an application takes.
RATES = [
    ('psssp_tuition', 'max_per_semester', '7000'),
    ('psssp_living', 'fulltime_no_dependents', '1800'),
]

ADMISSION_ANSWERS = admission_answers()


def seed():
    for section, key, value in RATES:
        PolicySetting.objects.update_or_create(
            section=section, key=key,
            defaults=dict(label=key, value=Decimal(value), unit='$'))
    call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                 verbosity=0)


def make_user(role=Role.STUDENT, deline_beneficiary=False):
    return User.objects.create_user(
        f'{role}{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=deline_beneficiary, is_indian_act_registered=True)


@override_settings(**PRODUCTION_TRANSPORT)
class TransportSecurityTests(TestCase):
    """The only place the deployed security settings are actually run."""

    def test_plain_http_is_redirected_to_https(self):
        response = Client().get('/api/schemas/')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers['Location'].startswith('https://'))

    def test_the_proxy_header_is_honoured(self):
        """Without this, every request behind Vercel's TLS terminator would
        redirect-loop."""
        response = Client(**PROXY).get('/api/schemas/')
        self.assertEqual(response.status_code, 200)


@override_settings(**PRODUCTION_TRANSPORT)
class ApplicationLifecycleTests(TestCase):
    """Register through to a priced award, over real routing."""

    def setUp(self):
        seed()
        self.client = APIClient(**PROXY)

    def _token(self, email, password='pw12345678'):
        response = self.client.post('/api/auth/token/',
                                    {'email': email, 'password': password},
                                    format='json')
        return response.data['access']

    def _as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._token(user.email)}')

    def test_a_student_can_register_sign_in_and_apply(self):
        response = self.client.post('/api/auth/register/', {
            'email': 'Smoke.Student@Example.COM', 'password': 'pw12345678',
            'confirm_password': 'pw12345678',
            'first_name': 'Smoke', 'last_name': 'Student',
            # Registration is gated on eligibility, enforced server-side.
            # The answers come from the eligibility tests rather than being
            # written out again: a question added there would otherwise leave
            # this set incomplete, and the failure reads as a broken sign-up
            # rather than as a stale fixture.
            'eligibility': dict(ELIGIBLE_BOTH),
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['email'], 'smoke.student@example.com')

        # Signing in with the case they originally typed must still work.
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self._token('Smoke.Student@Example.COM')}")

        response = self.client.post('/api/applications/', {
            'type': 'admission', 'stream': 'psssp', 'answers': ADMISSION_ANSWERS},
            format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'submitted')
        self.assertEqual([e['action'] for e in response.data['events']], ['submitted'])

    def test_the_full_review_and_award_path(self):
        student = make_user()
        worker = make_user(Role.SUPPORT_WORKER)
        director = make_user(Role.DIRECTOR)

        self._as(student)
        application_id = self.client.post('/api/applications/', {
            'type': 'admission', 'stream': 'psssp', 'answers': ADMISSION_ANSWERS},
            format='json').data['id']

        # The registrar confirms before anything can be forwarded: tuition is
        # funded against their figure, never the student's estimate.
        confirm_enrolment(Application.objects.get(pk=application_id))

        self._as(worker)
        for step in ('reviewed', 'forwarded'):
            response = self.client.post(f'/api/applications/{application_id}/transition/',
                                        {'action': step}, format='json')
            self.assertEqual(response.status_code, 200, step)

        # A support worker must not be able to decide.
        response = self.client.post(f'/api/applications/{application_id}/transition/',
                                    {'action': 'approved'}, format='json')
        self.assertEqual(response.status_code, 403)

        self._as(director)
        response = self.client.post(f'/api/applications/{application_id}/transition/',
                                    {'action': 'approved'}, format='json')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f'/api/applications/{application_id}/price/')
        self.assertEqual(response.status_code, 201)
        self.assertGreater(Decimal(response.data['total']), 0)
        self.assertTrue(response.data['lines'])
        self.assertTrue(response.data['trace']['rules'])

    def test_a_student_cannot_reach_another_students_application(self):
        owner, intruder = make_user(), make_user()
        self._as(owner)
        application_id = self.client.post('/api/applications/', {
            'type': 'admission', 'stream': 'psssp', 'answers': ADMISSION_ANSWERS},
            format='json').data['id']

        self._as(intruder)
        response = self.client.get(f'/api/applications/{application_id}/')
        # 404 rather than 403: existence is not disclosed.
        self.assertEqual(response.status_code, 404)

    def test_anonymous_requests_are_rejected(self):
        self.client.credentials()
        self.assertEqual(self.client.get('/api/applications/').status_code, 401)

    def test_a_bad_answer_names_the_field_it_belongs_to(self):
        self._as(make_user())
        response = self.client.post('/api/applications/', {
            'type': 'admission', 'stream': 'psssp',
            'answers': dict(ADMISSION_ANSWERS, course_load='whenever')}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('course_load', response.data['answers'])
