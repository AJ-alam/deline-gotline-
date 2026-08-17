"""The appeal request.

An appeal argues with a decision that has already been made, which shapes three
things that are not obvious from the form:

  * it is never late. Filing after something has gone wrong is what it is for,
    and it only became possible to mark one late when the form started asking
    for a semester — any application carrying one gets a term, and a term with
    a deadline behind it gets a flag;
  * its evidence is plural. An appeal is argued from a transcript *and* a letter
    *and* a medical note, and a single-file question meant the rest never
    reached the people deciding it;
  * it pays nothing, so it must survive the parts of the workflow that assume
    money — pricing, the payment run — without falling into either.
"""

from datetime import timedelta

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationDeadline, ApplicationEvent, ApplicationStatus,
    ApplicationType, FundingStream,
)
from funding.schemas import FieldType, ValidationError, get_schema
from funding.services import finance, workflow
from funding.test_fixtures import answers_for

SCHEMA = get_schema('appeal')


def appeal(**overrides) -> dict:
    defaults = dict(
        full_name='Majid Khan',
        student_number='A-99213',
        institution_name='Aurora College',
        semester='fall',
        academic_year='2026-2027',
        appeal_reason='The living allowance was priced for part-time study; I was full-time.',
        signature='Majid Khan',
    )
    defaults.update(overrides)
    return answers_for('appeal', **defaults)


class FormContentTests(SimpleTestCase):
    """The questions the office's form asks."""

    def test_it_asks_exactly_what_the_office_asked_for(self):
        self.assertEqual(
            set(SCHEMA.keys),
            {
                'full_name', 'student_number', 'institution_name',
                'semester', 'academic_year',
                'appeal_reason', 'policy_reference',
                'doc_supporting',
                'declaration_confirmed', 'signature', 'signed_on',
            },
        )

    def test_it_falls_into_the_three_steps_the_screens_show(self):
        self.assertEqual(
            SCHEMA.sections,
            ('Student and academic context', 'Reason for appeal',
             'Supporting evidence', 'Declaration'),
        )

    def test_the_reason_is_prose_and_is_required(self):
        field = SCHEMA.field('appeal_reason')
        self.assertEqual(field.type, FieldType.LONG_TEXT)
        self.assertTrue(field.required)
        self.assertIn('what outcome you are requesting', field.help_text)

    def test_the_policy_reference_is_optional(self):
        """Most students do not know the section number, and demanding it would
        turn an appeal into a research exercise."""
        self.assertFalse(SCHEMA.field('policy_reference').required)

    def test_the_term_is_a_closed_set_and_the_year_is_asked(self):
        """The term is how the office finds the decision being argued with.

        Asserted against the renewal's own list rather than against a copy:
        an appeal about a summer term has to be able to name it, and a second
        hand-written list here is exactly the drift this arrangement exists to
        stop.
        """
        self.assertEqual(SCHEMA.field('semester').choice_values,
                         get_schema('continuing_funding').field('semester').choice_values)
        self.assertTrue(SCHEMA.field('semester').required)
        self.assertTrue(SCHEMA.field('academic_year').required)

    def test_the_declaration_is_worded_as_the_office_words_it(self):
        field = SCHEMA.field('declaration_confirmed')
        self.assertEqual(field.type, FieldType.CONFIRM)
        self.assertEqual(
            field.help_text,
            'I confirm that the information provided is accurate and complete. '
            'I understand that appeal decisions are discretionary and subject '
            'to the DGG Education Policy.',
        )

    def test_the_declaration_cannot_be_filed_refused(self):
        with self.assertRaises(ValidationError):
            SCHEMA.clean(appeal(declaration_confirmed='false'))

    def test_the_date_signed_opens_on_today(self):
        self.assertTrue(SCHEMA.field('signed_on').defaults_to_today)

    def test_no_money_is_asked_for(self):
        """An appeal asks for a decision to be revisited, not for an amount."""
        self.assertNotIn('amount_requested', SCHEMA.keys)


class EvidenceTests(SimpleTestCase):
    """Supporting evidence is plural wherever it is asked for."""

    def test_evidence_takes_more_than_one_file(self):
        self.assertEqual(SCHEMA.field('doc_supporting').type, FieldType.FILES)

    def test_every_attached_document_is_kept(self):
        cleaned = SCHEMA.clean(appeal(
            doc_supporting=['document:1', 'document:2', 'document:3']))
        self.assertEqual(cleaned['doc_supporting'],
                         ['document:1', 'document:2', 'document:3'])

    def test_an_appeal_with_no_evidence_is_still_accepted(self):
        """Not every appeal has a document behind it. A student arguing that a
        course load was recorded wrongly is arguing about the office's own
        records."""
        cleaned = SCHEMA.clean(appeal())
        self.assertNotIn('doc_supporting', cleaned)

    def test_more_documents_than_the_cap_are_refused(self):
        limit = SCHEMA.field('doc_supporting').max_items
        with self.assertRaises(ValidationError):
            SCHEMA.clean(appeal(
                doc_supporting=[f'document:{n}' for n in range(limit + 1)]))

    def test_supporting_documents_mean_the_same_thing_on_every_form(self):
        """One key, one type.

        `doc_supporting` was a single file here and a single file on emergency
        relief — the same question, answerable once, on forms where people have
        several papers. The hardship bursary used to be a third; the office's
        own screen for it asks for no documents at all, so it no longer holds
        the key rather than holding it with a different meaning.
        """
        for slug in ('appeal', 'emergency_relief'):
            with self.subTest(slug=slug):
                self.assertEqual(get_schema(slug).field('doc_supporting').type,
                                 FieldType.FILES, slug)
        self.assertNotIn('doc_supporting', get_schema('hardship_bursary').keys)


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@appeal.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


class NeverLateTests(TestCase):
    """An appeal cannot be submitted late.

    It became possible to mark one late the moment the form asked for a
    semester: `deadlines.stamp` gives any application carrying one a term, and
    a term with a deadline behind it gets a lateness flag. An appeal filed in
    December about a Fall decision would have been badged "submitted late",
    which is not a fault — it is the whole point of the form.
    """

    def setUp(self):
        self.student = make_user()
        # A deadline that closed a month ago, for the term being appealed.
        closed = timezone.now() - timedelta(days=30)
        for stream in FundingStream.values:
            ApplicationDeadline.objects.create(
                stream=stream, academic_year='2026-2027', semester='fall',
                closes_at=closed, late_allowed=True)

    def filed(self, app_type, slug, answers):
        application = Application.objects.create(
            student=self.student, type=app_type, stream=FundingStream.PSSSP,
            schema_slug=slug, status=ApplicationStatus.DRAFT, answers=answers)
        workflow.record(application, ApplicationEvent.Action.SUBMITTED, self.student)
        application.refresh_from_db()
        return application

    def test_an_appeal_filed_after_the_cut_off_is_not_late(self):
        filed = self.filed(ApplicationType.APPEAL, 'appeal',
                           {'semester': 'fall', 'semester_start': '2026-09-01'})
        self.assertFalse(filed.submitted_after_deadline)

    def test_but_it_still_records_the_term_it_argues_with(self):
        """Withholding the judgement, not the fact. The term is how staff find
        the decision the appeal is about."""
        filed = self.filed(ApplicationType.APPEAL, 'appeal',
                           {'semester': 'fall', 'semester_start': '2026-09-01'})
        self.assertEqual(filed.semester, 'fall')
        self.assertEqual(filed.academic_year, '2026-2027')

    def test_a_funding_application_past_the_same_deadline_is_still_late(self):
        """The control. Without it, the test above passes for a stamp that has
        stopped working entirely."""
        filed = self.filed(ApplicationType.CONTINUING_FUNDING, 'continuing_funding',
                           {'semester': 'fall', 'semester_start': '2026-09-01'})
        self.assertTrue(filed.submitted_after_deadline)


class ThroughTheOfficeTests(TestCase):
    """An appeal pays nothing, and must survive the parts that assume money."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def setUp(self):
        self.student = make_user(email='appellant@appeal.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@appeal.test')
        self.director = make_user(Role.DIRECTOR, 'director@appeal.test')
        self.client = APIClient()

    def file_one(self, **overrides):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            '/api/applications/',
            {'type': 'appeal', 'answers': appeal(**overrides)}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(pk=response.data['id'])

    def test_a_student_can_file_an_appeal(self):
        self.assertEqual(self.file_one().status, ApplicationStatus.SUBMITTED)

    def test_it_carries_no_enrolment_gate(self):
        """Tuition is funded against the registrar's figure, so admission and
        renewals cannot be forwarded until one arrives. An appeal asks for
        nothing to be funded, and blocking it on a registrar would strand it."""
        application = self.file_one()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.AWAITING_DECISION)

    def test_the_director_can_decide_it(self):
        application = self.file_one()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.APPROVED)

    def test_an_approved_appeal_puts_nothing_in_the_payment_run(self):
        """It grants a reconsideration, not an amount. A zero-value row in the
        payment file is a line finance has to explain."""
        application = self.file_one()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, self.worker)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, self.worker)
        workflow.record(application, ApplicationEvent.Action.APPROVED, self.director)

        ready, blocked = finance.preview()
        self.assertNotIn(application.pk, [row['award'].application_id for row in ready])
        self.assertNotIn(application.pk, [row['award'].application_id for row in blocked])

    def test_the_evidence_survives_the_round_trip_as_a_list(self):
        application = self.file_one(
            doc_supporting=['document:1', 'document:2', 'document:3'])
        self.assertEqual(application.answers['doc_supporting'],
                         ['document:1', 'document:2', 'document:3'])

    def test_a_reviewer_can_read_it_back(self):
        application = self.file_one(doc_supporting=['document:1', 'document:2'])
        self.client.force_authenticate(self.worker)
        response = self.client.get(f'/api/applications/{application.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['answers']['doc_supporting']), 2)
        self.assertIn('appeal_reason', response.data['answers'])

    def test_another_student_cannot_read_it(self):
        application = self.file_one()
        self.client.force_authenticate(make_user(email='other@appeal.test'))
        response = self.client.get(f'/api/applications/{application.pk}/')
        self.assertIn(response.status_code, (403, 404))
