"""Asking a student for more information, and the student answering.

The loop the office actually needs:

  1. a reviewer asks, in their own words, for what is missing;
  2. the student is told — by email and in the portal — with a link;
  3. they open it, change what needs changing, attach or replace a document,
     and send it back;
  4. the office can open every document attached to any application.

Before this, (1) recorded a note nobody could act on, (3) did not exist at all —
a filed application could not be changed by anybody — and (4) showed a reviewer
the text `document:12` with no way to open it, which is the same as the
document never having been attached.
"""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

import shutil
import tempfile

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    FundingStream, SupportingDocument,
)
from funding.services import workflow
from funding.test_fixtures import answers_for
from notifications.models import Notification

MEDIA = tempfile.mkdtemp()


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@moreinfo.test', 'pw12345678',
        first_name='Test', last_name=str(role).title(), role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True)


def a_pdf(name='transcript.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4\nhello', content_type='application/pdf')


def appeal_answers(**overrides):
    defaults = dict(
        full_name='Majid Khan', student_number='A-1', institution_name='Aurora',
        semester='fall', academic_year='2026-2027',
        appeal_reason='The course load was recorded wrongly.',
        signature='Majid Khan',
    )
    defaults.update(overrides)
    return answers_for('appeal', **defaults)


@override_settings(MEDIA_ROOT=MEDIA)
class InformationRequestTests(TestCase):
    """A reviewer asks for something, in their own words."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.student = make_user(email='student@moreinfo.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker@moreinfo.test')
        self.client = APIClient()

        self.client.force_authenticate(self.student)
        response = self.client.post(
            '/api/applications/',
            {'type': 'appeal', 'answers': appeal_answers()}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

    def ask(self, note='Please attach your transcript for the Fall term.'):
        self.client.force_authenticate(self.worker)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/transition/',
            {'action': 'info_requested', 'note': note}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        return response

    def test_a_reviewer_can_say_what_is_needed_in_their_own_words(self):
        self.ask('We need proof you were registered full-time.')
        event = self.application.events.get(
            action=ApplicationEvent.Action.INFO_REQUESTED)
        self.assertEqual(event.note, 'We need proof you were registered full-time.')

    def test_the_application_says_what_was_asked_and_by_whom(self):
        """Without it the student opens the application knowing only that
        something is needed."""
        self.ask('We need proof you were registered full-time.')
        self.client.force_authenticate(self.student)
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data
        self.assertEqual(detail['information_requested']['note'],
                         'We need proof you were registered full-time.')
        self.assertEqual(detail['information_requested']['asked_by'],
                         self.worker.full_name)

    def test_the_student_is_notified_with_a_link_to_the_application(self):
        self.ask('Please attach your transcript.')
        notice = (Notification.objects.filter(user=self.student)
                  .order_by('-created_at').first())
        self.assertIsNotNone(notice)
        self.assertEqual(notice.link, f'/applications/{self.application.pk}')
        self.assertIn('transcript', notice.message)

    def test_the_notice_is_marked_as_something_to_act_on(self):
        """The student's dashboard counts these. A general notice would not."""
        self.ask()
        notice = (Notification.objects.filter(user=self.student)
                  .order_by('-created_at').first())
        self.assertEqual(notice.kind, Notification.Kind.ACTION_NEEDED)

    def test_asking_with_no_note_still_reaches_them(self):
        """A reviewer in a hurry should not silently send nothing."""
        self.ask(note='')
        notice = (Notification.objects.filter(user=self.student)
                  .order_by('-created_at').first())
        self.assertTrue(notice.message.strip())


@override_settings(MEDIA_ROOT=MEDIA)
class RevisionTests(TestCase):
    """The student answering: editing answers and swapping documents."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.student = make_user(email='student2@moreinfo.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker2@moreinfo.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        created = self.client.post(
            '/api/applications/',
            {'type': 'appeal', 'answers': appeal_answers()}, format='json')
        self.application = Application.objects.get(pk=created.data['id'])

    def ask_for_more(self):
        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/transition/',
                         {'action': 'info_requested', 'note': 'Attach a transcript.'},
                         format='json')
        self.application.refresh_from_db()
        self.client.force_authenticate(self.student)

    def revise(self, **overrides):
        return self.client.post(
            f'/api/applications/{self.application.pk}/revise/',
            {'answers': appeal_answers(**overrides)}, format='json')

    def test_the_application_says_it_may_be_edited(self):
        """What the client renders the edit form from."""
        self.ask_for_more()
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data
        self.assertTrue(detail['can_revise'])

    def test_a_submitted_application_may_not_be_edited(self):
        """Nothing may change under a reviewer who is reading it."""
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data
        self.assertFalse(detail['can_revise'])
        self.assertEqual(self.revise().status_code, 409)

    def test_the_student_can_correct_an_answer(self):
        self.ask_for_more()
        response = self.revise(appeal_reason='I was full-time for the whole term.')
        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['appeal_reason'],
                         'I was full-time for the whole term.')

    def test_revising_sends_it_back_to_the_office(self):
        """Saving without this leaves the application sitting in 'more
        information needed' while the information sits there unread."""
        self.ask_for_more()
        self.revise()
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.UNDER_REVIEW)

    def test_and_records_who_provided_it(self):
        self.ask_for_more()
        self.revise()
        event = self.application.events.get(
            action=ApplicationEvent.Action.INFO_PROVIDED)
        self.assertEqual(event.actor, self.student)

    def test_the_student_can_attach_a_document_and_name_it_in_the_answers(self):
        self.ask_for_more()
        upload = self.client.post(
            '/api/documents/',
            {'file': a_pdf(), 'field_key': 'doc_supporting',
             'application': self.application.pk},
            format='multipart')
        self.assertEqual(upload.status_code, 201, upload.data)

        response = self.revise(doc_supporting=[upload.data['reference']])
        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['doc_supporting'],
                         [upload.data['reference']])

    def test_a_document_can_be_replaced(self):
        """Changing a document, not only adding one."""
        self.ask_for_more()
        first = self.client.post(
            '/api/documents/',
            {'file': a_pdf('old.pdf'), 'field_key': 'doc_supporting'},
            format='multipart').data
        self.revise(doc_supporting=[first['reference']])

        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/transition/',
                         {'action': 'info_requested', 'note': 'Wrong term.'},
                         format='json')
        self.client.force_authenticate(self.student)
        second = self.client.post(
            '/api/documents/',
            {'file': a_pdf('new.pdf'), 'field_key': 'doc_supporting'},
            format='multipart').data
        self.revise(doc_supporting=[second['reference']])

        self.application.refresh_from_db()
        self.assertEqual(self.application.answers['doc_supporting'],
                         [second['reference']])

    def test_a_revision_is_validated_by_the_same_schema(self):
        """A revision is the application as it now stands, not a patch. A
        second, weaker notion of 'complete' is the one that lets something
        through."""
        self.ask_for_more()
        answers = appeal_answers()
        del answers['appeal_reason']
        response = self.client.post(
            f'/api/applications/{self.application.pk}/revise/',
            {'answers': answers}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('appeal_reason', response.data['answers'])

    def test_another_student_cannot_revise_it(self):
        self.ask_for_more()
        self.client.force_authenticate(make_user(email='other@moreinfo.test'))
        self.assertIn(self.revise().status_code, (403, 404))

    def test_staff_cannot_revise_it_either(self):
        """Answers are the applicant's account of their own circumstances. A
        reviewer editing them is the office answering its own question."""
        self.ask_for_more()
        self.client.force_authenticate(self.worker)
        self.assertIn(self.revise().status_code, (403, 404))

    def test_an_approved_application_cannot_be_revised(self):
        director = make_user(Role.DIRECTOR, 'director@moreinfo.test')
        for action in (ApplicationEvent.Action.REVIEWED,
                       ApplicationEvent.Action.FORWARDED,
                       ApplicationEvent.Action.APPROVED):
            workflow.record(self.application, action, director)
        self.application.refresh_from_db()
        self.client.force_authenticate(self.student)
        self.assertEqual(self.revise().status_code, 409)

    def test_a_corrected_bank_account_does_not_land_in_the_answers(self):
        """The same split as submission. A revision must not be the one path
        that puts an account number into a column returned whole."""
        student = make_user(email='banking@moreinfo.test')
        self.client.force_authenticate(student)
        created = self.client.post('/api/applications/', {
            'type': 'emergency_relief',
            'answers': answers_for(
                'emergency_relief', full_name='A B', email='a@b.test',
                phone='8675550143', emergency_type='housing',
                emergency_description='Furnace failed.', amount_requested='900',
                signature='A B'),
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        application = Application.objects.get(pk=created.data['id'])

        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{application.pk}/transition/',
                         {'action': 'info_requested', 'note': 'Bank details.'},
                         format='json')

        self.client.force_authenticate(student)
        response = self.client.post(f'/api/applications/{application.pk}/revise/', {
            'answers': answers_for(
                'emergency_relief', full_name='A B', email='a@b.test',
                phone='8675550143', emergency_type='housing',
                emergency_description='Furnace failed.', amount_requested='900',
                signature='A B', account_holder='A B', transit_number='12345',
                institution_number='001', account_number='9876543210'),
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)

        application.refresh_from_db()
        self.assertNotIn('account_number', application.answers)
        self.assertTrue(student.bank_accounts.filter(is_current=True).exists())


@override_settings(MEDIA_ROOT=MEDIA)
class DocumentAccessTests(TestCase):
    """The office must be able to open what was attached."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.student = make_user(email='owner@moreinfo.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker3@moreinfo.test')
        self.director = make_user(Role.DIRECTOR, 'director3@moreinfo.test')
        self.finance = make_user(Role.FINANCE, 'finance3@moreinfo.test')
        self.client = APIClient()

        self.client.force_authenticate(self.student)
        created = self.client.post(
            '/api/applications/',
            {'type': 'appeal', 'answers': appeal_answers()}, format='json')
        self.application = Application.objects.get(pk=created.data['id'])
        self.document = SupportingDocument.objects.create(
            application=self.application, owner=self.student,
            field_key='doc_supporting', file=a_pdf('transcript.pdf'),
            original_name='transcript.pdf')

    def open_as(self, user):
        self.client.force_authenticate(user)
        return self.client.get(f'/api/documents/{self.document.pk}/')

    def test_a_reviewer_can_open_it(self):
        self.assertEqual(self.open_as(self.worker).status_code, 200)

    def test_the_director_can_open_it(self):
        self.assertEqual(self.open_as(self.director).status_code, 200)

    def test_finance_can_open_it(self):
        self.assertEqual(self.open_as(self.finance).status_code, 200)

    def test_the_student_it_belongs_to_can_open_it(self):
        self.assertEqual(self.open_as(self.student).status_code, 200)

    def test_it_is_served_with_the_name_it_was_uploaded_under(self):
        """Stored under a generated uuid, so without this a reviewer opens
        `4f2a....pdf` and cannot tell one document from another."""
        response = self.open_as(self.worker)
        self.assertIn('transcript.pdf', response.headers.get('Content-Disposition', ''))

    def test_another_student_cannot_open_it(self):
        self.assertEqual(self.open_as(make_user(email='stranger@moreinfo.test'))
                         .status_code, 404)

    def test_a_stranger_is_not_told_whether_it_exists(self):
        """404 rather than 403: that a document exists is itself something a
        stranger should not learn."""
        self.assertEqual(self.open_as(make_user(email='stranger2@moreinfo.test'))
                         .status_code, 404)

    def test_signing_out_closes_it(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(f'/api/documents/{self.document.pk}/').status_code,
                      (401, 403))

    def test_the_application_lists_its_documents_for_the_office(self):
        """A reviewer was shown the text `document:12` and had no way to open
        it, which is the same as it never having been attached."""
        self.client.force_authenticate(self.worker)
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data
        names = {row['original_name'] for row in detail['documents']}
        self.assertIn('transcript.pdf', names)
        row = next(r for r in detail['documents'] if r['original_name'] == 'transcript.pdf')
        self.assertEqual(row['url'], f'/api/documents/{self.document.pk}/')

    def test_a_document_uploaded_before_the_application_existed_is_listed(self):
        """Uploads happen as the file is chosen, so they belong to the person
        until a submission claims them. Matched by the reference the answers
        carry, not by the foreign key alone."""
        loose = SupportingDocument.objects.create(
            owner=self.student, field_key='doc_supporting',
            file=a_pdf('letter.pdf'), original_name='letter.pdf')
        self.application.answers = {**self.application.answers,
                                    'doc_supporting': [f'document:{loose.pk}']}
        self.application.save(update_fields=['answers'])

        self.client.force_authenticate(self.worker)
        detail = self.client.get(f'/api/applications/{self.application.pk}/').data
        self.assertIn('letter.pdf', {row['original_name'] for row in detail['documents']})


@override_settings(MEDIA_ROOT=MEDIA)
class OwnerWritesNothingElseTests(TestCase):
    """Answering a request for information is the *only* write a student has.

    `IsStaffOrOwner` refused every unsafe method to an owner, because there was
    no legitimate write. There is one now — and opening it by method rather than
    by name would have handed the student `transition` and `price` on their own
    application at the same time: approving their own funding, and setting the
    amount.
    """

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.student = make_user(email='owner2@moreinfo.test')
        self.worker = make_user(Role.SUPPORT_WORKER, 'worker4@moreinfo.test')
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        created = self.client.post(
            '/api/applications/',
            {'type': 'appeal', 'answers': appeal_answers()}, format='json')
        self.application = Application.objects.get(pk=created.data['id'])
        # Put it in the one state where the student *does* have a write, so the
        # refusals below cannot pass merely because nothing is writable.
        self.client.force_authenticate(self.worker)
        self.client.post(f'/api/applications/{self.application.pk}/transition/',
                         {'action': 'info_requested', 'note': 'More please.'},
                         format='json')
        self.client.force_authenticate(self.student)

    def test_the_student_can_revise_in_this_state(self):
        """The control. Without it every refusal below could pass because the
        application was locked to everybody."""
        response = self.client.post(
            f'/api/applications/{self.application.pk}/revise/',
            {'answers': appeal_answers()}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_but_cannot_approve_their_own_application(self):
        response = self.client.post(
            f'/api/applications/{self.application.pk}/transition/',
            {'action': 'approved'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_nor_move_it_through_review(self):
        response = self.client.post(
            f'/api/applications/{self.application.pk}/transition/',
            {'action': 'info_provided'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_nor_price_it(self):
        response = self.client.post(f'/api/applications/{self.application.pk}/price/')
        self.assertEqual(response.status_code, 403)

    def test_nor_attach_it_to_another_account(self):
        response = self.client.post(
            f'/api/applications/{self.application.pk}/attach/',
            {'student_id': self.student.pk}, format='json')
        self.assertEqual(response.status_code, 403)


class OwnerPermissionTests(TestCase):
    """The permission itself, not the outcome it contributes to.

    `transition`, `price` and `attach` each carry their own role check, so a
    test that only watches the outcome passes whether or not `IsStaffOrOwner`
    is doing anything — it is guarded twice. This tests the layer directly, so
    that widening it is not silently free.
    """

    def setUp(self):
        self.student = make_user(email='perm@moreinfo.test')
        self.application = Application.objects.create(
            student=self.student, type=ApplicationType.APPEAL,
            stream=FundingStream.DGGR, schema_slug='appeal',
            status=ApplicationStatus.INFO_REQUESTED, answers={})

    def allowed(self, action, method='POST'):
        from accounts.api.permissions import IsStaffOrOwner

        request = type('R', (), {'user': self.student, 'method': method})()
        view = type('V', (), {'action': action})()
        return IsStaffOrOwner().has_object_permission(request, view, self.application)

    def test_the_owner_is_allowed_to_revise(self):
        self.assertTrue(self.allowed('revise'))

    def test_the_owner_is_allowed_to_read(self):
        self.assertTrue(self.allowed('retrieve', method='GET'))

    def test_the_owner_is_not_allowed_to_transition(self):
        """Opening this by method rather than by name would hand a student the
        power to approve their own funding."""
        self.assertFalse(self.allowed('transition'))

    def test_the_owner_is_not_allowed_to_price(self):
        self.assertFalse(self.allowed('price'))

    def test_the_owner_is_not_allowed_to_attach(self):
        self.assertFalse(self.allowed('attach'))

    def test_a_stranger_is_allowed_nothing(self):
        self.student = make_user(email='stranger3@moreinfo.test')
        self.assertFalse(self.allowed('revise'))
        self.assertFalse(self.allowed('retrieve', method='GET'))
