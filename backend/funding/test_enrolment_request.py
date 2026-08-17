"""Asking the institution to confirm — and asking again.

Submission raises the request automatically, but only when a registrar address
is already known. The renewal form does not ask for one: it is carried from the
student's last application. A student whose admission was on paper, or the
office's first renewal in the portal, has nothing to carry from — and the
request was skipped in silence.

What that costs is not a missing email. Tuition is funded against the
registrar's figure, so the application can never be forwarded or approved, by
anybody, and the screen said the confirmation was "not required" — the one
sentence that would stop a reviewer looking for the cause.

`verification.issue` had a single caller and no endpoint, so the comment
promising staff could reissue described something that did not exist. The same
gap left an expired request and a bounced address with no recovery.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, AuditEntry,
    EnrollmentVerification,
)
from funding.services import workflow
from funding.test_fixtures import answers_for, confirm_enrolment


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@enrol.test', 'pw12345678',
        first_name='Test', last_name=str(role).title(), role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class NoAddressToCarryTests(TestCase):
    """A renewal from somebody who has never filed in the portal before."""

    def setUp(self):
        self.student = make_user(email='student@enrol.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@enrol.test')
        self.director = make_user(Role.DIRECTOR, 'director@enrol.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)

        response = self.client.post('/api/applications/', {
            'type': 'continuing_funding',
            'answers': answers_for('continuing_funding'),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

    def test_no_request_goes_out_when_there_is_no_address(self):
        self.assertFalse(
            EnrollmentVerification.objects.filter(application=self.application).exists())

    def test_the_screen_does_not_call_it_not_required(self):
        """It is required. It has not been asked for, which is a different
        thing and the one staff have to act on."""
        self.client.force_authenticate(self.worker)
        enrolment = self.client.get(
            f'/api/applications/{self.application.pk}/').data['enrolment']

        self.assertTrue(enrolment['required'])
        self.assertEqual(enrolment['status'], 'not_requested')

    def test_staff_can_issue_the_request_themselves(self):
        self.client.force_authenticate(self.worker)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/request-enrolment/',
            {'registrar_email': 'registrar@aurora.test'}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        verification = EnrollmentVerification.objects.get(application=self.application)
        self.assertEqual(verification.registrar_email, 'registrar@aurora.test')

    def test_without_an_address_it_says_so_rather_than_failing_quietly(self):
        self.client.force_authenticate(self.worker)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/request-enrolment/',
            {}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('registrar_email', response.data)

    def test_the_application_can_then_be_carried_through(self):
        """The whole point: before this it could not be forwarded by anybody,
        for a reason nothing on the screen explained."""
        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/request-enrolment/',
                         {'registrar_email': 'registrar@aurora.test'}, format='json')

        confirm_enrolment(self.application)

        workflow.record(self.application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.APPROVED, self.director)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.APPROVED)

    def test_it_is_recorded_who_asked(self):
        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/request-enrolment/',
                         {'registrar_email': 'registrar@aurora.test'}, format='json')

        entry = AuditEntry.objects.get(action='application.enrolment_requested')
        self.assertEqual(entry.actor, self.worker)
        self.assertIn('registrar@aurora.test', entry.detail)

    def test_a_student_cannot_ask_their_own_institution(self):
        """The request carries the office's authority, and the answer decides
        what is paid."""
        self.client.force_authenticate(self.student)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/request-enrolment/',
            {'registrar_email': 'friend@example.test'}, format='json')

        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(
            EnrollmentVerification.objects.filter(application=self.application).exists())


class ReissuingTests(TestCase):
    """The address that bounced, and the request that expired."""

    def setUp(self):
        self.student = make_user(email='student2@enrol.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker2@enrol.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        response = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': answers_for('admission'),
        }, format='json')
        self.application = Application.objects.get(pk=response.data['id'])

    def test_a_request_can_be_sent_to_a_corrected_address(self):
        first = EnrollmentVerification.objects.get(application=self.application)

        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/request-enrolment/',
                         {'registrar_email': 'right@aurora.test'}, format='json')

        current = EnrollmentVerification.objects.get(application=self.application)
        self.assertEqual(current.registrar_email, 'right@aurora.test')
        self.assertNotEqual(current.token, first.token,
                            'the superseded link must stop working')

    def test_a_confirmed_enrolment_is_not_asked_for_again(self):
        confirm_enrolment(self.application)

        self.client.force_authenticate(self.worker)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/request-enrolment/',
            {'registrar_email': 'again@aurora.test'}, format='json')

        self.assertEqual(response.status_code, 409)

    def test_a_form_with_no_institution_is_refused(self):
        self.client.force_authenticate(self.student)
        graduation = self.client.post('/api/applications/', {
            'type': 'graduation_bursary',
            'answers': answers_for('graduation_bursary'),
        }, format='json')

        self.client.force_authenticate(self.worker)
        response = self.client.post(
            f'/api/applications/{graduation.data["id"]}/request-enrolment/',
            {'registrar_email': 'registrar@aurora.test'}, format='json')

        self.assertEqual(response.status_code, 400)
