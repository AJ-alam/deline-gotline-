"""The help page.

Its one job is to be reachable and correct. Two things it must never do:
require a session — the people who most need a phone number are the ones who
cannot get in — and carry an address written into the client, where the office
cannot correct it without a release.
"""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from core import support

URL = '/api/help/'


class HelpViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_it_is_readable_without_signing_in(self):
        """The whole point. Somebody locked out is who this page is for."""
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200, response.data)

    def test_it_carries_a_way_to_reach_the_office(self):
        contact = self.client.get(URL).data['contact']
        self.assertTrue(contact['email'])
        self.assertTrue(contact['phone'])
        self.assertTrue(contact['address'])

    def test_the_email_looks_like_an_email(self):
        self.assertIn('@', self.client.get(URL).data['contact']['email'])

    def test_it_carries_the_questions(self):
        faq = self.client.get(URL).data['faq']
        self.assertGreaterEqual(len(faq), 2)
        for entry in faq:
            with self.subTest(question=entry['question']):
                self.assertTrue(entry['question'].strip())
                self.assertTrue(entry['answer'].strip())

    def test_every_question_ends_in_a_question_mark(self):
        for entry in self.client.get(URL).data['faq']:
            self.assertTrue(entry['question'].endswith('?'), entry['question'])

    def test_no_two_questions_are_the_same(self):
        """They are keyed by their text on the client."""
        questions = [entry['question'] for entry in self.client.get(URL).data['faq']]
        self.assertEqual(len(questions), len(set(questions)))

    def test_signing_in_changes_nothing(self):
        """Nothing here is per-user. If it ever becomes so, this fails."""
        anonymous = self.client.get(URL).data
        self.client.force_authenticate(User.objects.create_user(
            'student@help.test', 'pw12345678', first_name='A', last_name='B',
            role=Role.STUDENT, is_deline_beneficiary=True,
            is_indian_act_registered=True))
        self.assertEqual(self.client.get(URL).data, anonymous)

    @override_settings(
        SUPPORT_EMAIL='someone.else@example.ca',
        SUPPORT_PHONE='(000) 000-0000',
        SUPPORT_ADDRESS='Somewhere else',
    )
    def test_a_deployment_can_correct_the_details_without_a_release(self):
        """The reason these are settings rather than a constant in the client.
        A help page that is out of date is worse than none."""
        contact = self.client.get(URL).data['contact']
        self.assertEqual(contact['email'], 'someone.else@example.ca')
        self.assertEqual(contact['phone'], '(000) 000-0000')
        self.assertEqual(contact['address'], 'Somewhere else')

    def test_the_answers_describe_what_the_portal_actually_does(self):
        """An answer that describes an intention rather than the behaviour is
        worse than no answer: it sends somebody to wait for an email that is
        not coming.

        Pinned against the two facts the enrolment answer asserts, both of
        which are enforced elsewhere — see funding.services.verification and
        funding.services.workflow.
        """
        answers = {entry['question']: entry['answer'] for entry in support.FAQ}
        enrolment = answers['How is my enrollment verified?']
        self.assertIn('registrar', enrolment)
        self.assertIn('cannot be forwarded or approved', enrolment)

        travel = answers['How do I claim travel?']
        self.assertIn('receipt', travel)
        # The claim's total is derived, not typed — see schemas/travel.py.
        self.assertIn('not something you type', travel)

    def test_it_is_not_writable(self):
        self.assertEqual(self.client.post(URL, {}).status_code, 405)
