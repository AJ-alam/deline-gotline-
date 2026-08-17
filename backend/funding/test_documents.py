"""Attaching documents to an application.

SupportingDocument was a model with a FileField and no endpoint: the `doc_*`
answers were text saying 'provided' and nothing was ever attached. An
application that cannot carry a transcript cannot be assessed.

These cover the part that matters about accepting files from the public — what
is allowed, how big, what it is called on disk, and whose it is.
"""

import io
import shutil
import tempfile
from pathlib import PurePath

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.api.document_views import MAX_BYTES
from funding.models import (
    Application, ApplicationType, FundingStream, SupportingDocument,
)

MEDIA = tempfile.mkdtemp()


def a_pdf(name='transcript.pdf', size=1024):
    return SimpleUploadedFile(name, b'%PDF-1.4\n' + b'x' * size,
                              content_type='application/pdf')


def make_user(role=Role.STUDENT, email=None):
    return User.objects.create_user(
        email or f'{role}@docs.test', 'pw12345678',
        first_name='Test', last_name='Person', role=role, is_deline_beneficiary=True, is_indian_act_registered=True)


@override_settings(MEDIA_ROOT=MEDIA)
class UploadTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.student = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def upload(self, **extra):
        payload = {'file': a_pdf(), 'field_key': 'doc_transcript'}
        payload.update(extra)
        return self.client.post('/api/documents/', payload, format='multipart')

    def test_a_student_can_attach_a_document(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['field_key'], 'doc_transcript')
        self.assertEqual(SupportingDocument.objects.count(), 1)

    def test_the_answer_gets_a_reference_not_a_file(self):
        """The schema stores a pointer; the file lives in its own table."""
        response = self.upload()
        document = SupportingDocument.objects.get()
        self.assertEqual(response.data['reference'], f'document:{document.pk}')

    def test_the_original_name_is_kept_as_a_label(self):
        self.upload(file=a_pdf('My Transcript 2026.pdf'))
        self.assertEqual(SupportingDocument.objects.get().original_name,
                         'My Transcript 2026.pdf')

    def test_the_stored_name_is_not_the_one_the_browser_sent(self):
        """A file called '../../settings.py' is the whole reason for this."""
        self.upload(file=a_pdf('../../../etc/passwd.pdf'))
        stored = SupportingDocument.objects.get().file.name

        self.assertNotIn('..', stored)
        self.assertNotIn('passwd', stored)
        self.assertTrue(stored.endswith('.pdf'))

    def test_a_double_extension_is_refused_outright(self):
        """Refusing beats accepting and renaming: nothing lands on disk at all."""
        response = self.upload(file=SimpleUploadedFile(
            'invoice.pdf.exe', b'%PDF-1.4 x', content_type='application/pdf'))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SupportingDocument.objects.exists())

    def test_an_executable_is_refused(self):
        response = self.upload(file=SimpleUploadedFile(
            'payload.exe', b'MZ\x90\x00', content_type='application/x-msdownload'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SupportingDocument.objects.exists())

    def test_an_executable_wearing_a_pdf_content_type_is_refused(self):
        """The browser's content type is a claim; the name has to agree."""
        response = self.upload(file=SimpleUploadedFile(
            'payload.exe', b'MZ\x90\x00', content_type='application/pdf'))
        self.assertEqual(response.status_code, 400)

    def test_a_photograph_of_a_document_is_accepted(self):
        """Most applicants have a phone, not a scanner."""
        response = self.upload(file=SimpleUploadedFile(
            'status-card.jpg', b'\xff\xd8\xff' + b'x' * 500, content_type='image/jpeg'))
        self.assertEqual(response.status_code, 201)

    def test_something_too_large_is_refused_with_a_useful_message(self):
        oversized = SimpleUploadedFile(
            'huge.pdf', b'%PDF-1.4' + b'x' * (MAX_BYTES + 1),
            content_type='application/pdf')
        response = self.upload(file=oversized)

        self.assertEqual(response.status_code, 400)
        self.assertIn('limit', str(response.data['file']).lower())

    def test_an_empty_file_is_refused(self):
        response = self.upload(file=SimpleUploadedFile(
            'empty.pdf', b'', content_type='application/pdf'))
        self.assertEqual(response.status_code, 400)

    def test_an_anonymous_upload_is_accepted_and_owned_by_nobody(self):
        """Deliberately reversed.

        This asserted a 401. Two awards are claimable with no account and the
        graduation award requires proof of completion, so the login requirement
        did not protect anything — it made that form impossible to submit. The
        control rendered, every request was refused, and a required answer could
        never be given.

        What bounds an anonymous upload is in `GuestUploadTests`: the size cap,
        the type allowlist, the generated filename, the refusal to attach to
        anybody's application, and a throttle. Not the login.
        """
        self.client.force_authenticate(None)
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(SupportingDocument.objects.get(pk=response.data['id']).owner)


@override_settings(MEDIA_ROOT=MEDIA)
class OwnershipTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.student = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def test_a_document_may_be_uploaded_before_the_application_exists(self):
        """The form is filled in over several sittings."""
        response = self.client.post('/api/documents/',
                                    {'file': a_pdf(), 'field_key': 'doc_transcript'},
                                    format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(SupportingDocument.objects.get().application)
        self.assertEqual(SupportingDocument.objects.get().owner, self.student)

    def test_it_can_be_attached_to_ones_own_application(self):
        application = Application.objects.create(
            student=self.student, type='admission', stream=FundingStream.PSSSP,
            schema_slug='admission', answers={})

        response = self.client.post(
            '/api/documents/',
            {'file': a_pdf(), 'field_key': 'doc_transcript',
             'application': application.pk},
            format='multipart')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(SupportingDocument.objects.get().application, application)

    def test_it_cannot_be_attached_to_someone_elses(self):
        theirs = Application.objects.create(
            student=make_user(email='other@docs.test'), type='admission',
            stream=FundingStream.PSSSP, schema_slug='admission', answers={})

        response = self.client.post(
            '/api/documents/',
            {'file': a_pdf(), 'field_key': 'doc_transcript', 'application': theirs.pk},
            format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SupportingDocument.objects.exists())


@override_settings(MEDIA_ROOT=MEDIA)
class GuestUploadTests(TestCase):
    """Uploading with no account.

    Two awards are claimable without one, and the graduation award requires
    proof of completion. Requiring a login here protected nothing and made that
    form unsubmittable: the control rendered, every request was refused, and the
    required answer could never be given.
    """

    def setUp(self):
        self.client = APIClient()

    def upload(self, **extra):
        return self.client.post(
            '/api/documents/',
            {'file': a_pdf('parchment.pdf'), 'field_key': 'doc_proof_of_completion',
             **extra},
            format='multipart')

    def test_someone_with_no_account_can_attach_their_certificate(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['reference'].startswith('document:'))

    def test_it_belongs_to_nobody_until_a_claim_carries_it(self):
        response = self.upload()
        document = SupportingDocument.objects.get(pk=response.data['id'])
        self.assertIsNone(document.owner)
        self.assertIsNone(document.application)

    def test_the_same_refusals_still_apply(self):
        """Open does not mean unchecked. The size cap, the type allowlist and
        the generated filename are what bound this, not the login."""
        response = self.client.post(
            '/api/documents/',
            {'file': SimpleUploadedFile('payload.exe', b'MZ', content_type='application/x-msdownload'),
             'field_key': 'doc_proof_of_completion'},
            format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_the_stored_name_is_never_the_one_that_was_sent(self):
        response = self.client.post(
            '/api/documents/',
            {'file': a_pdf('../../settings.pdf'), 'field_key': 'doc_proof_of_completion'},
            format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        document = SupportingDocument.objects.get(pk=response.data['id'])
        self.assertNotIn('..', document.file.name)
        self.assertTrue(document.file.name.endswith('.pdf'))

    def test_an_anonymous_caller_cannot_attach_to_an_application(self):
        """Naming somebody else's application is how a stranger's file lands on
        a claim under review."""
        student = User.objects.create_user(
            'owner@test.com', 'pw12345678', first_name='O', last_name='Wner',
            role=Role.STUDENT, is_deline_beneficiary=True, is_indian_act_registered=True)
        theirs = Application.objects.create(
            student=student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission', answers={})

        response = self.upload(application=theirs.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(theirs.documents.count(), 0)
