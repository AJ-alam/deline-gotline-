"""Correcting the registrar's address moves the request with it.

`registrar_email` became a stored answer when the renewal started asking for
one, which made it editable — by the student answering a request for more
information, and by the office amending a filed application. Nothing noticed the
change: the application recorded the corrected address while the only live link
sat in the wrong institution's mailbox, and no screen said the two disagreed.

That is the office's most common corrective action. A registrar's address
bounces, the reviewer asks the student to fix it, the student fixes it, and
nothing is ever sent again — with tuition funded against the registrar's figure,
the application then cannot be priced by anybody, for a reason nothing explains.

Found by walking the path rather than by reading the code: the fix that added
the field and the fix that carried it at send time were both tested, and neither
test edited the address afterwards.
"""

import itertools

from rest_framework.test import APITestCase

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, EnrollmentVerification,
)
from funding.services import workflow
from funding.test_fixtures import admission_answers, confirm_enrolment, continuing_answers
from notifications.models import OutboundEmail

_counter = itertools.count(1)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'{role}{next(_counter)}@reissue.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class ReissueOnCorrectionTests(APITestCase):
    def setUp(self):
        self.student = make_user()
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.admin = make_user(Role.ADMIN)
        self.client.force_authenticate(self.student)

        response = self.client.post('/api/applications/', {
            'type': 'continuing_funding',
            'answers': continuing_answers(registrar_email='typo@aurora.test'),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

    def verification(self):
        return EnrollmentVerification.objects.filter(
            application=self.application).first()

    def stored(self):
        return self.client.get(f'/api/applications/{self.application.pk}/').data['answers']

    def ask_for_more(self):
        workflow.record(self.application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(self.application, ApplicationEvent.Action.INFO_REQUESTED,
                        self.worker, note='Your registrar address bounced.')

    # ── The student fixing it ───────────────────────────────────────────────

    def test_it_starts_pointed_at_the_typo(self):
        self.assertEqual(self.verification().registrar_email, 'typo@aurora.test')

    def test_a_student_correcting_it_moves_the_request(self):
        self.ask_for_more()
        self.client.force_authenticate(self.student)
        answers = self.stored()

        response = self.client.post(
            f'/api/applications/{self.application.pk}/revise/',
            {'answers': {**answers, 'registrar_email': 'right@aurora.test'}},
            format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.verification().registrar_email, 'right@aurora.test')

    def test_and_the_institution_is_actually_written_to(self):
        """A row moved is not a request sent.

        `send_enrolment_request` queues on commit, deliberately — a registrar
        must never receive a link to a request that was rolled back. A TestCase
        never commits, so the callback has to be captured or this asserts that
        the transaction wrapper works rather than that the mail is queued.
        """
        self.ask_for_more()
        self.client.force_authenticate(self.student)
        before = OutboundEmail.objects.filter(to_email='right@aurora.test').count()

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/api/applications/{self.application.pk}/revise/',
                             {'answers': {**self.stored(),
                                          'registrar_email': 'right@aurora.test'}},
                             format='json')

        self.assertEqual(
            OutboundEmail.objects.filter(to_email='right@aurora.test').count(),
            before + 1)

    def test_the_link_that_bounced_stops_working(self):
        """Two live links to one application is how a registrar confirms an
        enrolment from an address the office has stopped trusting."""
        self.ask_for_more()
        old_token = self.verification().token
        self.client.force_authenticate(self.student)

        self.client.post(f'/api/applications/{self.application.pk}/revise/',
                         {'answers': {**self.stored(),
                                      'registrar_email': 'right@aurora.test'}},
                         format='json')

        self.assertNotEqual(self.verification().token, old_token)
        self.assertEqual(
            self.client.get(f'/api/enrolment/{old_token}/').status_code, 404)

    # ── The office fixing it ────────────────────────────────────────────────

    def test_an_administrator_correcting_it_moves_the_request(self):
        self.client.force_authenticate(self.admin)
        answers = self.stored()

        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': {**answers, 'registrar_email': 'office@aurora.test'},
             'note': 'Corrected by phone.'},
            format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.verification().registrar_email, 'office@aurora.test')

    # ── When it must NOT fire ───────────────────────────────────────────────

    def test_an_edit_that_leaves_the_address_alone_sends_nothing(self):
        """A second link invalidates the one a registrar may be part-way
        through filling in. An edit to a misspelled programme must not do that.
        """
        self.client.force_authenticate(self.admin)
        token = self.verification().token
        before = OutboundEmail.objects.count()

        self.client.post(f'/api/applications/{self.application.pk}/amend/',
                         {'answers': {**self.stored(), 'program': 'Nursing (corrected)'},
                          'note': 'Programme name.'}, format='json')

        self.assertEqual(self.verification().token, token,
                         'the live link must survive an unrelated edit')
        self.assertEqual(OutboundEmail.objects.count(), before)

    def test_nor_does_a_change_of_case_or_spacing(self):
        self.client.force_authenticate(self.admin)
        token = self.verification().token

        self.client.post(f'/api/applications/{self.application.pk}/amend/',
                         {'answers': {**self.stored(),
                                      'registrar_email': '  TYPO@Aurora.test '},
                          'note': 'probe'}, format='json')

        self.assertEqual(self.verification().token, token,
                         'the same address written differently is the same address')

    def test_a_confirmed_enrolment_is_never_asked_again(self):
        """The institution has answered, and the answer is what tuition is
        funded against. An address corrected afterwards is a correction to the
        record, not a reason to send a registrar a second form."""
        confirm_enrolment(self.application)
        self.assertEqual(self.verification().status,
                         EnrollmentVerification.Status.COMPLETED)

        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/applications/{self.application.pk}/amend/',
                         {'answers': {**self.stored(),
                                      'registrar_email': 'late@aurora.test'},
                          'note': 'probe'}, format='json')

        current = self.verification()
        self.assertEqual(current.status, EnrollmentVerification.Status.COMPLETED)
        self.assertNotEqual(current.registrar_email, 'late@aurora.test')

    def test_a_type_that_needs_no_institution_is_untouched(self):
        """An appeal has no registrar. Reissuing on one would create a
        verification for an application that must never have one."""
        self.client.force_authenticate(self.student)
        from funding.test_fixtures import answers_for

        appeal = self.client.post('/api/applications/', {
            'type': 'appeal', 'answers': answers_for('appeal'),
        }, format='json')
        appeal_id = appeal.data['id']

        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/applications/{appeal_id}/amend/',
                         {'answers': self.client.get(
                             f'/api/applications/{appeal_id}/').data['answers'],
                          'note': 'probe'}, format='json')

        self.assertFalse(
            EnrollmentVerification.objects.filter(application_id=appeal_id).exists())


class AdmissionReissueTests(APITestCase):
    """The same rule on the other type that needs a confirmation."""

    def setUp(self):
        self.student = make_user()
        self.admin = make_user(Role.ADMIN)
        self.client.force_authenticate(self.student)
        response = self.client.post('/api/applications/', {
            'type': 'admission',
            'answers': admission_answers(registrar_email='typo@aurora.test'),
        }, format='json')
        self.application = Application.objects.get(pk=response.data['id'])

    def test_correcting_an_admission_s_registrar_moves_the_request(self):
        self.client.force_authenticate(self.admin)
        answers = self.client.get(
            f'/api/applications/{self.application.pk}/').data['answers']

        self.client.post(f'/api/applications/{self.application.pk}/amend/',
                         {'answers': {**answers, 'registrar_email': 'right@aurora.test'},
                          'note': 'Corrected.'}, format='json')

        self.assertEqual(
            EnrollmentVerification.objects.get(
                application=self.application).registrar_email,
            'right@aurora.test')
