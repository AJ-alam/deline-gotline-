"""Draining the outbound queue from a scheduler.

`send_queued_emails` is a management command, and nothing on a serverless
deployment can run one on a timer — which is how 143 messages once sat unsent
while every test passed. `POST /api/tasks/send-emails/` is that command over
HTTP so an ordinary cron line can drive it.

The caller is a cron line with no account, so a shared secret is the only thing
in front of it. That makes the *refusals* the part worth testing: an endpoint
that sends mail for anybody who asks is worse than one that never runs.
"""

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from notifications.delivery import enqueue
from notifications.models import OutboundEmail

TOKEN = 'a-real-token-nobody-would-guess'

# The test settings use a console backend, which needs no credentials and is
# therefore never asked about them. The credential checks only mean anything
# against the transport a deployment actually uses.
SMTP = 'django.core.mail.backends.smtp.EmailBackend'


class DrainAuthorisationTests(TestCase):
    """Who may flush the queue."""

    def setUp(self):
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')
        self.url = reverse('send-queued-emails')

    def assertNothingSent(self):
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(OutboundEmail.objects.get().status,
                         OutboundEmail.Status.PENDING)

    @override_settings(TASK_TOKEN='')
    def test_an_unconfigured_token_refuses_rather_than_opening_the_endpoint(self):
        """A blank secret compared against a blank header is a match.

        Getting this backwards leaves a public endpoint that anybody can use to
        flush the office's mail queue, so the unset case is refused explicitly
        rather than falling through to the comparison.
        """
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 503)
        self.assertNothingSent()

    @override_settings(TASK_TOKEN='')
    def test_an_unconfigured_token_refuses_even_when_the_caller_sends_nothing(self):
        """The empty string is what an absent header presents."""
        response = self.client.post(self.url, HTTP_X_TASK_TOKEN='')

        self.assertEqual(response.status_code, 503)
        self.assertNothingSent()

    @override_settings(TASK_TOKEN=TOKEN)
    def test_no_credentials_at_all_is_refused(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertNothingSent()

    @override_settings(TASK_TOKEN=TOKEN)
    def test_the_wrong_token_is_refused(self):
        response = self.client.post(
            self.url, HTTP_AUTHORIZATION='Bearer not-the-token')

        self.assertEqual(response.status_code, 403)
        self.assertNothingSent()

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_prefix_of_the_token_is_refused(self):
        """compare_digest, not startswith."""
        response = self.client.post(
            self.url, HTTP_AUTHORIZATION=f'Bearer {TOKEN[:-1]}')

        self.assertEqual(response.status_code, 403)
        self.assertNothingSent()

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_signed_in_student_may_not_drain_the_queue(self):
        """Being a person is not authorisation; holding the secret is.

        The endpoint takes no authentication classes, so a session or a bearer
        JWT is simply not the credential it asks for.
        """
        from accounts.models import Role, User

        student = User.objects.create_user(
            email='student@example.com', password='DemoPass123!', role=Role.STUDENT)
        self.client.force_login(student)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertNothingSent()


class DrainDeliveryTests(TestCase):
    """What a correctly authorised call actually does."""

    def setUp(self):
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')
        self.url = reverse('send-queued-emails')

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_bearer_token_drains_the_queue(self):
        response = self.client.post(
            self.url, HTTP_AUTHORIZATION=f'Bearer {TOKEN}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'sent': 1, 'failed': 0})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(OutboundEmail.objects.get().status,
                         OutboundEmail.Status.SENT)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_the_x_task_token_header_works_too(self):
        """Some shared-hosting cron setups strip Authorization."""
        response = self.client.post(self.url, HTTP_X_TASK_TOKEN=TOKEN)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_second_call_sends_nothing_twice(self):
        self.client.post(self.url, HTTP_X_TASK_TOKEN=TOKEN)
        response = self.client.post(self.url, HTTP_X_TASK_TOKEN=TOKEN)

        self.assertEqual(response.json(), {'sent': 0, 'failed': 0})
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_the_response_says_what_it_did(self):
        """A cron that logs its output should record something readable, and a
        scheduler with no eyes on it is the reason the queue was never drained
        the first time."""
        for index in range(3):
            enqueue(f'r{index}@aurora.ca', 'Subject', '<p>Body</p>')

        response = self.client.post(self.url, HTTP_X_TASK_TOKEN=TOKEN)

        self.assertEqual(response.json(), {'sent': 4, 'failed': 0})


class EmailStatusAuthorisationTests(TestCase):
    """The diagnostic is behind the same secret as the drain.

    It reports what a deployment is configured to do, which is not something to
    publish. Tested separately from the drain rather than trusting the shared
    base class: the two endpoints share `authorise` today, and a test that only
    ever exercised one of them would pass the day somebody overrides it on the
    other.
    """

    def setUp(self):
        self.url = reverse('email-status')

    @override_settings(TASK_TOKEN='')
    def test_an_unconfigured_token_refuses_rather_than_opening_the_endpoint(self):
        self.assertEqual(self.client.get(self.url).status_code, 503)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_no_credentials_at_all_is_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_prefix_of_the_token_is_refused(self):
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f'Bearer {TOKEN[:-1]}')

        self.assertEqual(response.status_code, 403)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_signed_in_student_may_not_read_it(self):
        from accounts.models import Role, User

        student = User.objects.create_user(
            email='student@example.com', password='DemoPass123!', role=Role.STUDENT)
        self.client.force_login(student)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_the_x_task_token_header_works_too(self):
        response = self.client.get(self.url, HTTP_X_TASK_TOKEN=TOKEN)

        self.assertEqual(response.status_code, 200)


class EmailStatusReportingTests(TestCase):
    """What the diagnostic says, and what it must never say."""

    def setUp(self):
        self.url = reverse('email-status')

    def get(self):
        return self.client.get(self.url, HTTP_X_TASK_TOKEN=TOKEN).json()

    @override_settings(TASK_TOKEN=TOKEN, EMAIL_BACKEND=SMTP,
                       EMAIL_HOST_PASSWORD='hunter2-do-not-leak')
    def test_the_smtp_password_is_never_in_the_response(self):
        """A diagnostic is not an escape hatch for reading credentials.

        Asserted against the whole serialised body rather than against the field
        that holds it: the fault worth stopping is a password arriving somewhere
        nobody thought to look, which checking one key by name cannot see.
        """
        import json

        body = json.dumps(self.get())

        self.assertNotIn('hunter2-do-not-leak', body)

    @override_settings(TASK_TOKEN=TOKEN, EMAIL_HOST_PASSWORD='hunter2')
    def test_it_says_whether_the_password_is_set_without_saying_what_it_is(self):
        self.assertIs(self.get()['delivery']['password_set'], True)

    @override_settings(TASK_TOKEN=TOKEN, EMAIL_BACKEND=SMTP,
                       EMAIL_HOST_PASSWORD='')
    def test_a_missing_password_is_reported_as_a_problem(self):
        report = self.get()

        self.assertIs(report['delivery']['password_set'], False)
        self.assertFalse(report['deliverable'])
        self.assertTrue(any('EMAIL_HOST_PASSWORD' in problem
                            for problem in report['problems']))

    @override_settings(TASK_TOKEN=TOKEN)
    def test_it_changes_nothing(self):
        """Read-only. A diagnostic that drains the queue it is measuring cannot
        be run to find out whether the queue is draining."""
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')

        self.get()

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(OutboundEmail.objects.get().status,
                         OutboundEmail.Status.PENDING)

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_queue_that_has_never_been_drained_is_reported_as_a_problem(self):
        """The production fault this endpoint was written for.

        No scheduler existed, so the outbox filled and `sent` stayed at nought
        while every screen in the portal looked healthy. Messages waiting with
        nothing ever delivered is that state, and it is the one the office
        cannot see from anywhere else.
        """
        enqueue('registrar@aurora.ca', 'Subject', '<p>Body</p>')

        report = self.get()

        self.assertEqual(report['queue']['pending'], 1)
        self.assertEqual(report['queue']['sent'], 0)
        self.assertFalse(report['deliverable'])
        self.assertTrue(any('none has ever been sent' in problem
                            for problem in report['problems']))

    @override_settings(TASK_TOKEN=TOKEN)
    def test_a_backlog_beside_earlier_deliveries_is_a_note_rather_than_a_problem(self):
        """A scheduler that runs in a minute leaves messages waiting too.

        Reporting that as a fault is how a diagnostic becomes one nobody reads,
        which is the same way `residency_flag` came to be ignored.
        """
        self.client.post(reverse('send-queued-emails'), HTTP_X_TASK_TOKEN=TOKEN)
        enqueue('someone@aurora.ca', 'Subject', '<p>Body</p>')
        enqueue('another@aurora.ca', 'Subject', '<p>Body</p>')
        OutboundEmail.objects.filter(to_email='someone@aurora.ca').update(
            status=OutboundEmail.Status.SENT)

        report = self.get()

        self.assertEqual(report['queue']['sent'], 1)
        self.assertFalse(any('none has ever been sent' in problem
                             for problem in report['problems']))
        self.assertTrue(any('waiting' in note for note in report['notes']))

    @override_settings(TASK_TOKEN=TOKEN, DEBUG=False, TESTING=False,
                       FRONTEND_URL='http://localhost:5173')
    def test_a_localhost_registrar_link_is_a_problem_on_a_deployment(self):
        """Mail really does go out, carrying a link only the sender can open.

        The registrar has no way to report that back, and the office's own
        browser resolves it perfectly — so nothing anywhere says so.
        """
        report = self.get()

        self.assertFalse(report['deliverable'])
        self.assertTrue(any('points at the machine' in problem
                            for problem in report['problems']))

    @override_settings(TASK_TOKEN=TOKEN, DEBUG=True,
                       FRONTEND_URL='http://localhost:5173')
    def test_the_same_link_is_only_a_note_while_developing(self):
        report = self.get()

        self.assertTrue(any('points at the machine' in note
                            for note in report['notes']))

    @override_settings(TASK_TOKEN=TOKEN, FRONTEND_URL='https://dgg.example.ca')
    def test_it_reports_the_link_a_registrar_will_actually_receive(self):
        """The token in the mail is built from FRONTEND_URL, so this is the one
        place the wrong host can be seen before an institution receives it."""
        self.assertEqual(self.get()['links']['registrar_link'],
                         'https://dgg.example.ca/enrolment/<token>')

    @override_settings(TASK_TOKEN=TOKEN)
    def test_it_names_who_the_backlog_would_reach(self):
        """The question asked before draining a queue nobody has drained.

        Whether 112 waiting messages are a morning of testing or a real intake
        decides whether flushing them is a fix or a mailout to institutions, and
        no screen in the portal answers it.
        """
        enqueue('registrar@aurora.ca', 'One', '<p>Body</p>')
        enqueue('registrar@aurora.ca', 'Two', '<p>Body</p>')
        enqueue('student@example.com', 'Three', '<p>Body</p>')

        queue = self.get()['queue']

        self.assertEqual(queue['distinct_recipients'], 2)
        self.assertEqual(queue['pending_recipients'][0],
                         {'to_email': 'registrar@aurora.ca', 'count': 2})

    @override_settings(TASK_TOKEN=TOKEN)
    def test_delivered_messages_are_not_named(self):
        """Only what would go out *now*. A sent message is history, and listing
        it would overstate the backlog somebody is deciding about."""
        enqueue('already@aurora.ca', 'Sent', '<p>Body</p>')
        self.client.post(reverse('send-queued-emails'), HTTP_X_TASK_TOKEN=TOKEN)
        enqueue('waiting@aurora.ca', 'Pending', '<p>Body</p>')

        queue = self.get()['queue']

        self.assertEqual(queue['distinct_recipients'], 1)
        self.assertEqual([r['to_email'] for r in queue['pending_recipients']],
                         ['waiting@aurora.ca'])
