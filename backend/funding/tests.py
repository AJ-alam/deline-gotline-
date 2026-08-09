"""Tests for the consolidated funding domain model."""

import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from funding.models import (
    Application, ApplicationDeadline, ApplicationEvent, ApplicationStatus,
    ApplicationType, Award, FundingStream, PolicySetting,
)

User = get_user_model()


_counter = itertools.count(1)


def make_student(email=None):
    email = email or f'student{next(_counter)}@test.com'
    return User.objects.create_user(
        email=email, password='pw123456', full_name='Test Student', role='student',
    )


def make_application(student=None, **kwargs):
    defaults = dict(
        type=ApplicationType.ADMISSION,
        stream=FundingStream.PSSSP,
        schema_slug='admission',
        answers={'course_load': 'full_time', 'institution_name': 'Aurora College'},
    )
    defaults.update(kwargs)
    return Application.objects.create(student=student or make_student(), **defaults)


class ApplicationModelTests(TestCase):

    def test_one_model_covers_every_form_variant(self):
        """Nine Form* models collapse into one typed Application."""
        student = make_student()
        for app_type in ApplicationType:
            Application.objects.create(
                student=student, type=app_type, stream=FundingStream.DGGR,
                schema_slug='x', answers={},
            )
        self.assertEqual(Application.objects.count(), len(ApplicationType))

    def test_funding_stream_is_stored_not_inferred_from_a_title(self):
        app = make_application(stream=FundingStream.UCEPP)
        # Was: Q(form__title__icontains='UCEPP') — an unindexable LIKE scan over
        # a human-editable string.
        self.assertEqual(
            Application.objects.filter(stream=FundingStream.UCEPP).count(), 1,
        )
        self.assertEqual(app.get_stream_display(), 'C-DFN UCEPP')

    def test_answers_are_keyed_by_stable_schema_keys(self):
        app = make_application()
        self.assertEqual(app.answers['course_load'], 'full_time')

    def test_open_states_exclude_decided_applications(self):
        self.assertTrue(make_application(status=ApplicationStatus.UNDER_REVIEW).is_open)
        self.assertFalse(make_application(status=ApplicationStatus.APPROVED).is_open)
        self.assertFalse(make_application(status=ApplicationStatus.DECLINED).is_open)

    def test_default_ordering_is_newest_first(self):
        student = make_student()
        older = make_application(student, submitted_at=timezone.now() - timedelta(days=5))
        newer = make_application(student)
        self.assertEqual(list(Application.objects.all()), [newer, older])


class ApplicationEventTests(TestCase):
    """Replaces sixteen timestamp/actor columns that could contradict `status`."""

    def test_workflow_history_is_queryable_in_order(self):
        app = make_application()
        staff = User.objects.create_user(
            email='ssw@test.com', password='pw123456', full_name='SSW', role='ssw',
        )
        for action in (
            ApplicationEvent.Action.SUBMITTED,
            ApplicationEvent.Action.REVIEWED,
            ApplicationEvent.Action.FORWARDED,
            ApplicationEvent.Action.APPROVED,
        ):
            ApplicationEvent.objects.create(application=app, action=action, actor=staff)

        self.assertEqual(
            [e.action for e in app.events.all()],
            ['submitted', 'reviewed', 'forwarded', 'approved'],
        )

    def test_events_survive_actor_deletion(self):
        app = make_application()
        staff = User.objects.create_user(
            email='gone@test.com', password='pw123456', full_name='Gone', role='ssw',
        )
        ApplicationEvent.objects.create(
            application=app, action=ApplicationEvent.Action.APPROVED, actor=staff,
        )
        staff.delete()
        event = app.events.get()
        self.assertIsNone(event.actor)      # audit trail must not vanish with the user
        self.assertEqual(event.action, 'approved')


class AwardTests(TestCase):

    def test_awards_have_exactly_one_parent(self):
        """Payment carried FKs to both Application and FormSubmission."""
        app = make_application()
        Award.objects.create(
            application=app, category=Award.Category.TUITION, amount=Decimal('7000.00'),
        )
        Award.objects.create(
            application=app, category=Award.Category.LIVING, amount=Decimal('1800.00'),
        )
        self.assertEqual(app.awards.count(), 2)
        self.assertEqual(
            sum(a.amount for a in app.awards.all()), Decimal('8800.00'),
        )

    def test_reference_numbers_are_unique(self):
        app = make_application()
        Award.objects.create(
            application=app, category=Award.Category.TUITION,
            amount=Decimal('100'), reference='REF-1',
        )
        with self.assertRaises(IntegrityError):
            Award.objects.create(
                application=app, category=Award.Category.BOOKS,
                amount=Decimal('50'), reference='REF-1',
            )


class PolicySettingTests(TestCase):

    def test_a_setting_cannot_be_duplicated(self):
        """The old table had no uniqueness guard, so .get() could raise on dupes."""
        PolicySetting.objects.create(
            section='psssp_tuition', key='max_per_semester',
            label='Max per semester', value=Decimal('7000'),
        )
        with self.assertRaises(IntegrityError):
            PolicySetting.objects.create(
                section='psssp_tuition', key='max_per_semester',
                label='Duplicate', value=Decimal('9999'),
            )


class ApplicationDeadlineTests(TestCase):

    def test_one_deadline_per_stream_year_and_semester(self):
        ApplicationDeadline.objects.create(
            stream=FundingStream.PSSSP, academic_year='2026-27',
            semester='fall', closes_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            ApplicationDeadline.objects.create(
                stream=FundingStream.PSSSP, academic_year='2026-27',
                semester='fall', closes_at=timezone.now(),
            )
