"""Form B: generated from the application, and required before any decision.

Three things have to hold, and each is a way the office could otherwise pay the
wrong amount:

  * the enrolment verification goes to the registrar automatically, filled in
    from the application, so nobody retypes a tuition figure;
  * an admission application cannot be forwarded or approved until the
    institution has confirmed — tuition is funded against the registrar's
    figure, never the student's estimate;
  * the Social Insurance Number never leaves the encrypted table it is written
    to, and in particular never reaches the registrar.
"""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicantIdentifier, ApplicationEvent, ApplicationStatus,
    ApplicationType, AuditEntry, EnrollmentVerification, FundingStream,
)
from funding.schemas import ValidationError, get_schema
from funding.services import identifiers, verification, workflow
from funding.test_fixtures import (
    TEST_SIN, admission_answers, verification_answers,
)
from funding.test_rules import seed_rates

Action = ApplicationEvent.Action


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@gate.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role, is_deline_beneficiary=True, is_indian_act_registered=True)


def submitted_admission(client=None, **overrides):
    """An admission application submitted the way a student submits one."""
    client = client or APIClient()
    student = make_user(email=f'student{User.objects.count()}@gate.test')
    client.force_authenticate(student)
    response = client.post('/api/applications/', {
        'type': 'admission', 'stream': 'psssp',
        'answers': admission_answers(**overrides),
    }, format='json')
    assert response.status_code == 201, response.data
    return Application.objects.get(pk=response.data['id'])


class GenerationTests(TestCase):
    """The registrar is asked automatically, and asked with the answers filled in."""

    def test_submitting_an_admission_asks_the_registrar(self):
        application = submitted_admission(registrar_email='registrar@aurora.ca')
        request = EnrollmentVerification.objects.get(application=application)
        self.assertEqual(request.registrar_email, 'registrar@aurora.ca')
        self.assertEqual(request.status, EnrollmentVerification.Status.REQUESTED)

    def test_the_form_arrives_filled_in_from_the_application(self):
        application = submitted_admission(
            institution_name='Aurora College', program='Environmental Science',
            tuition_requested='8888', student_number='DGG-2026-41',
        )
        prefill = verification.prefill_for(application)

        self.assertEqual(prefill['institution_name'], 'Aurora College')
        self.assertEqual(prefill['program'], 'Environmental Science')
        self.assertEqual(prefill['confirmed_tuition'], '8888.00')
        self.assertEqual(prefill['student_number'], 'DGG-2026-41')

    def test_the_prefilled_form_validates_against_its_own_schema(self):
        """A pre-fill that the form would reject is worse than none."""
        application = submitted_admission()
        prefill = verification.prefill_for(application)
        schema = get_schema('enrollment_verification')

        for key, value in prefill.items():
            with self.subTest(field=key):
                # Every pre-filled key must be a field the form defines, and the
                # value must survive that field's own cleaning.
                self.assertIn(key, schema.keys)
                schema.field(key).clean(value)

    def test_the_registrar_is_told_what_was_withheld_and_why(self):
        application = submitted_admission()
        request = EnrollmentVerification.objects.get(application=application)
        context = verification.context_for(request)
        self.assertIn('withheld', context['note_to_registrar'].lower())

    def test_the_link_reaches_the_registrar_over_http(self):
        application = submitted_admission(registrar_email='reg@aurora.ca')
        request = EnrollmentVerification.objects.get(application=application)

        response = APIClient().get(f'/api/enrolment/{request.token}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schema']['slug'], 'enrollment_verification')
        self.assertIn('prefill', response.data['application'])


class PrivacyTests(TestCase):
    """What must not travel with the form, or land in the answers column."""

    def setUp(self):
        self.application = submitted_admission()

    def test_the_sin_is_not_in_the_answers(self):
        self.assertNotIn('sin', self.application.answers)
        self.assertNotIn(TEST_SIN, str(self.application.answers))

    def test_the_sin_is_stored_encrypted(self):
        stored = ApplicantIdentifier.objects.get(application=self.application)
        self.assertNotIn(TEST_SIN, stored.ciphertext)
        self.assertEqual(stored.last_three, TEST_SIN[-3:])

    def test_the_sin_can_be_read_back_by_someone_who_needs_it(self):
        admin = make_user(Role.ADMIN, 'admin@gate.test')
        self.assertEqual(
            identifiers.reveal(self.application, admin, 'Federal PSSSP reporting'),
            TEST_SIN,
        )

    def test_reading_it_is_recorded(self):
        admin = make_user(Role.ADMIN, 'admin@gate.test')
        identifiers.reveal(self.application, admin, 'Federal PSSSP reporting')

        entry = AuditEntry.objects.get(action='identifier.revealed')
        self.assertEqual(entry.actor, admin)
        self.assertIn('PSSSP', entry.detail)

    def test_reading_it_without_a_reason_is_refused(self):
        admin = make_user(Role.ADMIN, 'admin@gate.test')
        with self.assertRaises(identifiers.IdentifierError):
            identifiers.reveal(self.application, admin, '   ')
        self.assertFalse(AuditEntry.objects.filter(action='identifier.revealed').exists())

    def test_staff_reading_the_application_get_only_the_last_three_digits(self):
        client = APIClient()
        client.force_authenticate(make_user(Role.SUPPORT_WORKER, 'worker@gate.test'))

        response = client.get(f'/api/applications/{self.application.pk}/')

        self.assertEqual(response.data['identifiers']['sin'], f'•••••{TEST_SIN[-3:]}')
        self.assertNotIn(TEST_SIN, str(response.data))

    def test_the_registrar_is_sent_neither_the_sin_nor_the_date_of_birth(self):
        """The institution confirms an enrolment; it has no need for either."""
        request = EnrollmentVerification.objects.get(application=self.application)
        payload = str(APIClient().get(f'/api/enrolment/{request.token}/').data)

        self.assertNotIn(TEST_SIN, payload)
        self.assertNotIn('date_of_birth', payload)

    def test_the_form_has_no_field_that_could_carry_them(self):
        keys = get_schema('enrollment_verification').keys
        self.assertNotIn('sin', keys)
        self.assertNotIn('date_of_birth', keys)


class SinValidationTests(TestCase):

    def setUp(self):
        self.field = get_schema('admission').field('sin')

    def test_a_valid_number_is_accepted_and_stored_as_digits(self):
        self.assertEqual(self.field.clean('199 999 996'), '199999996')

    def test_a_transposition_is_caught(self):
        """The commonest typing mistake, and the reason for the check digit."""
        with self.assertRaises(ValueError):
            self.field.clean('199999969')

    def test_the_wrong_length_is_refused(self):
        with self.assertRaises(ValueError):
            self.field.clean('12345678')

    def test_a_leading_zero_is_refused(self):
        """No issued SIN begins with 0 — the first digit is the province."""
        with self.assertRaises(ValueError):
            self.field.clean('046454286')

    def test_it_is_required_on_the_admission_form(self):
        answers = admission_answers()
        del answers['sin']
        with self.assertRaises(ValidationError) as caught:
            get_schema('admission').clean(answers)
        self.assertIn('sin', caught.exception.errors)


class GateTests(TestCase):
    """Nothing is decided before the institution has answered."""

    def setUp(self):
        self.application = submitted_admission()
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@gate.test')
        self.director = make_user(Role.DIRECTOR, 'director@gate.test')

    def test_review_is_allowed_before_the_registrar_answers(self):
        """Staff can start work; they just cannot commit to an amount."""
        workflow.record(self.application, Action.REVIEWED, self.worker)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.UNDER_REVIEW)

    def test_forwarding_is_refused_until_the_institution_confirms(self):
        workflow.record(self.application, Action.REVIEWED, self.worker)
        with self.assertRaises(workflow.EnrolmentNotConfirmed):
            workflow.record(self.application, Action.FORWARDED, self.worker)

    def test_approving_is_refused_until_the_institution_confirms(self):
        """Defence in depth.

        In the ordinary run of things approval cannot be reached without
        forwarding, which is already gated. This puts the application straight
        into awaiting-decision — as a repair script or an imported record
        might — and checks the gate still holds on the approval itself, rather
        than relying on the forward having caught it.
        """
        Application.objects.filter(pk=self.application.pk).update(
            status=ApplicationStatus.AWAITING_DECISION)
        self.application.refresh_from_db()

        with self.assertRaises(workflow.EnrolmentNotConfirmed):
            workflow.record(self.application, Action.APPROVED, self.director)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.AWAITING_DECISION)

    def test_declining_is_never_blocked(self):
        """An application that will not be approved must not be held open
        waiting on a registrar who may never answer."""
        workflow.record(self.application, Action.REVIEWED, self.worker)
        workflow.record(self.application, Action.DECLINED, self.director, 'Not eligible')
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.DECLINED)

    def test_a_type_with_no_institution_is_not_gated(self):
        bursary = Application.objects.create(
            student=make_user(email='bursary@gate.test'),
            type=ApplicationType.GRADUATION_BURSARY, stream=FundingStream.DGGR,
            schema_slug='graduation_bursary', status=ApplicationStatus.UNDER_REVIEW,
            answers={'credential': 'diploma'})

        workflow.record(bursary, Action.FORWARDED, self.worker)
        bursary.refresh_from_db()
        self.assertEqual(bursary.status, ApplicationStatus.AWAITING_DECISION)

    def test_a_registrar_saying_not_enrolled_does_not_open_the_gate(self):
        """Confirmed and enrolled are different answers."""
        workflow.record(self.application, Action.REVIEWED, self.worker)
        request = EnrollmentVerification.objects.get(application=self.application)
        verification.complete(request, verification_answers(is_enrolled='false'))

        with self.assertRaises(workflow.EnrolmentNotConfirmed):
            workflow.record(self.application, Action.FORWARDED, self.worker)

    def test_once_confirmed_the_application_moves(self):
        workflow.record(self.application, Action.REVIEWED, self.worker)
        request = EnrollmentVerification.objects.get(application=self.application)
        verification.complete(request, verification_answers())

        workflow.record(self.application, Action.FORWARDED, self.worker)
        workflow.record(self.application, Action.APPROVED, self.director)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.APPROVED)


class GateOverHttpTests(TestCase):
    """What a reviewer sees when they try, and what the queue tells them."""

    def setUp(self):
        self.client = APIClient()
        self.application = submitted_admission()
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@gate.test')

    def test_the_refusal_says_what_is_blocking_it(self):
        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/transition/',
                         {'action': 'reviewed'}, format='json')

        response = self.client.post(
            f'/api/applications/{self.application.pk}/transition/',
            {'action': 'forwarded'}, format='json')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['blocked_by'], 'enrolment_verification')
        self.assertIn('institution', response.data['detail'].lower())

    def test_the_queue_row_reports_the_enrolment_state(self):
        """Staff should know before they open it that it cannot be forwarded."""
        self.client.force_authenticate(self.worker)
        row = next(r for r in self.client.get('/api/applications/').data['results']
                   if r['id'] == self.application.pk)

        self.assertTrue(row['enrolment']['required'])
        self.assertEqual(row['enrolment']['status'], 'requested')
        self.assertFalse(row['enrolment']['confirmed'])

    def test_the_state_becomes_confirmed_once_the_registrar_answers(self):
        request = EnrollmentVerification.objects.get(application=self.application)
        APIClient().post(f'/api/enrolment/{request.token}/',
                         {'answers': verification_answers()}, format='json')

        self.client.force_authenticate(self.worker)
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data

        self.assertEqual(detail['enrolment']['status'], 'completed')
        self.assertTrue(detail['enrolment']['confirmed'])

    def test_what_the_institution_declared_is_readable_by_staff(self):
        request = EnrollmentVerification.objects.get(application=self.application)
        APIClient().post(
            f'/api/enrolment/{request.token}/',
            {'answers': verification_answers(books_amount='450',
                                             registrar_notes='Part load in term two.')},
            format='json')

        self.client.force_authenticate(self.worker)
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data

        self.assertEqual(detail['enrolment_answers']['books_amount'], '450.00')
        self.assertIn('Part load', detail['enrolment_answers']['registrar_notes'])

    def test_the_declaration_is_not_merged_into_the_students_own_answers(self):
        """The application must not end up carrying keys its schema does not define."""
        request = EnrollmentVerification.objects.get(application=self.application)
        APIClient().post(f'/api/enrolment/{request.token}/',
                         {'answers': verification_answers(books_amount='450')},
                         format='json')

        self.application.refresh_from_db()
        self.assertNotIn('books_amount', self.application.answers)
        self.assertNotIn('registrar_notes', self.application.answers)


class ConfirmedFigureTests(TestCase):
    """The registrar's tuition figure is the one that gets paid."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def test_the_award_follows_the_institution_not_the_student(self):
        application = submitted_admission(tuition_requested='9999')
        worker = make_user(Role.SUPPORT_WORKER, 'worker@gate.test')
        director = make_user(Role.DIRECTOR, 'director@gate.test')

        request = EnrollmentVerification.objects.get(application=application)
        verification.complete(request, verification_answers(confirmed_tuition='4200'))

        workflow.record(application, Action.REVIEWED, worker)
        workflow.record(application, Action.FORWARDED, worker)
        workflow.record(application, Action.APPROVED, director)

        application.refresh_from_db()
        self.assertEqual(application.answers['confirmed_tuition'], '4200.00')

        from funding.services.decisions import record_decision
        decision = record_decision(application, actor=director)
        tuition = [line for line in decision.lines.all() if 'tuition' in line.rule_code]
        self.assertTrue(tuition)
        self.assertLessEqual(sum(line.amount for line in tuition), Decimal('4200.00'))


class PreviewTests(TestCase):
    """What the student is shown before submitting.

    A preview built from a second copy of the pre-fill logic would drift from
    what actually gets sent, and the drift would only show up as a registrar
    receiving something different from what the student approved.
    """

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user(email='previewer@gate.test'))

    def preview(self, **overrides):
        return self.client.post('/api/enrolment-preview/', {
            'type': 'admission', 'answers': admission_answers(**overrides),
        }, format='json')

    def test_it_returns_the_form_and_the_prefill(self):
        response = self.preview(institution_name='Aurora College')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schema']['slug'], 'enrollment_verification')
        self.assertEqual(response.data['prefill']['institution_name'], 'Aurora College')

    def test_it_matches_what_the_registrar_would_actually_receive(self):
        """The property that makes a preview worth having."""
        answers = admission_answers(institution_name='Aurora College',
                                    tuition_requested='8888')
        shown = self.client.post('/api/enrolment-preview/',
                                 {'type': 'admission', 'answers': answers},
                                 format='json').data['prefill']

        application = Application.objects.create(
            student=make_user(email='real@gate.test'), type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            answers={k: str(v) for k, v in answers.items() if k != 'sin'})
        sent = verification.prefill_for(application)

        self.assertEqual(shown['institution_name'], sent['institution_name'])
        self.assertEqual(shown['confirmed_tuition'], sent['confirmed_tuition'])

    def test_it_says_what_was_withheld(self):
        self.assertIn('withheld',
                      self.preview().data['note_to_registrar'].lower())

    def test_the_preview_never_carries_the_sin(self):
        response = self.preview()
        self.assertNotIn(TEST_SIN, str(response.data))

    def test_nothing_is_stored(self):
        before = Application.objects.count()
        self.preview()
        self.assertEqual(Application.objects.count(), before)
        self.assertFalse(EnrollmentVerification.objects.exists())

    def test_a_type_with_no_registrar_is_refused(self):
        response = self.client.post('/api/enrolment-preview/', {
            'type': 'graduation_bursary', 'answers': {}}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_it_needs_a_signed_in_person(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.preview().status_code, 401)
