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
from funding.models import PolicySetting

_counter = itertools.count(1)

# What Vercel sends after terminating TLS.
PROXY = {'HTTP_X_FORWARDED_PROTO': 'https'}

PRODUCTION_TRANSPORT = dict(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)

RATES = [
    ('psssp_tuition', 'max_per_semester', '7000'),
    ('psssp_living', 'fulltime_no_dependents', '1800'),
    ('system_config', 'book_allowance', '500'),
]

ADMISSION_ANSWERS = {
    'first_name': 'Smoke', 'last_name': 'Student', 'date_of_birth': '2001-05-04',
    'email': 'smoke@example.com', 'street_address': '1 Main St', 'city': 'Deline',
    'province': 'NT', 'institution_name': 'Aurora College', 'program': 'Nursing',
    'registrar_email': 'reg@aurora.ca', 'semester': 'Fall',
    'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
    'course_load': 'Full-time', 'signature': 'Smoke Student',
    'tuition_requested': '6000',
    # Deliberately no confirmed_tuition: that is the registrar's figure, asked
    # for on the enrollment verification, and the schema rejects it here. Tuition
    # is therefore not awarded until verification arrives, which is the rule.
    'doc_transcript': 'provided', 'doc_letter_of_intent': 'provided',
    'doc_status_card': 'provided', 'doc_void_cheque': 'provided',
}


def seed():
    for section, key, value in RATES:
        PolicySetting.objects.update_or_create(
            section=section, key=key,
            defaults=dict(label=key, value=Decimal(value), unit='$'))
    call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                 verbosity=0)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'{role}{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name='Person', role=role)


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
            'first_name': 'Smoke', 'last_name': 'Student'}, format='json')
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
