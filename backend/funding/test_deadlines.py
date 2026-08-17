"""Submission cut-offs.

ApplicationDeadline was a table with tests and no reader: nothing wrote
`submitted_after_deadline`, so the staff dashboard's "submitted late" count
could only ever be zero. These cover the reader — that lateness is decided
against the deadline in force at submission, that it is decided once, and that
an office which has set no deadline marks nobody late.
"""

from datetime import datetime, timezone as utc

from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationDeadline, ApplicationEvent, ApplicationStatus,
    FundingStream,
)
from funding.services import deadlines, workflow


def make_student(email='student@test.com'):
    return User.objects.create_user(email, 'pw12345678', first_name='Test',
                                    last_name='Person', role=Role.STUDENT, is_deline_beneficiary=True, is_indian_act_registered=True)


def make_application(student, submitted_at, **answers):
    return Application.objects.create(
        student=student, type='admission', stream=FundingStream.PSSSP,
        schema_slug='admission', submitted_at=submitted_at,
        answers={'semester': 'fall', 'semester_start': '2026-09-01', **answers},
    )


def deadline(closes_at, stream=FundingStream.PSSSP, semester='fall',
             academic_year='2026-2027'):
    return ApplicationDeadline.objects.create(
        stream=stream, academic_year=academic_year, semester=semester,
        closes_at=closes_at)


AUGUST_FIRST = datetime(2026, 8, 1, 23, 59, tzinfo=utc.utc)


class AcademicYearTests(TestCase):
    """August is the hinge: earlier months belong to the year already running."""

    def test_a_september_start_belongs_to_the_year_beginning(self):
        self.assertEqual(
            deadlines.academic_year_of(datetime(2026, 9, 1).date()), '2026-2027')

    def test_a_january_start_belongs_to_the_year_already_running(self):
        self.assertEqual(
            deadlines.academic_year_of(datetime(2027, 1, 5).date()), '2026-2027')

    def test_august_itself_starts_the_new_year(self):
        self.assertEqual(
            deadlines.academic_year_of(datetime(2026, 8, 1).date()), '2026-2027')

    def test_no_date_yields_no_year(self):
        self.assertEqual(deadlines.academic_year_of(None), '')


class StampTests(TestCase):

    def setUp(self):
        self.student = make_student()

    def test_an_application_filed_before_the_cut_off_is_not_late(self):
        deadline(AUGUST_FIRST)
        application = make_application(
            self.student, datetime(2026, 7, 20, 12, 0, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)

    def test_an_application_filed_after_the_cut_off_is_late(self):
        deadline(AUGUST_FIRST)
        application = make_application(
            self.student, datetime(2026, 8, 2, 9, 0, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertTrue(application.submitted_after_deadline)

    def test_the_term_is_recorded_on_the_application(self):
        """Both columns existed and nothing ever filled them in."""
        deadline(AUGUST_FIRST)
        application = make_application(
            self.student, datetime(2026, 7, 20, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertEqual(application.semester, 'fall')
        self.assertEqual(application.academic_year, '2026-2027')

    def test_the_callers_instance_matches_what_was_written(self):
        """A stale in-memory copy is how the old status/timestamp pairs drifted."""
        deadline(AUGUST_FIRST)
        application = make_application(
            self.student, datetime(2026, 8, 2, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        self.assertTrue(application.submitted_after_deadline)
        self.assertEqual(application.semester, 'fall')

    def test_no_deadline_set_means_nobody_is_late(self):
        """An office that set no date has imposed no cut-off."""
        application = make_application(
            self.student, datetime(2030, 1, 1, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)

    def test_a_deadline_for_another_stream_does_not_apply(self):
        deadline(AUGUST_FIRST, stream=FundingStream.UCEPP)
        application = make_application(
            self.student, datetime(2026, 8, 2, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)

    def test_a_deadline_for_another_term_does_not_apply(self):
        deadline(AUGUST_FIRST, semester='winter')
        application = make_application(
            self.student, datetime(2026, 8, 2, tzinfo=utc.utc))

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)

    def test_a_type_with_no_semester_is_never_late(self):
        """A graduation bursary is not filed against a term."""
        deadline(AUGUST_FIRST)
        application = Application.objects.create(
            student=self.student, type='graduation_bursary',
            stream=FundingStream.DGGR, schema_slug='graduation_bursary',
            submitted_at=datetime(2026, 8, 2, tzinfo=utc.utc),
            answers={'credential': 'diploma'})

        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)
        self.assertEqual(application.semester, '')

    def test_moving_the_deadline_later_does_not_make_a_filed_application_late(self):
        """Lateness is decided once. An appeal argues against the date that was
        in force, not whatever the office has set since."""
        governing = deadline(AUGUST_FIRST)
        application = make_application(
            self.student, datetime(2026, 7, 20, tzinfo=utc.utc))
        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        governing.closes_at = datetime(2026, 7, 1, tzinfo=utc.utc)
        governing.save(update_fields=['closes_at'])

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)

    def test_a_later_transition_does_not_restamp(self):
        deadline(AUGUST_FIRST)
        application = make_application(
            self.student, datetime(2026, 7, 20, tzinfo=utc.utc))
        workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        ApplicationDeadline.objects.update(
            closes_at=datetime(2026, 7, 1, tzinfo=utc.utc))
        workflow.record(application, ApplicationEvent.Action.REVIEWED,
                        actor=make_student('worker@test.com'))

        application.refresh_from_db()
        self.assertFalse(application.submitted_after_deadline)
        self.assertEqual(application.status, ApplicationStatus.UNDER_REVIEW)


class UpcomingTests(TestCase):

    def test_only_cut_offs_still_ahead_are_returned_soonest_first(self):
        now = timezone.now()
        past = deadline(now - timezone.timedelta(days=1), semester='spring')
        soon = deadline(now + timezone.timedelta(days=10), semester='fall')
        later = deadline(now + timezone.timedelta(days=40), semester='winter')

        found = deadlines.upcoming(when=now)

        self.assertEqual([d.pk for d in found], [soon.pk, later.pk])
        self.assertNotIn(past.pk, [d.pk for d in found])

    def test_none_set_returns_nothing_rather_than_inventing_dates(self):
        self.assertEqual(deadlines.upcoming(), [])

    def test_one_date_set_across_every_stream_is_one_deadline(self):
        """The office sets the same date for all three streams. Returned row by
        row, that is the same deadline told to a student three times."""
        now = timezone.now()
        closes = now + timezone.timedelta(days=10)
        for stream in FundingStream.values:
            deadline(closes, stream=stream, semester='fall')

        found = deadlines.upcoming(when=now)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].semester, 'fall')

    def test_the_limit_counts_terms_not_rows(self):
        now = timezone.now()
        for index, semester in enumerate(('fall', 'winter', 'spring', 'summer')):
            for stream in FundingStream.values:
                deadline(now + timezone.timedelta(days=10 * (index + 1)),
                         stream=stream, semester=semester,
                         academic_year=f'202{index}-202{index + 1}')

        found = deadlines.upcoming(when=now, limit=3)

        self.assertEqual([d.semester for d in found], ['fall', 'winter', 'spring'])
