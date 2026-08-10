"""What the portal tells people.

These use captureOnCommitCallbacks, because every message is queued on commit
and a plain TestCase rolls back — so without it the whole notification path
would appear to work while sending nothing at all.
"""

import itertools

from django.core import mail
from django.test import TestCase, override_settings

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType, FundingStream,
)
from funding.services import verification, workflow
from notifications.delivery import deliver_pending
from notifications.models import Notification, OutboundEmail

_counter = itertools.count(1)

ANSWERS = {
    'first_name': 'Jane', 'last_name': 'Doe',
    'institution_name': 'Aurora College', 'program': 'Nursing',
    'registrar_email': 'registrar@aurora.ca',
}


def make_application(**kwargs):
    student = User.objects.create_user(
        f'm{next(_counter)}@test.com', 'pw12345678',
        first_name='Jane', last_name='Doe',
    )
    defaults = dict(
        student=student, type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
        schema_slug='admission', answers=dict(ANSWERS),
        status=ApplicationStatus.SUBMITTED,
    )
    defaults.update(kwargs)
    return Application.objects.create(**defaults)


def make_staff(role=Role.SUPPORT_WORKER):
    return User.objects.create_user(
        f's{next(_counter)}@test.com', 'pw12345678',
        first_name='S', last_name='Taff', role=role,
    )


@override_settings(FRONTEND_URL='https://portal.example.ca')
class RegistrarLinkTests(TestCase):
    """The link the tuition path depends on."""

    def test_issuing_a_verification_queues_the_link(self):
        application = make_application()
        with self.captureOnCommitCallbacks(execute=True):
            issued = verification.issue(application, 'registrar@aurora.ca')

        queued = OutboundEmail.objects.get()
        self.assertEqual(queued.to_email, 'registrar@aurora.ca')
        self.assertIn('Jane Doe', queued.subject)
        self.assertIn(issued.token, queued.body_html)
        self.assertIn('https://portal.example.ca/enrolment/', queued.body_html)

    def test_the_email_names_the_student_and_programme(self):
        with self.captureOnCommitCallbacks(execute=True):
            verification.issue(make_application(), 'registrar@aurora.ca')

        body = OutboundEmail.objects.get().body_html
        self.assertIn('Aurora College', body)
        self.assertIn('Nursing', body)

    def test_nothing_is_queued_when_issuing_rolls_back(self):
        """A registrar must never receive a link to a request that was not saved."""
        application = make_application()
        try:
            with self.captureOnCommitCallbacks(execute=True):
                verification.issue(application, 'registrar@aurora.ca')
                raise RuntimeError('something failed after issuing')
        except RuntimeError:
            pass
        # The callback list is only executed for callbacks registered in a
        # committed block; nothing was delivered.
        self.assertEqual(mail.outbox, [])

    def test_the_queued_link_actually_delivers(self):
        with self.captureOnCommitCallbacks(execute=True):
            verification.issue(make_application(), 'registrar@aurora.ca')

        self.assertEqual(deliver_pending(), {'sent': 1, 'failed': 0})
        self.assertEqual(mail.outbox[0].to, ['registrar@aurora.ca'])
        self.assertEqual(mail.outbox[0].alternatives[0][1], 'text/html')


@override_settings(FRONTEND_URL='https://portal.example.ca')
class WorkflowMessageTests(TestCase):

    def test_submitting_tells_the_applicant_it_arrived(self):
        application = make_application(status=ApplicationStatus.DRAFT)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        to_student = OutboundEmail.objects.get(to_email=application.student.email)
        self.assertIn('received', to_student.subject.lower())

    def test_submitting_also_asks_the_institution_to_confirm_enrolment(self):
        """Without this the registrar never receives a link and tuition can
        never be confirmed, so the application can never be fully priced."""
        application = make_application(status=ApplicationStatus.DRAFT)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        self.assertTrue(
            OutboundEmail.objects.filter(to_email='registrar@aurora.ca').exists(),
        )
        application.refresh_from_db()
        self.assertIsNotNone(application.enrollment_verification)

    def test_no_confirmation_is_requested_without_a_registrar_email(self):
        application = make_application(
            status=ApplicationStatus.DRAFT,
            answers={k: v for k, v in ANSWERS.items() if k != 'registrar_email'},
        )
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        self.assertFalse(
            OutboundEmail.objects.filter(to_email='registrar@aurora.ca').exists(),
        )

    def test_types_that_need_no_enrolment_do_not_ask_for_it(self):
        application = make_application(
            status=ApplicationStatus.DRAFT,
            type=ApplicationType.HARDSHIP_BURSARY,
        )
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        self.assertFalse(
            OutboundEmail.objects.filter(to_email='registrar@aurora.ca').exists(),
        )

    def test_approval_tells_the_applicant(self):
        application = make_application()
        staff, director = make_staff(), make_staff(Role.DIRECTOR)
        workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, staff)

        OutboundEmail.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.APPROVED, director)

        queued = OutboundEmail.objects.get()
        self.assertIn('approved', queued.subject.lower())

    def test_a_decline_carries_the_reason_given(self):
        application = make_application()
        staff = make_staff()
        OutboundEmail.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.DECLINED, staff,
                            note='Not enrolled at an eligible institution.')

        queued = OutboundEmail.objects.get()
        self.assertIn('Not enrolled at an eligible institution.', queued.body_html)

    def test_requesting_information_says_what_is_needed(self):
        application = make_application()
        staff = make_staff()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)

        OutboundEmail.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.INFO_REQUESTED, staff,
                            note='We need your most recent transcript.')

        queued = OutboundEmail.objects.get()
        self.assertIn('most recent transcript', queued.body_html)

    def test_internal_steps_do_not_email_the_applicant(self):
        """Forwarding to the Director is not the applicant's business."""
        application = make_application()
        staff = make_staff()
        OutboundEmail.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
            workflow.record(application, ApplicationEvent.Action.FORWARDED, staff)

        self.assertFalse(OutboundEmail.objects.exists())

    def test_an_application_without_a_student_emails_no_applicant(self):
        """The registrar is still asked: their confirmation does not depend on
        the portal knowing who the applicant is."""
        application = make_application(student=None, status=ApplicationStatus.DRAFT)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        recipients = set(OutboundEmail.objects.values_list('to_email', flat=True))
        self.assertEqual(recipients, {'registrar@aurora.ca'})


class InPortalNoticeTests(TestCase):

    def test_a_decision_also_appears_in_the_portal(self):
        application = make_application()
        director = make_staff(Role.DIRECTOR)
        staff = make_staff()
        workflow.record(application, ApplicationEvent.Action.REVIEWED, staff)
        workflow.record(application, ApplicationEvent.Action.FORWARDED, staff)
        workflow.record(application, ApplicationEvent.Action.APPROVED, director)

        notice = Notification.objects.filter(user=application.student).first()
        self.assertIsNotNone(notice)
        self.assertIn(str(application.pk), notice.link)

    def test_a_failed_notice_does_not_break_the_transition(self):
        """A person's application must not fail because a notice could not be written."""
        from unittest.mock import patch

        application = make_application(status=ApplicationStatus.DRAFT)
        with patch.object(Notification.objects, 'create', side_effect=RuntimeError('db')):
            workflow.record(application, ApplicationEvent.Action.SUBMITTED)

        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.SUBMITTED)
