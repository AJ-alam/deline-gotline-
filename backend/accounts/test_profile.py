"""The student's profile: identity, screening, enrolment, banking.

Four kinds of fact behind one screen, and the tests are grouped the same way.
Two of the groups are guards rather than features:

  * `ScreeningWriteTests` — the streams are decided by the office's rule from
    the student's answers, and cannot be supplied by a client. A profile screen
    that let somebody write their own funding stream would be the sign-up
    component's original fault, rebuilt.

  * `ProfileNeverPricesTests` — the enrolment profile pre-fills forms and is
    read by nothing that decides money. The previous system kept `institution`,
    `program` and `enrollment_status` on the user, and award calculation fell
    back to them whenever an answer was missing, so last year's facts priced
    this year's application.
"""

from __future__ import annotations

import itertools
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.api.serializers import EnrolmentProfileSerializer, UserSerializer
from accounts.models import BankAccount, EnrolmentProfile, Role, User
from accounts.services import profile as profile_service
from funding.models import (
    Application, ApplicationType, AuditEntry, FundingStream,
)
from funding.schemas import get_schema
from funding.services import prefill
from funding.test_fixtures import admission_answers as admission_fixture

_counter = itertools.count(1)

SCREENING_YES = {
    'indian_act_registered': 'yes',
    'deline_beneficiary': 'yes',
    'receives_sfa': 'no',
    'lives_in_nwt': 'yes',
    'accredited_institution': 'yes',
    'programme_twelve_weeks': 'yes',
}


def make_user(role=Role.STUDENT, **extra) -> User:
    defaults = dict(
        first_name='Sara', last_name='Student', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True,
        eligible_streams=['psssp', 'dggr'], eligibility_answers=dict(SCREENING_YES),
    )
    defaults.update(extra)
    return User.objects.create_user(
        f'p{next(_counter)}@profile.test', 'pw12345678', **defaults)


def signed_in(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Identity ─────────────────────────────────────────────────────────────────


class IdentityTests(TestCase):
    """What a student may correct about themselves on `/api/me/`."""

    def setUp(self):
        self.student = make_user()
        self.client = signed_in(self.student)

    def test_a_student_can_correct_their_own_details(self):
        response = self.client.patch('/api/me/', {
            'first_name': 'Sarah', 'phone': '8675550100',
            'street_address': '12 Lakeview', 'city': 'Délı̨nę',
            'province': 'NT', 'postal_code': 'X0E 0G0',
            'date_of_birth': '2001-04-12',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'Sarah')
        self.assertEqual(self.student.city, 'Délı̨nę')
        self.assertEqual(str(self.student.date_of_birth), '2001-04-12')

    def test_a_student_with_nothing_on_file_can_still_save_their_details(self):
        """The screen posts every box in the section, filled or not.

        Registration does not collect a date of birth, so on a first visit
        `date_of_birth` is posted empty — and a DRF DateField read that as a
        malformed date. Every student, on their first Save, was told their date
        of birth was wrong on a box they had left alone and could not save the
        section at all.

        Asserted across every editable field rather than against the one that
        broke: a text field takes '' silently, which is exactly why clearing a
        text field proved nothing.
        """
        optional = [
            name for name, field in UserSerializer().fields.items()
            # A person must have a name; everything else about them may be
            # unknown. Asserted directly below.
            if not field.read_only and name not in ('first_name', 'last_name')
        ]
        response = self.client.patch(
            '/api/me/', {name: '' for name in optional}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.date_of_birth)
        self.assertEqual(self.student.city, '')

    def test_a_person_must_still_have_a_name(self):
        """The other half of the same rule: blank means "nothing on file" only
        where nothing on file is a state a person can be in."""
        response = self.client.patch('/api/me/', {'first_name': '', 'last_name': ''},
                                     format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('first_name', response.json())
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'Sara')

    def test_a_detail_that_is_filled_in_survives_the_round_trip(self):
        """What the screen does on a second Save: post back what it read."""
        self.client.patch('/api/me/', {'date_of_birth': '2001-04-12'},
                          format='json')
        stored = self.client.get('/api/me/').json()

        again = self.client.patch('/api/me/', {
            name: stored[name] for name, field in UserSerializer().fields.items()
            if not field.read_only
        }, format='json')

        self.assertEqual(again.status_code, 200, again.data)
        self.student.refresh_from_db()
        self.assertEqual(str(self.student.date_of_birth), '2001-04-12')

    def test_the_email_and_role_are_not_editable(self):
        self.client.patch('/api/me/', {'email': 'someone@else.test',
                                       'role': Role.ADMIN}, format='json')
        self.student.refresh_from_db()
        self.assertNotEqual(self.student.email, 'someone@else.test')
        self.assertEqual(self.student.role, Role.STUDENT)

    def test_the_streams_are_not_editable(self):
        """Read-only, and read-only in the sense that matters: silently ignored
        rather than refused, because DRF drops read-only fields — so the test
        has to assert the stored value, not the status code."""
        self.client.patch('/api/me/',
                          {'eligible_streams': ['psssp', 'ucepp', 'dggr']},
                          format='json')
        self.student.refresh_from_db()
        self.assertEqual(self.student.eligible_streams, ['psssp', 'dggr'])

    def test_the_screening_booleans_are_not_editable_directly(self):
        """The hole this closes: `is_indian_act_registered` is what
        `streams.saved_streams` falls back to, so a student who could PATCH it
        could hand themselves PSSSP without the screening ever running."""
        student = make_user(is_indian_act_registered=False,
                            is_deline_beneficiary=False,
                            eligible_streams=[])
        signed_in(student).patch('/api/me/', {
            'is_indian_act_registered': True, 'is_deline_beneficiary': True,
        }, format='json')

        student.refresh_from_db()
        self.assertFalse(student.is_indian_act_registered)
        self.assertFalse(student.is_deline_beneficiary)

    def test_the_profile_is_private(self):
        for path in ('/api/me/', '/api/me/eligibility/', '/api/me/enrolment/',
                     '/api/me/banking/'):
            self.assertEqual(APIClient().get(path).status_code, 401, path)


# ── Screening ────────────────────────────────────────────────────────────────


class ScreeningReadTests(TestCase):
    def setUp(self):
        self.student = make_user()
        self.client = signed_in(self.student)

    def test_it_returns_the_questions_the_answers_and_the_outcome(self):
        body = self.client.get('/api/me/eligibility/').json()

        self.assertEqual(len(body['questions']), 6)
        self.assertEqual(body['answers'], SCREENING_YES)
        self.assertEqual(body['streams'], ['psssp', 'dggr'])

    def test_the_questions_are_the_office_s_own(self):
        """Served from `eligibility.QUESTIONS`, not restated by the profile.

        The wording, the order and the rule that reads them have to stay
        together — the sign-up page's original fault was that they did not.
        """
        from accounts.services import eligibility

        keys = [question['key'] for question in
                self.client.get('/api/me/eligibility/').json()['questions']]
        self.assertEqual(keys, [q['key'] for q in eligibility.QUESTIONS])

    def test_staff_have_no_screening(self):
        for role in (Role.SUPPORT_WORKER, Role.DIRECTOR, Role.FINANCE, Role.ADMIN):
            client = signed_in(make_user(role=role))
            self.assertEqual(client.get('/api/me/eligibility/').status_code, 403, role)


class ScreeningWriteTests(TestCase):
    def setUp(self):
        self.student = make_user()
        self.client = signed_in(self.student)

    def put(self, answers, client=None):
        return (client or self.client).put(
            '/api/me/eligibility/', {'answers': answers}, format='json')

    def test_re_answering_recomputes_the_streams(self):
        response = self.put({**SCREENING_YES, 'receives_sfa': 'yes'})

        self.assertEqual(response.status_code, 200)
        # SFA withdraws both C-DFN streams and leaves the DGGR bursary, which is
        # §7's arrangement rather than an accident of ordering.
        self.assertEqual(response.json()['streams'], ['dggr'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.eligible_streams, ['dggr'])

    def test_the_streams_cannot_be_supplied_by_the_client(self):
        """The whole point. A client sends answers; the office's rule decides."""
        response = self.client.put('/api/me/eligibility/', {
            'answers': {**SCREENING_YES, 'indian_act_registered': 'no'},
            'streams': ['psssp', 'ucepp', 'dggr'],
            'eligible_streams': ['psssp', 'ucepp', 'dggr'],
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.eligible_streams, ['dggr'])

    def test_the_answers_are_stored_as_given(self):
        answers = {**SCREENING_YES, 'lives_in_nwt': 'moving'}
        self.put(answers)

        self.student.refresh_from_db()
        self.assertEqual(self.student.eligibility_answers['lives_in_nwt'], 'moving')

    def test_the_booleans_follow_the_answers(self):
        """They are the fallback `streams.saved_streams` reads on old accounts.
        Left at what sign-up recorded, they are a stale funding decision waiting
        for the tags to be empty."""
        self.put({**SCREENING_YES, 'indian_act_registered': 'no'})

        self.student.refresh_from_db()
        self.assertFalse(self.student.is_indian_act_registered)
        self.assertTrue(self.student.is_deline_beneficiary)

    def test_the_assessment_date_moves(self):
        before = self.student.eligibility_assessed_at
        self.put(SCREENING_YES)
        self.student.refresh_from_db()
        self.assertIsNotNone(self.student.eligibility_assessed_at)
        self.assertNotEqual(self.student.eligibility_assessed_at, before)

    def test_a_partial_answer_set_is_refused(self):
        """Not a patch. Three answers would re-screen against a mixture of what
        is true now and what was true at sign-up."""
        response = self.put({'receives_sfa': 'yes'})

        self.assertEqual(response.status_code, 400)
        self.student.refresh_from_db()
        self.assertEqual(self.student.eligible_streams, ['psssp', 'dggr'])

    def test_a_blank_answer_counts_as_unanswered(self):
        response = self.put({**SCREENING_YES, 'accredited_institution': ''})
        self.assertEqual(response.status_code, 400)

    def test_an_answer_of_spaces_counts_as_unanswered(self):
        """`missing_answers` strips before it looks. A screen that posts a
        space would otherwise re-screen against six answers, one of which the
        rule reads as 'no'."""
        response = self.put({**SCREENING_YES, 'deline_beneficiary': '   '})
        self.assertEqual(response.status_code, 400)

    def test_an_answer_nobody_offered_is_refused_rather_than_read_as_no(self):
        """`_yes` reads anything it does not recognise as a no, silently — so
        an unoffered value decided a funding stream by falling through a
        comparison and looked exactly like answering no."""
        response = self.put({**SCREENING_YES, 'receives_sfa': 'maybe'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('receives_sfa', response.json()['answers'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.eligible_streams, ['psssp', 'dggr'])

    def test_the_third_choice_on_the_one_question_that_has_one_is_accepted(self):
        """`lives_in_nwt` offers 'moving'. Validating against yes/no alone
        would refuse an answer the office's own question offers."""
        self.assertEqual(
            self.put({**SCREENING_YES, 'lives_in_nwt': 'moving'}).status_code, 200)

    def test_an_answer_that_is_not_a_string_is_refused(self):
        for value in (True, 5, ['yes'], {'yes': True}, None):
            with self.subTest(value=value):
                response = self.client.put(
                    '/api/me/eligibility/',
                    {'answers': {**SCREENING_YES, 'receives_sfa': value}},
                    format='json')
                self.assertEqual(response.status_code, 400, repr(value))

    def test_answers_that_are_not_a_mapping_are_refused(self):
        for payload in ({'answers': 'yes'}, {'answers': ['yes']}, {}):
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.put('/api/me/eligibility/', payload,
                                    format='json').status_code,
                    400, str(payload))

    def test_unknown_keys_are_dropped_rather_than_stored(self):
        self.put({**SCREENING_YES, 'is_secretly_eligible': 'yes'})
        self.student.refresh_from_db()
        self.assertNotIn('is_secretly_eligible', self.student.eligibility_answers)

    def test_becoming_ineligible_is_recorded_and_explained(self):
        """A student who has started receiving SFA and is not a beneficiary
        qualifies for nothing. Refusing to record that would leave the portal
        funding them under a stream they have told us they no longer hold."""
        response = self.put({
            **SCREENING_YES, 'deline_beneficiary': 'no', 'receives_sfa': 'yes',
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body['outcome']['eligible'])
        self.assertIn('Student Financial Assistance', body['outcome']['message'])
        self.assertEqual(body['streams'], [])
        self.student.refresh_from_db()
        self.assertEqual(self.student.eligible_streams, [])

    def test_an_account_with_no_streams_cannot_file_an_application(self):
        """The consequence, asserted rather than assumed: the submission path
        answers 409 with the office's contact message instead of pricing
        something under a stream nobody holds."""
        from funding.test_fixtures import admission_answers

        self.put({**SCREENING_YES, 'deline_beneficiary': 'no',
                  'receives_sfa': 'yes'})
        response = self.client.post('/api/applications/', {
            'type': ApplicationType.ADMISSION,
            'answers': admission_answers(),
        }, format='json')

        self.assertEqual(response.status_code, 409)
        self.assertIn('does not currently qualify', response.json()['detail'])

    def test_every_change_is_audited(self):
        """Six answers that decide what a person is paid, edited by the person
        being paid."""
        self.put({**SCREENING_YES, 'receives_sfa': 'yes'})

        entry = AuditEntry.objects.filter(
            action='account.screening_updated').latest('id')
        self.assertEqual(entry.actor_id, self.student.pk)
        self.assertIn('receives_sfa', entry.detail)
        self.assertIn('dggr', entry.detail)

    def test_an_unchanged_screening_still_records_who_looked(self):
        self.put(SCREENING_YES)
        entry = AuditEntry.objects.filter(
            action='account.screening_updated').latest('id')
        self.assertIn('nothing', entry.detail)

    def test_staff_cannot_write_a_screening(self):
        client = signed_in(make_user(role=Role.ADMIN))
        self.assertEqual(self.put(SCREENING_YES, client=client).status_code, 403)


# ── Enrolment ────────────────────────────────────────────────────────────────


class EnrolmentProfileTests(TestCase):
    def setUp(self):
        self.student = make_user()
        self.client = signed_in(self.student)

    def test_it_opens_empty_rather_than_missing(self):
        body = self.client.get('/api/me/enrolment/').json()
        self.assertEqual(body['institution_name'], '')
        self.assertIsNone(body['program_start'])

    def test_reading_it_does_not_write_a_row(self):
        """`GET /api/form-prefill/` is called on every form open. Reading a
        profile through prefill must not create one."""
        prefill.for_schema(self.student, get_schema('admission'))
        self.assertFalse(EnrolmentProfile.objects.filter(user=self.student).exists())

    def test_a_student_can_save_where_they_study(self):
        response = self.client.put('/api/me/enrolment/', {
            'institution_name': 'Aurora College',
            'program': 'Nursing',
            'course_load': 'full_time',
            'credential_level': 'degree',
            'registrar_email': 'registrar@aurora.test',
            'student_number': 'A-4471',
            'program_start': '2026-09-01',
            'program_end': '2030-06-30',
            'dependent_count': 2,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        profile = EnrolmentProfile.objects.get(user=self.student)
        self.assertEqual(profile.institution_name, 'Aurora College')
        self.assertEqual(profile.dependent_count, 2)

    def test_a_field_left_out_is_left_alone(self):
        """The screen saves one section at a time. A strict PUT would need the
        client to send back every field it is not editing, which is how a value
        gets blanked by a form that never showed it."""
        self.client.put('/api/me/enrolment/',
                        {'institution_name': 'Aurora', 'program': 'Nursing'},
                        format='json')
        self.client.put('/api/me/enrolment/', {'program': 'Carpentry'},
                        format='json')

        profile = EnrolmentProfile.objects.get(user=self.student)
        self.assertEqual(profile.institution_name, 'Aurora')
        self.assertEqual(profile.program, 'Carpentry')

    def test_a_field_sent_empty_is_cleared(self):
        self.client.put('/api/me/enrolment/', {'student_number': 'A-1'},
                        format='json')
        self.client.put('/api/me/enrolment/', {'student_number': ''},
                        format='json')

        self.assertEqual(
            EnrolmentProfile.objects.get(user=self.student).student_number, '')

    def test_an_empty_box_of_any_kind_is_a_box_nobody_filled_in(self):
        """The screen posts every field in its section.

        So a student who has never entered their programme dates posts
        `program_start: ''`, and a DRF DateField reads that as a malformed date
        — three errors against boxes they never typed in, and a section that
        could not be saved at all until they invented dates. Exactly the fault
        a required SIN caused on every edit of every form that asks for one.

        Cleared with a text field only, this passed: a CharField takes '' and
        says nothing. Which is why this asserts across every field the section
        posts rather than against one of them.
        """
        response = self.client.put('/api/me/enrolment/', {
            field: '' for field in EnrolmentProfileSerializer().fields
            if field != 'updated_at'
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        profile = EnrolmentProfile.objects.get(user=self.student)
        self.assertIsNone(profile.program_start)
        self.assertIsNone(profile.dependent_count)
        self.assertEqual(profile.institution_name, '')

    def test_a_saved_profile_can_be_saved_again_unchanged(self):
        """What the screen does on a second Save: post back what it was given.

        A round trip that only works the first time is a screen that breaks
        as soon as somebody presses the button twice.
        """
        self.client.put('/api/me/enrolment/', {
            'institution_name': 'Aurora College', 'program_start': '2026-09-01',
            'dependent_count': 0, 'course_load': 'full_time',
        }, format='json')

        stored = self.client.get('/api/me/enrolment/').json()
        stored.pop('updated_at')
        again = self.client.put('/api/me/enrolment/', stored, format='json')

        self.assertEqual(again.status_code, 200, again.data)
        self.assertEqual(again.json()['institution_name'], 'Aurora College')
        self.assertEqual(again.json()['program_start'], '2026-09-01')

    def test_every_column_on_the_profile_is_optional(self):
        """What actually makes "omitted means unchanged" true.

        The view sets `partial=True`, but that is not what holds the line —
        every column being optional is. Removing `partial=True` changes nothing
        today, and this is the test that will notice the day somebody makes one
        of these required and quietly turns every partial save into a refusal.
        """
        required = [
            field.name for field in EnrolmentProfile._meta.get_fields()
            if getattr(field, 'concrete', False)
            and field.name not in ('id', 'user', 'updated_at')
            and not (field.blank or field.null)
        ]
        self.assertEqual(required, [])

    def test_a_choice_the_forms_do_not_recognise_is_refused(self):
        """A profile holding `course_load='fulltime'` pre-fills a form with a
        value the schema refuses, and the student meets a validation error on an
        answer they never typed."""
        response = self.client.put('/api/me/enrolment/',
                                   {'course_load': 'fulltime'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('full_time', str(response.json()['course_load']))

    def test_every_profile_choice_matches_its_schema_field(self):
        """Asserted against the schema rather than against a list written here,
        so a choice added to a form tomorrow does not silently become one the
        profile refuses."""
        schema = get_schema('admission')
        for column, key in (('course_load', 'course_load'),
                            ('credential_level', 'credential_level'),
                            ('learning_style', 'learning_style')):
            field = next(f for f in schema.fields if f.key == key)
            for choice in field.choices:
                response = self.client.put('/api/me/enrolment/',
                                           {column: choice.value}, format='json')
                self.assertEqual(response.status_code, 200,
                                 f'{column}={choice.value}: {response.data}')

    def test_a_programme_cannot_end_before_it_starts(self):
        response = self.client.put('/api/me/enrolment/', {
            'program_start': '2026-09-01', 'program_end': '2026-01-01',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_the_dates_are_checked_against_what_is_stored_not_only_what_arrives(self):
        """A partial update is validated against the profile it will produce.
        Checking only the incoming pair would let a second request move the
        start past a stored end."""
        self.client.put('/api/me/enrolment/', {
            'program_start': '2026-09-01', 'program_end': '2027-06-30',
        }, format='json')

        response = self.client.put('/api/me/enrolment/',
                                   {'program_start': '2028-01-01'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_a_bad_email_is_refused(self):
        response = self.client.put('/api/me/enrolment/',
                                   {'registrar_email': 'not-an-address'},
                                   format='json')
        self.assertEqual(response.status_code, 400)

    def test_one_profile_per_student(self):
        self.client.put('/api/me/enrolment/', {'program': 'A'}, format='json')
        self.client.put('/api/me/enrolment/', {'program': 'B'}, format='json')
        self.assertEqual(
            EnrolmentProfile.objects.filter(user=self.student).count(), 1)

    def test_a_profile_is_nobody_else_s(self):
        other = make_user()
        signed_in(other).put('/api/me/enrolment/',
                             {'institution_name': 'Somewhere else'}, format='json')

        self.client.put('/api/me/enrolment/', {'institution_name': 'Aurora'},
                        format='json')
        self.assertEqual(
            EnrolmentProfile.objects.get(user=other).institution_name,
            'Somewhere else')

    def test_staff_have_no_enrolment_profile(self):
        client = signed_in(make_user(role=Role.SUPPORT_WORKER))
        self.assertEqual(client.get('/api/me/enrolment/').status_code, 403)
        self.assertEqual(
            client.put('/api/me/enrolment/', {'program': 'x'}, format='json').status_code,
            403)


# ── Banking ──────────────────────────────────────────────────────────────────


BANK = {
    'account_holder': 'Sara Student',
    'transit_number': '12345',
    'institution_number': '001',
    'account_number': '9876543210',
}


class BankingProfileTests(TestCase):
    def setUp(self):
        self.student = make_user()
        self.client = signed_in(self.student)

    def test_nothing_on_file_reads_as_nothing(self):
        """An answer, not a transport error. A DRF response whose body is
        `None` is 200 with no content type, which a client cannot parse."""
        response = self.client.get('/api/me/banking/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['account'])

    def test_a_student_can_say_where_they_are_paid(self):
        response = self.client.put('/api/me/banking/', BANK, format='json')

        self.assertEqual(response.status_code, 200)
        account = BankAccount.objects.get(user=self.student, is_current=True)
        self.assertEqual(account.account_number, '9876543210')

    def test_the_number_never_comes_back(self):
        """The one value in this system that is written and never read back to a
        screen — including to the screen that wrote it."""
        body = self.client.put('/api/me/banking/', BANK, format='json').json()

        self.assertEqual(body['account']['account_number'], '****3210')
        self.assertNotIn('9876543210', str(body))
        self.assertNotIn('9876543210', str(self.client.get('/api/me/banking/').json()))
        self.assertNotIn('9876543210', str(self.client.get('/api/me/').json()))

    def test_changing_it_retires_the_previous_account(self):
        """A payment already sent stays traceable to the details in force when
        it went out, so the old row is retired rather than edited."""
        self.client.put('/api/me/banking/', BANK, format='json')
        self.client.put('/api/me/banking/',
                        {**BANK, 'account_number': '1111222233'}, format='json')

        accounts = BankAccount.objects.filter(user=self.student).order_by('id')
        self.assertEqual(accounts.count(), 2)
        self.assertFalse(accounts[0].is_current)
        self.assertIsNotNone(accounts[0].retired_at)
        self.assertTrue(accounts[1].is_current)

    def test_saving_the_same_details_does_not_churn_the_record(self):
        self.client.put('/api/me/banking/', BANK, format='json')
        self.client.put('/api/me/banking/', BANK, format='json')
        self.assertEqual(BankAccount.objects.filter(user=self.student).count(), 1)

    def test_a_missing_field_is_refused(self):
        """Half a bank account looks like an account on file and cannot be
        paid, which is worse than none."""
        response = self.client.put(
            '/api/me/banking/', {k: v for k, v in BANK.items()
                                 if k != 'account_number'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('account_number', response.json())
        self.assertFalse(BankAccount.objects.filter(user=self.student).exists())

    def test_the_shapes_the_form_promises_are_enforced(self):
        for field, bad in (('transit_number', '1234'),
                           ('institution_number', '01'),
                           ('account_number', '123'),
                           ('transit_number', 'ABCDE')):
            with self.subTest(field=field, value=bad):
                response = self.client.put('/api/me/banking/',
                                           {**BANK, field: bad}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_the_profile_and_the_forms_write_the_same_record(self):
        """One account, one history. Two paths writing two ideas of where
        somebody is paid is how the payment run comes to hold the wrong one."""
        from funding.services import banking

        self.client.put('/api/me/banking/', BANK, format='json')
        application = Application.objects.create(
            student=self.student, type=ApplicationType.TRAVEL,
            stream=FundingStream.DGGR, schema_slug='travel', answers={})
        banking.record(application, {**BANK, 'account_number': '5555666677'})

        self.assertEqual(BankAccount.objects.filter(
            user=self.student, is_current=True).count(), 1)
        self.assertEqual(
            BankAccount.objects.get(user=self.student, is_current=True).account_number,
            '5555666677')

    def test_it_is_audited(self):
        self.client.put('/api/me/banking/', BANK, format='json')
        entry = AuditEntry.objects.filter(
            action='account.banking_updated').latest('id')
        self.assertEqual(entry.actor_id, self.student.pk)
        self.assertIn('****3210', entry.detail)
        self.assertNotIn('9876543210', entry.detail)

    def test_staff_have_no_bank_account_here(self):
        client = signed_in(make_user(role=Role.FINANCE))
        self.assertEqual(client.get('/api/me/banking/').status_code, 403)
        self.assertEqual(
            client.put('/api/me/banking/', BANK, format='json').status_code, 403)


# ── What the profile is for ──────────────────────────────────────────────────


class PrefillFromProfileTests(TestCase):
    """The reason any of this exists: the next form opens filled in."""

    def setUp(self):
        self.student = make_user(city='Délı̨nę', phone='8675550100')
        self.profile = EnrolmentProfile.objects.create(
            user=self.student, institution_name='Aurora College',
            program='Nursing', course_load='full_time', credential_level='degree',
            student_number='A-4471', registrar_email='registrar@aurora.test',
            program_start='2026-09-01', program_end='2030-06-30',
            dependent_count=0,
        )

    def prefill(self, slug='admission'):
        return prefill.for_schema(self.student, get_schema(slug))

    def test_the_profile_fills_the_form(self):
        answers = self.prefill()
        self.assertEqual(answers['institution_name'], 'Aurora College')
        self.assertEqual(answers['program'], 'Nursing')
        self.assertEqual(answers['registrar_email'], 'registrar@aurora.test')

    def test_identity_still_comes_from_the_account(self):
        answers = self.prefill()
        self.assertEqual(answers['first_name'], self.student.first_name)
        self.assertEqual(answers['city'], 'Délı̨nę')

    def test_no_dependants_is_an_answer(self):
        """`if value` would drop a zero — the same fault as the frontend's
        `!answers[key]` reading "No" as unanswered."""
        self.assertEqual(self.prefill()['dependent_count'], 0)

    def test_the_profile_beats_an_earlier_application(self):
        """What a student maintains on purpose beats what is inferred from a
        form they filled in last February."""
        Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            answers={'institution_name': 'Somewhere Old', 'program': 'Old Program'},
        )
        answers = self.prefill()
        self.assertEqual(answers['institution_name'], 'Aurora College')

    def test_an_earlier_application_still_fills_what_the_profile_does_not(self):
        """Nobody is made worse off by the profile existing. A student who has
        applied before and never opened the screen keeps what they had."""
        self.profile.institution_name = ''
        self.profile.save()
        Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            submitted_at='2026-02-01T00:00:00Z',
            answers={'institution_name': 'Somewhere Old'},
        )
        self.assertEqual(self.prefill()['institution_name'], 'Somewhere Old')

    def test_nothing_is_filled_in_that_the_schema_does_not_ask(self):
        """A prefill that invents a key makes the form unsubmittable: an unknown
        answer is refused at validation."""
        for slug in ('admission', 'travel', 'continuing_funding',
                     'graduation_bursary', 'appeal', 'emergency_relief',
                     'hardship_bursary', 'academic_scholarship', 'practicum'):
            with self.subTest(slug=slug):
                schema = get_schema(slug)
                unknown = set(prefill.for_schema(self.student, schema)) - set(schema.keys)
                self.assertEqual(unknown, set())

    def test_a_per_term_fact_is_never_pre_filled(self):
        """The semester, its dates, the tuition quoted and this term's SFA
        answer are the student's to state each time. Filling them in is
        answering on their behalf."""
        answers = self.prefill()
        for key in ('semester', 'semester_start', 'semester_end',
                    'tuition_requested', 'receives_sfa', 'signature'):
            self.assertNotIn(key, answers)

    def test_the_prefill_endpoint_returns_it(self):
        body = signed_in(self.student).get('/api/form-prefill/admission/').json()
        self.assertEqual(body['answers']['institution_name'], 'Aurora College')

    def test_a_pre_filled_date_is_one_the_form_will_take_back(self):
        """The profile holds a `date`; the schema validates a string.

        A pre-fill that hands the form a value its own validator refuses makes
        the form unsubmittable on a box the student never touched — and this is
        the shape that broke when a list first reached `jsonable`. Asserted
        through the endpoint and then through validation, because the conversion
        happens on the way out.
        """
        body = signed_in(self.student).get('/api/form-prefill/admission/').json()
        self.assertEqual(body['answers']['program_start'], '2026-09-01')

        schema = get_schema('admission')
        cleaned = schema.clean({
            **admission_fixture(),
            'program_start': body['answers']['program_start'],
            'program_end': body['answers']['program_end'],
        })
        self.assertEqual(str(cleaned['program_start']), '2026-09-01')

    def test_editing_the_profile_does_not_reach_back_into_a_filed_application(self):
        """An application's answers are copied at submission, not referenced.

        This is the identity-by-reference question the whole rebuild turns on:
        if a filed application read the profile, correcting a spelling in
        August would rewrite what a decision made in September was defended by.
        """
        client = signed_in(self.student)
        filed = client.post('/api/applications/', {
            'type': ApplicationType.ADMISSION,
            'answers': admission_fixture(),
        }, format='json')
        self.assertEqual(filed.status_code, 201, filed.data)

        self.profile.institution_name = 'Somewhere Entirely Else'
        self.profile.course_load = 'part_time'
        self.profile.save()

        application = Application.objects.get(pk=filed.json()['id'])
        self.assertEqual(application.answers['institution_name'],
                         admission_fixture()['institution_name'])
        self.assertEqual(application.answers['course_load'], 'full_time')

    def test_re_screening_does_not_move_an_application_already_filed(self):
        """`Application.stream` is decided once, at submission.

        A student who starts receiving SFA in November has not retroactively
        been funded from a different pot in September, and the decision made
        then was priced against the stream stored then.
        """
        client = signed_in(self.student)
        filed = client.post('/api/applications/', {
            'type': ApplicationType.ADMISSION,
            'answers': admission_fixture(),
        }, format='json')
        application = Application.objects.get(pk=filed.json()['id'])
        self.assertEqual(application.stream, FundingStream.PSSSP)

        client.put('/api/me/eligibility/',
                   {'answers': {**SCREENING_YES, 'receives_sfa': 'yes'}},
                   format='json')

        application.refresh_from_db()
        self.assertEqual(application.stream, FundingStream.PSSSP)

    def test_every_profile_column_is_asked_by_some_schema(self):
        """A profile column no form asks for is a box a student fills in for
        nothing."""
        from funding.schemas import all_schemas

        asked = set()
        for schema in all_schemas():
            asked |= set(schema.keys)
        self.assertEqual([key for key in prefill.FROM_PROFILE if key not in asked], [])


class RegistrarEmailFromProfileTests(TestCase):
    """The bug the profile closes.

    A renewal does not ask for a registrar's address; it is carried from the
    student's last application. Somebody whose admission was on paper has
    nothing to carry, so the request was skipped in silence — tuition could
    never be confirmed and the application could never be approved, by anybody.
    """

    def setUp(self):
        self.student = make_user()

    def application(self, **answers):
        return Application.objects.create(
            student=self.student, type=ApplicationType.CONTINUING_FUNDING,
            stream=FundingStream.PSSSP, schema_slug='continuing_funding',
            answers=answers)

    def test_the_profile_supplies_an_address_no_earlier_application_holds(self):
        from funding.services import workflow

        EnrolmentProfile.objects.create(
            user=self.student, registrar_email='registrar@aurora.test')
        self.assertEqual(
            workflow.registrar_email_for(self.application()),
            'registrar@aurora.test')

    def test_the_application_s_own_answer_still_wins(self):
        from funding.services import workflow

        EnrolmentProfile.objects.create(
            user=self.student, registrar_email='profile@aurora.test')
        self.assertEqual(
            workflow.registrar_email_for(
                self.application(registrar_email='typed@aurora.test')),
            'typed@aurora.test')

    def test_with_neither_it_is_still_empty(self):
        from funding.services import workflow

        self.assertEqual(workflow.registrar_email_for(self.application()), '')


class ProfileNeverPricesTests(TestCase):
    """The architectural guard.

    The previous system held `institution`, `program` and `enrollment_status` on
    the user, and award calculation fell back to them whenever an answer was
    missing — so last year's facts priced this year's application and nothing on
    any screen said so. The profile is allowed to exist only because exactly one
    module reads it.
    """

    def setUp(self):
        from funding.test_rules import seed_rates

        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.student = make_user()

    def test_changing_the_profile_does_not_change_what_is_awarded(self):
        from funding.services.decisions import preview
        from funding.test_fixtures import confirm_enrolment

        application = Application.objects.create(
            student=self.student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            answers={'course_load': 'full_time', 'semester_start': '2026-09-01',
                     'semester_end': '2026-12-31', 'confirmed_tuition': '6000'})
        confirm_enrolment(application)
        before = preview(application).total

        EnrolmentProfile.objects.create(
            user=self.student, course_load='part_time', dependent_count=9,
            program='Something Else', institution_name='Elsewhere')

        application.refresh_from_db()
        self.assertEqual(preview(application).total, before)

    def test_only_prefill_reads_the_profile(self):
        """Read from the source, because a test that priced one application
        proves one application. Anything under `funding/` that learns to read
        this table is the old fallback returning."""
        root = Path(__file__).resolve().parent.parent
        allowed = {
            root / 'funding' / 'services' / 'prefill.py',
            # The registrar's address is not money: it decides who is *asked* to
            # confirm an enrolment, and the figure they return is still the only
            # thing tuition is funded against.
            root / 'funding' / 'services' / 'workflow.py',
        }

        offenders = []
        for path in (root / 'funding').rglob('*.py'):
            if path in allowed or 'migrations' in path.parts or path.name.startswith('test_'):
                continue
            text = path.read_text(encoding='utf-8')
            if 'EnrolmentProfile' in text or 'enrolment_profile' in text:
                offenders.append(str(path.relative_to(root)))

        self.assertEqual(offenders, [], 'These read the enrolment profile: '
                                        + ', '.join(offenders))
