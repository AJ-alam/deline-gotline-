"""Tests for the email outbox.

The failure this replaces: mail was handed to a daemon thread that returned
success immediately, so on serverless the process froze at response time and
approval notices vanished with no error.
"""

from django.core import mail
from django.db import transaction
from django.test import TestCase, TransactionTestCase

from notifications.delivery import (
    MAX_ATTEMPTS, deliver, deliver_pending, enqueue, enqueue_on_commit,
)
from notifications.models import OutboundEmail


class EnqueueTests(TestCase):

    def test_queueing_does_not_send(self):
        """Requests stay fast: no SMTP call happens on the request path."""
        enqueue('student@test.com', 'Decision', '<p>Approved</p>')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(OutboundEmail.objects.count(), 1)
        self.assertEqual(OutboundEmail.objects.get().status, OutboundEmail.Status.PENDING)

    def test_missing_recipient_is_refused_not_queued(self):
        self.assertIsNone(enqueue('', 'Decision', '<p>body</p>'))
        self.assertEqual(OutboundEmail.objects.count(), 0)


class DeliveryTests(TestCase):

    def test_delivering_marks_sent_and_reaches_the_backend(self):
        enqueue('student@test.com', 'Decision', '<p>Approved</p>')
        result = deliver_pending()

        self.assertEqual(result, {'sent': 1, 'failed': 0})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'Decision')

        record = OutboundEmail.objects.get()
        self.assertEqual(record.status, OutboundEmail.Status.SENT)
        self.assertIsNotNone(record.sent_at)

    def test_html_and_plain_text_are_both_present(self):
        enqueue('student@test.com', 'Decision', '<p>Approved</p><br>Congratulations')
        deliver_pending()
        message = mail.outbox[0]
        self.assertIn('Approved', message.body)              # generated plain text
        self.assertNotIn('<p>', message.body)
        self.assertEqual(message.alternatives[0][1], 'text/html')

    def test_a_failure_is_retried_not_discarded(self):
        record = enqueue('student@test.com', 'Decision', '<p>body</p>')
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.dummy.NoBackend'):
            self.assertFalse(deliver(record))

        record.refresh_from_db()
        self.assertEqual(record.status, OutboundEmail.Status.PENDING)   # still queued
        self.assertEqual(record.attempts, 1)
        self.assertTrue(record.last_error)

    def test_delivery_gives_up_only_after_repeated_failure(self):
        record = enqueue('student@test.com', 'Decision', '<p>body</p>')
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.dummy.NoBackend'):
            for _ in range(MAX_ATTEMPTS):
                deliver(record)

        record.refresh_from_db()
        self.assertEqual(record.status, OutboundEmail.Status.FAILED)
        self.assertEqual(record.attempts, MAX_ATTEMPTS)

    def test_exhausted_messages_are_not_retried_forever(self):
        OutboundEmail.objects.create(
            to_email='x@test.com', subject='S', body_html='<p>b</p>',
            attempts=MAX_ATTEMPTS, status=OutboundEmail.Status.PENDING,
        )
        self.assertEqual(deliver_pending(), {'sent': 0, 'failed': 0})

    def test_a_sent_message_is_never_sent_twice(self):
        enqueue('student@test.com', 'Decision', '<p>body</p>')
        deliver_pending()
        deliver_pending()
        self.assertEqual(len(mail.outbox), 1)

    def test_limit_bounds_one_run(self):
        for i in range(5):
            enqueue(f's{i}@test.com', 'Decision', '<p>body</p>')
        self.assertEqual(deliver_pending(limit=2), {'sent': 2, 'failed': 0})
        self.assertEqual(
            OutboundEmail.objects.filter(status=OutboundEmail.Status.PENDING).count(), 3,
        )


class TransactionSafetyTests(TransactionTestCase):
    """A student must never be told about a decision that rolled back."""

    def test_nothing_is_queued_when_the_transaction_rolls_back(self):
        class Rollback(Exception):
            pass

        with self.assertRaises(Rollback):
            with transaction.atomic():
                enqueue_on_commit('student@test.com', 'Approved', '<p>body</p>')
                raise Rollback()

        self.assertEqual(OutboundEmail.objects.count(), 0)

    def test_queued_after_the_transaction_commits(self):
        with transaction.atomic():
            enqueue_on_commit('student@test.com', 'Approved', '<p>body</p>')
            self.assertEqual(OutboundEmail.objects.count(), 0)   # not yet

        self.assertEqual(OutboundEmail.objects.count(), 1)
