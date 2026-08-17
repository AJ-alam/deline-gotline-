"""The office correcting a filed application on the applicant's behalf.

A student may only edit their own application while the office is waiting for
information. The office needs to fix things outside that window — a misspelled
institution, a transposed student number, an answer given over the counter —
and until this existed the only ways were to decline the application or to ask
the student to file it again.

Three properties make it safe rather than a hole in the middle of the record:

  * administrators only, so the person who rewrites the answers is not the
    person who assesses them;
  * the same schema, and the same splitting of the SIN and the banking fields,
    as a submission — an office edit that could put a SIN into `answers` would
    undo the arrangement everything else maintains;
  * the applicant is told, every time. A correction nobody hears about is
    indistinguishable from a record that was never right, and it is the version
    they would be held to on appeal.
"""

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import BankAccount, Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicantIdentifier,
    AuditEntry,
)
from funding.schemas import ValidationError as SchemaValidationError, get_schema
from funding.management.commands.prune_stale_answers import stale_keys
from funding.services import workflow
from funding.test_fixtures import answers_for
from notifications.models import Notification, OutboundEmail


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@amend.test', 'pw12345678',
        first_name='Test', last_name=str(role).title(), role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


def appeal_answers(**overrides):
    defaults = dict(
        full_name='Majid Khan', student_number='A-1',
        institution_name='Aurora College', semester='fall',
        academic_year='2026-2027',
        appeal_reason='The course load was recorded wrongly.',
        signature='Majid Khan',
    )
    defaults.update(overrides)
    return answers_for('appeal', **defaults)


class AmendmentTests(TestCase):

    def setUp(self):
        self.student = make_user(email='student@amend.test')
        self.admin = make_user(Role.ADMIN, 'admin@amend.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@amend.test')
        self.director = make_user(Role.DIRECTOR, 'director@amend.test')
        self.finance = make_user(Role.FINANCE, 'finance@amend.test')
        self.client = APIClient()

        self.client.force_authenticate(self.student)
        response = self.client.post(
            '/api/applications/',
            {'type': 'appeal', 'answers': appeal_answers()}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])
        Notification.objects.all().delete()
        OutboundEmail.objects.all().delete()

    def amend(self, actor=None, **overrides):
        self.client.force_authenticate(actor or self.admin)
        note = overrides.pop('_note', '')
        payload = {'answers': appeal_answers(**overrides)}
        if note:
            payload['note'] = note
        return self.client.post(
            f'/api/applications/{self.application.pk}/amend/', payload,
            format='json')

    # ── Who may ────────────────────────────────────────────────────────────

    def test_an_administrator_can_correct_a_filed_application(self):
        response = self.amend(institution_name='Aurora College — North Slave')

        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['institution_name'],
                         'Aurora College — North Slave')

    def test_a_director_mid_decision_is_told_the_answers_changed(self):
        """An amendment leaves the application where it sits — and where it
        sits may be the director's queue.

        They were asked to decide one thing and are now deciding another. Only
        the applicant was told, and they are not the person about to sign it
        off. Same fault as forwarding an application and approving it a second
        later: somebody is asked to act on a state that has since changed and is
        not told about it.
        """
        for action in (ApplicationEvent.Action.REVIEWED,
                       ApplicationEvent.Action.FORWARDED):
            workflow.record(self.application, action, self.worker)
        Notification.objects.all().delete()

        self.amend(institution_name='Somewhere else entirely',
                   _note='Corrected the institution over the phone.')

        told = Notification.objects.filter(user=self.director)
        self.assertTrue(told.exists(), 'the director was not told')
        self.assertIn('changed', told.first().title.lower())
        # And the applicant is still told, as they always were.
        self.assertTrue(Notification.objects.filter(user=self.student).exists())

    def test_a_director_is_not_told_about_an_amendment_that_is_not_theirs_yet(self):
        """Nothing is waiting on them, so nothing needs their attention."""
        self.amend(institution_name='Aurora College — North Slave')

        self.assertFalse(Notification.objects.filter(user=self.director).exists())

    def test_a_support_worker_cannot(self):
        """The people who assess an application do not rewrite it.

        Someone who can both change the answers and advance the application can
        price whatever they like without a second person seeing it.
        """
        response = self.amend(actor=self.worker, institution_name='Somewhere else')

        self.assertEqual(response.status_code, 403)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['institution_name'],
                         'Aurora College')

    def test_neither_can_the_director_or_finance(self):
        for actor in (self.director, self.finance):
            response = self.amend(actor=actor, institution_name='Somewhere else')
            self.assertEqual(response.status_code, 403, actor.role)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['institution_name'],
                         'Aurora College')

    def test_a_student_cannot_amend_their_own_application_this_way(self):
        """`revise` is their path, and only while the office is waiting.

        Opening this to the owner would give a student an edit with no status
        attached to it — a way to change a filed application at any time,
        including while it is being assessed.
        """
        response = self.amend(actor=self.student, appeal_reason='Something else')

        self.assertEqual(response.status_code, 403)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['appeal_reason'],
                         'The course load was recorded wrongly.')

    def test_an_anonymous_caller_cannot(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': appeal_answers()}, format='json')
        self.assertEqual(response.status_code, 401)

    # ── What it does to the application ────────────────────────────────────

    def test_an_amendment_does_not_move_the_application(self):
        """A correction is not a step through review.

        Routing it through `workflow.record` would rewrite the status to
        whatever the action mapped to, so fixing a typo on a decided
        application would quietly reopen it.
        """
        workflow.record(self.application, ApplicationEvent.Action.REVIEWED,
                        actor=self.worker)
        self.application.refresh_from_db()

        self.amend(institution_name='Aurora College — North Slave')

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.UNDER_REVIEW)
        self.assertTrue(workflow.status_is_consistent(self.application))

    def test_the_history_says_who_changed_it(self):
        self.amend(institution_name='Aurora College — North Slave',
                   _note='Corrected the campus, confirmed by phone.')

        event = self.application.events.get(action=ApplicationEvent.Action.AMENDED)
        self.assertEqual(event.actor, self.admin)
        self.assertIn('Corrected the campus', event.note)

    def test_the_audit_entry_names_the_answers_that_changed(self):
        self.amend(institution_name='Aurora College — North Slave')

        entry = AuditEntry.objects.get(action='application.amended')
        self.assertEqual(entry.actor, self.admin)
        self.assertIn('institution_name', entry.detail)
        self.assertNotIn('appeal_reason', entry.detail)

    # ── What the applicant is told ─────────────────────────────────────────

    def test_the_student_is_notified_that_their_application_changed(self):
        self.amend(institution_name='Aurora College — North Slave',
                   _note='Corrected the campus name.')

        notice = Notification.objects.get(user=self.student)
        self.assertEqual(notice.kind, Notification.Kind.AMENDED)
        self.assertIn('Corrected the campus name', notice.message)
        self.assertEqual(notice.link, f'/applications/{self.application.pk}')

    def test_the_notice_carries_its_own_kind(self):
        """Not GENERAL. A person has to be able to tell 'we changed your form'
        from every other notice without reading the wording for clues."""
        self.amend(institution_name='Aurora College — North Slave')
        self.assertEqual(
            Notification.objects.get(user=self.student).kind,
            Notification.Kind.AMENDED)

    def test_an_email_goes_out_as_well(self):
        # Queued on commit, so a message can never describe an edit that rolled
        # back. Nothing commits inside a TestCase unless the callbacks are run.
        with self.captureOnCommitCallbacks(execute=True):
            self.amend(institution_name='Aurora College — North Slave')

        email = OutboundEmail.objects.get(to_email=self.student.email)
        self.assertIn('updated', email.subject.lower())

    # ── What it refuses ────────────────────────────────────────────────────

    def test_a_decided_application_cannot_be_rewritten(self):
        """Its answers are the record the decision was made from."""
        for action in (ApplicationEvent.Action.REVIEWED,
                       ApplicationEvent.Action.FORWARDED,
                       ApplicationEvent.Action.APPROVED):
            workflow.record(self.application, action, actor=self.director)
        self.application.refresh_from_db()

        response = self.amend(institution_name='Somewhere else')

        self.assertEqual(response.status_code, 409)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['institution_name'],
                         'Aurora College')

    def test_answers_that_do_not_validate_are_refused(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': {'full_name': 'Majid Khan'}}, format='json')

        self.assertEqual(response.status_code, 400)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['appeal_reason'],
                         'The course load was recorded wrongly.')

    def test_an_unknown_answer_cannot_be_introduced_by_the_office(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': appeal_answers(not_a_field='x')}, format='json')

        self.assertEqual(response.status_code, 400)


class PrivateAnswersSurviveAnAmendmentTests(TestCase):
    """The office's edit goes through the same splitting as a submission.

    This is the property most worth pinning: `answers` is returned whole by the
    detail endpoint, printed on the paper form and used to pre-fill the
    registrar's copy. A path that writes `answers` without splitting puts a SIN
    into all three.
    """

    def setUp(self):
        self.student = make_user(email='student2@amend.test')
        self.admin = make_user(Role.ADMIN, 'admin2@amend.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)

        response = self.client.post('/api/applications/', {
            'type': 'graduation_bursary',
            'answers': answers_for('graduation_bursary'),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

    def test_a_sin_corrected_by_the_office_never_lands_in_answers(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': answers_for('graduation_bursary', sin='130692544')},
            format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertNotIn('130692544', str(self.application.answers))
        self.assertTrue(
            ApplicantIdentifier.objects.filter(application=self.application).exists())

    def test_a_bank_account_corrected_by_the_office_reaches_the_account(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': answers_for('graduation_bursary',
                                    account_number='5555544444',
                                    transit_number='54321')},
            format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertNotIn('5555544444', str(self.application.answers))
        self.assertTrue(
            BankAccount.objects.filter(user=self.student, is_current=True).exists()
            or ApplicantIdentifier.objects.filter(
                application=self.application, kind='bank_account').exists())


class EditingWhatTheServerWroteTests(TestCase):
    """An application carries answers its own schema never asked for.

    When a registrar confirms an enrolment, the tuition they state is written
    onto the application — `confirmed_tuition`, which the admission schema has
    no question for, because the student is never asked it. Re-posting the
    stored answers was then refused for a key the *server* had put there, so
    every admission application became uneditable by anybody the moment its
    institution answered: no correction by the office, and no reply to a
    request for more information by the student.
    """

    def setUp(self):
        self.student = make_user(email='student3@amend.test')
        self.admin = make_user(Role.ADMIN, 'admin3@amend.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)

        response = self.client.post('/api/applications/', {
            'type': 'admission', 'answers': answers_for('admission'),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

        # What the registrar's confirmation does to the answers.
        self.application.answers = {
            **self.application.answers, 'confirmed_tuition': '6250.00'}
        self.application.save(update_fields=['answers'])

    def test_the_office_can_still_edit_it(self):
        self.client.force_authenticate(self.admin)
        answers = {**self.application.answers, 'program': 'Environmental Technology'}

        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': answers}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['program'],
                         'Environmental Technology')

    def test_the_registrar_s_figure_survives_the_edit(self):
        self.client.force_authenticate(self.admin)
        answers = {**self.application.answers, 'program': 'Environmental Technology'}

        self.client.post(f'/api/applications/{self.application.pk}/amend/',
                         {'answers': answers}, format='json')

        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['confirmed_tuition'], '6250.00')

    def test_an_edit_cannot_set_the_registrar_s_figure(self):
        """Tuition is funded against the institution's number, never against one
        somebody typed. A route by which an edit could set it is a route by
        which an award can be inflated."""
        self.client.force_authenticate(self.admin)
        answers = {**self.application.answers, 'confirmed_tuition': '99999.00'}

        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': answers}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['confirmed_tuition'], '6250.00')

    def test_a_key_that_is_not_already_stored_is_still_refused(self):
        """Carrying forward what the server wrote is not the same as accepting
        anything: an unknown key the application does not already have is an
        answer nothing will ever read."""
        self.client.force_authenticate(self.admin)
        answers = {**self.application.answers, 'invented_field': 'x'}

        response = self.client.post(
            f'/api/applications/{self.application.pk}/amend/',
            {'answers': answers}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('invented_field', str(response.data))


class PrivateAnswersAreNotAskedForTwiceTests(TestCase):
    """A required SIN or bank account is split off and never returned.

    So re-posting a stored application posts it without them, and required, they
    were reported missing on every edit — of both kinds, on every form that asks
    for one. The student answering a request for more information hit exactly
    the same wall as the office.
    """

    def test_a_stored_application_validates_without_its_private_answers(self):
        schema = get_schema('graduation_bursary')
        submitted = schema.clean(answers_for('graduation_bursary'))
        public, private = schema.split_private(submitted)
        self.assertTrue(private, 'this form is supposed to have private answers')

        # What comes back from the API: everything except what was split off.
        again = schema.clean({k: str(v) for k, v in public.items()}, revising=True)

        self.assertNotIn('sin', again)
        self.assertEqual(again['full_name'], submitted['full_name'])

    def test_a_private_answer_that_is_sent_is_still_validated(self):
        schema = get_schema('graduation_bursary')
        with self.assertRaises(SchemaValidationError):
            schema.clean(answers_for('graduation_bursary', sin='not-a-sin'),
                         revising=True)

    def test_a_missing_required_public_answer_is_still_refused(self):
        """Only the private ones are forgiven. A blank the applicant can see is
        still a blank."""
        schema = get_schema('graduation_bursary')
        answers = answers_for('graduation_bursary')
        answers['full_name'] = ''
        with self.assertRaises(SchemaValidationError):
            schema.clean(answers, revising=True)


class PruningAnswersNobodyCanSeeTests(TestCase):
    """A schema is code, so a form changes between deploys.

    Applications filed before a change keep the old keys. Nothing renders them —
    `answers` is drawn from the schema — so they are answers to questions nobody
    can see, sitting in the record an award is defended from.
    """

    def setUp(self):
        self.student = make_user(email='student4@amend.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        response = self.client.post('/api/applications/', {
            'type': 'appeal', 'answers': appeal_answers()}, format='json')
        self.application = Application.objects.get(pk=response.data['id'])

    def test_an_answer_whose_question_is_gone_is_found(self):
        self.application.answers = {**self.application.answers,
                                    'original_decision': 'Declined in March'}
        self.application.save(update_fields=['answers'])

        self.assertEqual(stale_keys(self.application), ['original_decision'])

    def test_what_the_registrar_wrote_is_not_stale(self):
        """`confirmed_tuition` has no question because the student is never
        asked it — the institution states it. Pruning it would throw away the
        figure tuition is funded against."""
        self.application.answers = {**self.application.answers,
                                    'confirmed_tuition': '6000.00'}
        self.application.save(update_fields=['answers'])

        self.assertEqual(stale_keys(self.application), [])

    def test_nothing_changes_without_apply(self):
        self.application.answers = {**self.application.answers, 'gone': 'x'}
        self.application.save(update_fields=['answers'])

        call_command('prune_stale_answers', verbosity=0)

        self.application.refresh_from_db()
        self.assertIn('gone', self.application.answers)

    def test_apply_removes_it_and_leaves_the_rest(self):
        self.application.answers = {**self.application.answers, 'gone': 'x'}
        self.application.save(update_fields=['answers'])

        call_command('prune_stale_answers', '--apply', verbosity=0)

        self.application.refresh_from_db()
        self.assertNotIn('gone', self.application.answers)
        self.assertEqual(self.application.answers['appeal_reason'],
                         'The course load was recorded wrongly.')
