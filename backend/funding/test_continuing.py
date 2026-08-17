"""The continuing-funding renewal.

This type had no test that ever submitted one. It was named in three membership
assertions and nothing else, so the whole suite passed while ten of its fields
were removed — which is the only reason these tests exist as a file rather than
as three additions to test_api.

The renewal is short on purpose: it shows what is already on file and asks the
student to confirm it. That shortness is exactly what makes it dangerous, so
most of what follows is about the answers it does *not* collect and where the
award calculation gets them instead.
"""

import itertools
from types import SimpleNamespace

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, EnrollmentVerification,
    FundingStream,
)
from funding.rules.engine import build_context
from funding.schemas import ValidationError, all_schemas, get_schema
from funding.services import deadlines, verification
from funding.test_fixtures import admission_answers, continuing_answers

_counter = itertools.count(1)


def make_student(**flags):
    defaults = dict(is_deline_beneficiary=True, is_indian_act_registered=True)
    defaults.update(flags)
    return User.objects.create_user(
        f'continuing{next(_counter)}@test.com', 'pw12345678',
        first_name='Majid', last_name='Khan', role=Role.STUDENT, **defaults)


def context_for(answers):
    """Just enough of an Application for the rules engine to flatten."""
    application = SimpleNamespace(
        answers=answers, type=ApplicationType.CONTINUING_FUNDING,
        stream=FundingStream.PSSSP,
    )
    return build_context(application, rates=None)


class ShapeTests(APITestCase):
    """What the form asks, and what it deliberately does not."""

    def test_it_asks_exactly_what_the_renewal_screen_shows(self):
        keys = set(get_schema('continuing_funding').keys)
        self.assertEqual(keys, {
            'full_name', 'beneficiary_number', 'email',
            'institution_name', 'program', 'course_load', 'dependent_count',
            'semester', 'receives_sfa',
            'doc_transcript', 'doc_enrollment_confirmation',
            'declaration_confirmed', 'signature',
        })

    def test_it_does_not_ask_for_figures_the_registrar_confirms(self):
        """Tuition has never been funded against a student's own estimate."""
        keys = set(get_schema('continuing_funding').keys)
        for key in ('tuition_requested', 'confirmed_tuition',
                    'semester_start', 'semester_end'):
            self.assertNotIn(key, keys)

    def test_every_question_falls_into_one_of_the_two_steps(self):
        """A section the frontend does not place would render on the last step."""
        schema = get_schema('continuing_funding')
        self.assertEqual(
            set(schema.sections),
            {'Review your information', 'Upload required documents', 'Declaration'},
        )


class DeclarationTests(APITestCase):
    """A declaration with two valid answers is not a declaration."""

    def test_an_unconfirmed_declaration_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            get_schema('continuing_funding').clean(
                continuing_answers(declaration_confirmed='false'))
        self.assertIn('declaration_confirmed', caught.exception.errors)

    def test_a_missing_declaration_is_refused(self):
        answers = continuing_answers()
        answers.pop('declaration_confirmed')
        with self.assertRaises(ValidationError) as caught:
            get_schema('continuing_funding').clean(answers)
        self.assertIn('declaration_confirmed', caught.exception.errors)

    def test_a_confirmed_declaration_is_stored_as_true(self):
        cleaned = get_schema('continuing_funding').clean(continuing_answers())
        self.assertIs(cleaned['declaration_confirmed'], True)


class StreamTests(APITestCase):
    """SFA decides which pot pays, so it is asked every semester.

    Dropping this question would not have failed anything: an absent answer
    reads as 'no SFA', and a student on SFA would be funded from PSSSP with
    PSSSP's caps.
    """

    def setUp(self):
        self.student = make_student()
        self.client.force_authenticate(self.student)

    def submit(self, **overrides):
        return self.client.post('/api/applications/', {
            'type': 'continuing_funding',
            'answers': continuing_answers(**overrides),
        }, format='json')

    def test_a_student_not_on_sfa_is_funded_from_psssp(self):
        response = self.submit(receives_sfa='false')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['stream'], FundingStream.PSSSP)

    def test_a_student_on_sfa_is_not_funded_from_psssp(self):
        response = self.submit(receives_sfa='true')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['stream'], FundingStream.DGGR)

    def test_the_question_cannot_be_left_unanswered(self):
        """An unanswered SFA question must not quietly become 'no SFA'.

        `streams.receives_sfa` reads a missing answer as False, so an optional
        field here would put every student who skipped it into PSSSP. Nothing
        else in this class catches that: they all supply an answer.
        """
        answers = continuing_answers()
        answers.pop('receives_sfa')
        response = self.client.post('/api/applications/', {
            'type': 'continuing_funding', 'answers': answers,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('receives_sfa', response.data['answers'])

    def test_the_semester_cannot_be_left_unanswered(self):
        """Without a term, deadlines.coordinates returns blanks and nothing is
        ever measured as late."""
        answers = continuing_answers()
        answers.pop('semester')
        response = self.client.post('/api/applications/', {
            'type': 'continuing_funding', 'answers': answers,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('semester', response.data['answers'])

    def test_the_answer_is_stored_as_a_boolean_not_a_word(self):
        """`_loose_equal` compares 'no' to True as bool('no') — which is True.

        A choice field spelling this yes/no would make both answers read as
        'on SFA' to every rule gated on it.
        """
        self.submit(receives_sfa='true')
        application = Application.objects.get(type='continuing_funding')
        self.assertIs(application.answers['receives_sfa'], True)


class DependantsTests(APITestCase):
    """The form asks how many; the engine asks whether."""

    def test_a_dependant_count_above_zero_selects_the_dependants_rate(self):
        self.assertEqual(
            context_for({'dependent_count': 2}).facts['dependants'],
            'with_dependents',
        )

    def test_no_dependants_selects_the_plain_rate(self):
        self.assertEqual(
            context_for({'dependent_count': 0}).facts['dependants'],
            'no_dependents',
        )

    def test_a_count_stored_as_a_string_still_counts(self):
        """Answers come back out of a JSON column, not out of Python."""
        self.assertEqual(
            context_for({'dependent_count': '3'}).facts['dependants'],
            'with_dependents',
        )

    def test_an_explicit_yes_no_still_wins_where_a_form_asks_it(self):
        """The admission form asks the boolean; it must not be overridden."""
        self.assertEqual(
            context_for({'has_dependents': True}).facts['dependants'],
            'with_dependents',
        )
        self.assertEqual(
            context_for({'has_dependents': False, 'dependent_count': 4}).facts['dependants'],
            'no_dependents',
        )


class RegistrarCarryOverTests(APITestCase):
    """The renewal promises the registrar is contacted. It has no field for one."""

    def setUp(self):
        self.student = make_student()
        self.client.force_authenticate(self.student)

    def file_admission(self, registrar='registrar@aurora.ca'):
        return self.client.post('/api/applications/', {
            'type': 'admission',
            'answers': admission_answers(registrar_email=registrar),
        }, format='json')

    def submit_renewal(self):
        return self.client.post('/api/applications/', {
            'type': 'continuing_funding', 'answers': continuing_answers(),
        }, format='json')

    def test_the_registrar_is_taken_from_the_application_on_file(self):
        self.file_admission()
        response = self.submit_renewal()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        issued = EnrollmentVerification.objects.get(
            application__type='continuing_funding')
        self.assertEqual(issued.registrar_email, 'registrar@aurora.ca')

    def test_a_renewal_with_nothing_on_file_does_not_fail_the_submission(self):
        """No registrar to reach is a gap for staff, not a 500 for the student."""
        response = self.submit_renewal()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApplicationStatus.SUBMITTED)
        self.assertFalse(
            EnrollmentVerification.objects.filter(
                application__type='continuing_funding').exists())

    def test_the_registrar_email_is_never_copied_into_the_renewals_answers(self):
        """It is carried at send time. Storing it would let it drift from the
        admission application it came from, silently, a semester later."""
        self.file_admission()
        self.submit_renewal()
        renewal = Application.objects.get(type='continuing_funding')
        self.assertNotIn('registrar_email', renewal.answers)


class PrefillTests(APITestCase):
    """Step one shows what is on file. It has to actually be on file."""

    def setUp(self):
        self.student = make_student()
        self.student.beneficiary_number = 'DGG-2026-0041'
        self.student.save(update_fields=['beneficiary_number'])
        self.client.force_authenticate(self.student)

    def prefill(self, slug='continuing_funding'):
        return self.client.get(f'/api/form-prefill/{slug}/')

    def file_admission(self, **overrides):
        answers = dict(institution_name='Aurora College',
                       program='Environmental Science')
        answers.update(overrides)
        return self.client.post('/api/applications/', {
            'type': 'admission', 'answers': admission_answers(**answers),
        }, format='json')

    def test_who_the_student_is_comes_from_their_account(self):
        answers = self.prefill().data['answers']
        self.assertEqual(answers['full_name'], 'Majid Khan')
        self.assertEqual(answers['email'], self.student.email)
        self.assertEqual(answers['beneficiary_number'], 'DGG-2026-0041')

    def test_where_they_study_comes_from_the_application_on_file(self):
        self.file_admission()
        answers = self.prefill().data['answers']
        self.assertEqual(answers['institution_name'], 'Aurora College')
        self.assertEqual(answers['program'], 'Environmental Science')
        self.assertEqual(answers['course_load'], 'full_time')

    def test_this_terms_answers_are_never_pre_filled(self):
        """Answering these for the student is the whole failure mode."""
        self.file_admission()
        answers = self.prefill().data['answers']
        for key in ('semester', 'receives_sfa', 'declaration_confirmed',
                    'signature', 'doc_transcript',
                    'doc_enrollment_confirmation'):
            self.assertNotIn(key, answers, key)

    def test_nothing_is_offered_that_the_schema_does_not_define(self):
        """An unknown answer is refused at validation, so a prefill that
        invented a key would make the form unsubmittable."""
        self.file_admission()
        keys = set(get_schema('continuing_funding').keys)
        self.assertTrue(set(self.prefill().data['answers']) <= keys)

    def test_a_student_with_no_history_still_gets_their_own_name(self):
        answers = self.prefill().data['answers']
        self.assertEqual(answers['full_name'], 'Majid Khan')
        self.assertNotIn('institution_name', answers)

    def test_one_students_history_never_reaches_another(self):
        self.file_admission(institution_name='Aurora College')
        self.client.force_authenticate(make_student())
        self.assertNotIn('institution_name', self.prefill().data['answers'])

    def test_it_is_never_cached_by_anything_in_between(self):
        self.assertIn('no-store', self.prefill()['Cache-Control'])

    def test_it_requires_signing_in(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.prefill().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_an_unknown_form_is_a_404(self):
        self.assertEqual(self.prefill('form-c').status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_every_form_that_asks_a_name_is_given_one(self):
        """A key the schema does not define is skipped without a word.

        `admission` and `travel` ask for `first_name` and `last_name`; the
        others ask for `full_name`. Only `full_name` was mapped, so on the first
        form anybody files, the name pre-filled as nothing — no error, no log,
        just a returning student typing what the portal already held. Asserted
        across every schema rather than for one form, because the fault was the
        gap between two schemas and a test for either one alone passes.
        """
        for schema in all_schemas():
            keys = set(schema.keys)
            asked = keys & {'full_name', 'first_name', 'last_name'}
            if not asked:
                continue
            response = self.prefill(schema.slug)
            if response.status_code != 200:
                continue
            answers = response.data['answers']
            for key in asked:
                self.assertTrue(
                    answers.get(key),
                    f'{schema.slug} asks for {key} and pre-fills nothing into it',
                )

    def test_what_the_account_holds_is_not_asked_for_again(self):
        """The address and date of birth are on the account and were never
        offered back, on any form."""
        self.student.date_of_birth = '1999-04-04'
        self.student.city = 'Deline'
        self.student.province = 'NT'
        self.student.postal_code = 'X0E 0G0'
        self.student.street_address = '1 Main Street'
        self.student.save()

        answers = self.prefill('admission').data['answers']
        self.assertEqual(str(answers['date_of_birth']), '1999-04-04')
        self.assertEqual(answers['city'], 'Deline')
        self.assertEqual(answers['postal_code'], 'X0E 0G0')





class NameTests(APITestCase):
    """The renewal spells the applicant's name differently from every other form."""

    def test_the_registrars_email_can_read_a_single_full_name(self):
        application = SimpleNamespace(
            answers={'full_name': 'Majid Khan'}, student=None)
        self.assertEqual(verification.student_name(application), 'Majid Khan')

    def test_a_named_student_is_carried_onto_the_generated_form(self):
        student = make_student()
        application = Application.objects.create(
            student=student, type=ApplicationType.CONTINUING_FUNDING,
            stream=FundingStream.PSSSP, schema_slug='continuing_funding',
            answers={'full_name': 'Majid Khan', 'program': 'Environmental Science'},
        )
        self.assertEqual(
            verification.prefill_for(application)['student_name'], 'Majid Khan')


class DeadlineTests(APITestCase):
    """Which semester is asked, so lateness can still be measured."""

    def test_a_renewal_lands_in_a_term(self):
        student = make_student()
        application = Application.objects.create(
            student=student, type=ApplicationType.CONTINUING_FUNDING,
            stream=FundingStream.PSSSP, schema_slug='continuing_funding',
            answers=continuing_answers(semester='fall'),
        )
        academic_year, semester = deadlines.coordinates(application)
        self.assertEqual(semester, 'fall')
        self.assertTrue(
            academic_year,
            'without a term the renewal can never be measured against a deadline',
        )
