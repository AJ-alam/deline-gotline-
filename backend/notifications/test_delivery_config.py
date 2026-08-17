"""Getting mail out of the building.

The enrolment verification is the message the whole tuition path depends on:
until the registrar opens their link nothing can be confirmed, forwarded or
paid. It is queued on commit and delivered by a separate worker, which gives it
three ways to fail quietly — the queue never drained, the credentials never
set, or the message unprintable on the machine doing the sending.

The third one actually happened: every message contains "Délı̨nę", the console
backend writes to a Windows terminal in cp1252, and all 143 queued messages
failed with UnicodeEncodeError.
"""

import io
import sys

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from notifications.delivery import deliver_pending, enqueue
from notifications.email_backends import Utf8ConsoleEmailBackend
from notifications.models import OutboundEmail

# The characters that broke it: the government's own name, a curly apostrophe
# and an em dash.
AWKWARD = 'Délı̨nę Got’ı̨nę Government — enrolment confirmation'

CONSOLE = 'notifications.email_backends.Utf8ConsoleEmailBackend'


class UnicodeDeliveryTests(TestCase):
    """A message must not fail to send because a terminal cannot draw it."""

    def setUp(self):
        enqueue('registrar@aurora.ca', AWKWARD, f'<p>{AWKWARD}</p>')

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_a_message_with_the_office_name_in_it_sends(self):
        result = deliver_pending()

        self.assertEqual(result, {'sent': 1, 'failed': 0})
        self.assertEqual(OutboundEmail.objects.get().status, OutboundEmail.Status.SENT)

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_more_than_one_message_can_be_sent_in_a_run(self):
        """The first fix wrapped stdout in a TextIOWrapper, which closed the
        underlying buffer when collected — so the second message failed with
        'I/O operation on closed file'."""
        for index in range(3):
            enqueue(f'r{index}@aurora.ca', AWKWARD, f'<p>{AWKWARD}</p>')

        result = deliver_pending()

        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['sent'], 4)
        self.assertFalse(
            OutboundEmail.objects.filter(status=OutboundEmail.Status.PENDING).exists())

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_stdout_is_left_usable_afterwards(self):
        deliver_pending()
        self.assertFalse(sys.stdout.closed)

    def test_the_backend_does_not_raise_on_a_stream_it_cannot_reconfigure(self):
        """Under a test runner stdout is often a pipe or a StringIO."""
        Utf8ConsoleEmailBackend(stream=io.StringIO())


class QueueTests(TestCase):
    """Queued is not sent. Nothing drains it on its own."""

    def test_queueing_does_not_deliver(self):
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(OutboundEmail.objects.get().status,
                         OutboundEmail.Status.PENDING)

    def test_the_worker_delivers_what_was_queued(self):
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')

        call_command('send_queued_emails', verbosity=0)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['registrar@aurora.ca'])
        self.assertEqual(OutboundEmail.objects.get().status, OutboundEmail.Status.SENT)

    def test_a_message_with_no_recipient_is_not_queued(self):
        self.assertIsNone(enqueue('', 'Subject', '<p>Body</p>'))
        self.assertFalse(OutboundEmail.objects.exists())


class StatusReportTests(TestCase):
    """The report exists so a misconfiguration is found here rather than by a
    registrar who never received anything."""

    def report(self):
        out = io.StringIO()
        call_command('email_status', stdout=out, no_color=True)
        return out.getvalue()

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_a_console_backend_is_reported_as_not_reaching_anyone(self):
        self.assertIn('nothing reaches a real registrar', self.report().replace('\n', ' '))

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_a_console_subclass_is_not_mistaken_for_smtp(self):
        """Matching on the dotted path reported the local UTF-8 console backend
        as SMTP and demanded credentials it does not use."""
        report = self.report()
        self.assertNotIn('EMAIL_HOST_USER is not set', report)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                       EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_smtp_without_credentials_is_reported_as_a_problem(self):
        report = self.report()
        self.assertIn('EMAIL_HOST_USER is not set', report)
        self.assertIn('EMAIL_HOST_PASSWORD is not set', report)

    @override_settings(EMAIL_BACKEND=CONSOLE, FRONTEND_URL='http://localhost:5173')
    def test_a_link_pointing_at_this_machine_is_flagged(self):
        self.assertIn('cannot open that link', self.report().replace('\n', ' '))

    @override_settings(EMAIL_BACKEND=CONSOLE, FRONTEND_URL='https://funding.deline.ca')
    def test_a_deployed_link_is_not_flagged(self):
        self.assertNotIn('cannot open that link', self.report().replace('\n', ' '))

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_a_queue_that_has_never_been_drained_is_reported(self):
        for index in range(3):
            enqueue(f'r{index}@aurora.ca', 'Subject', '<p>Body</p>')

        self.assertIn('none has ever been sent', self.report().replace('\n', ' '))

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_a_healthy_queue_says_so(self):
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')
        deliver_pending()

        self.assertIn('Outbound email is deliverable', self.report())
