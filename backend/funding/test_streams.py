"""Which pot an application is funded from.

The stream used to be a dropdown the client filled in and the server stored as
given. It gates `applies_to_streams` on the tuition and living-allowance rules,
so it decides which caps and rates apply — which means a client that could
choose it could choose a stream the applicant does not qualify for and change
what they are paid.

These pin that the server decides it, from the same facts the sign-up screening
used, and that a client cannot override it.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import Application, ApplicationType, FundingStream
from funding.services import streams
from funding.test_fixtures import admission_answers


def make_student(email='s@streams.test', registered=True, beneficiary=True):
    return User.objects.create_user(
        email, 'pw12345678', first_name='Test', last_name='Person',
        role=Role.STUDENT,
        is_indian_act_registered=registered,
        is_deline_beneficiary=beneficiary,
    )


class DerivationTests(TestCase):
    """The office's rules, transcribed: PSSSP needs Indian Act registration and
    no SFA; DGGR needs beneficiary status and SFA does not block it."""

    def test_registered_and_not_on_sfa_is_funded_from_psssp(self):
        student = make_student(registered=True, beneficiary=False)
        self.assertEqual(
            streams.for_application(student, ApplicationType.ADMISSION,
                                    {'receives_sfa': False}),
            FundingStream.PSSSP)

    def test_sfa_takes_psssp_away(self):
        student = make_student(registered=True, beneficiary=True)
        self.assertEqual(
            streams.for_application(student, ApplicationType.ADMISSION,
                                    {'receives_sfa': True}),
            FundingStream.DGGR)

    def test_sfa_does_not_take_dggr_away(self):
        student = make_student(registered=False, beneficiary=True)
        self.assertEqual(
            streams.for_application(student, ApplicationType.ADMISSION,
                                    {'receives_sfa': True}),
            FundingStream.DGGR)

    def test_someone_who_qualifies_for_both_gets_the_federal_programme(self):
        """DGGR tops up rather than replaces. Funding a student from the smaller
        pot because a dropdown defaulted that way is the bug this removes."""
        student = make_student(registered=True, beneficiary=True)
        self.assertEqual(
            streams.for_application(student, ApplicationType.ADMISSION,
                                    {'receives_sfa': False}),
            FundingStream.PSSSP)

    def test_sfa_is_read_from_the_application_not_the_person(self):
        """It changes every term, so it is not a fact about someone."""
        student = make_student(registered=True, beneficiary=True)
        self.assertFalse(hasattr(student, 'receives_sfa'))
        self.assertEqual(
            streams.for_application(student, ApplicationType.ADMISSION,
                                    {'receives_sfa': 'yes'}),
            FundingStream.DGGR)

    def test_a_bursary_is_always_from_the_governments_own_funds(self):
        student = make_student(registered=True, beneficiary=True)
        for application_type in streams.ALWAYS_DGGR:
            with self.subTest(type=application_type):
                self.assertEqual(
                    streams.for_application(student, application_type,
                                            {'receives_sfa': False}),
                    FundingStream.DGGR)

    def test_someone_who_qualifies_for_nothing_is_refused_rather_than_guessed_at(self):
        student = make_student(registered=False, beneficiary=False)
        with self.assertRaises(streams.NoStreamAvailable):
            streams.for_application(student, ApplicationType.ADMISSION, {})

    def test_ucepp_is_never_assigned_automatically(self):
        """It has rates and rules, but nothing in the screening selects it — it
        is the office's to assign."""
        for registered, beneficiary in ((True, True), (True, False), (False, True)):
            with self.subTest(registered=registered, beneficiary=beneficiary):
                student = make_student(f'{registered}{beneficiary}@streams.test',
                                       registered, beneficiary)
                self.assertNotEqual(
                    streams.for_application(student, ApplicationType.ADMISSION,
                                            {'receives_sfa': False}),
                    FundingStream.UCEPP)


class SubmissionTests(TestCase):
    """Over HTTP, where a client might try to choose."""

    def setUp(self):
        self.client = APIClient()

    def submit(self, student, **extra):
        self.client.force_authenticate(student)
        body = {'type': 'admission', 'answers': admission_answers(receives_sfa='false')}
        body.update(extra)
        return self.client.post('/api/applications/', body, format='json')

    def test_the_stream_is_assigned_without_the_client_sending_one(self):
        response = self.submit(make_student())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['stream'], FundingStream.PSSSP)

    def test_a_stream_sent_by_the_client_is_ignored(self):
        """The whole point: it cannot be chosen, only derived."""
        response = self.submit(make_student(registered=False, beneficiary=True),
                               stream='psssp')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['stream'], FundingStream.DGGR)
        self.assertEqual(Application.objects.get().stream, FundingStream.DGGR)

    def test_the_sfa_answer_on_this_application_decides_it(self):
        """Same student, same account flags — the answer on the form is what
        moves them off the federal programme."""
        student = make_student()

        on_sfa = self.submit(student, answers=admission_answers(receives_sfa='true'))
        self.assertEqual(on_sfa.status_code, 201)
        self.assertEqual(on_sfa.data['stream'], FundingStream.DGGR)

        not_on_sfa = self.submit(student, answers=admission_answers(receives_sfa='false'))
        self.assertEqual(not_on_sfa.data['stream'], FundingStream.PSSSP)

    def test_an_account_that_qualifies_for_nothing_is_told_so(self):
        response = self.submit(make_student(registered=False, beneficiary=False))
        self.assertEqual(response.status_code, 409)
        self.assertIn('Education Department', response.data['detail'])
