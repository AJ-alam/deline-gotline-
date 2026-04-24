"""
Comprehensive tests for the forms application.

Covers:
  - Form CRUD (admin-only write, any-auth read)
  - Form submission lifecycle (pending → reviewed → forwarded → accepted/rejected)
  - Submission notes
  - Eligibility check endpoint
  - Duplicate detection endpoint
  - Share link generation from SubmissionController
  - MidSemesterChange and ApplicationDeadline models
  - Serializer validation
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from programs.models import Program
from forms.models import (
    Form, FormField, FormSubmission, SubmissionAnswer,
    SubmissionNote, MidSemesterChange, ApplicationDeadline,
)
from forms.serializers import FormSerializer, FormSubmissionSerializer
from api.models import ShareableLink, Profile
from notifications.models import Notification

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, role='student', **kwargs):
    return User.objects.create_user(
        email=email, password='Test1234!',
        full_name=kwargs.pop('full_name', 'Test User'),
        role=role, **kwargs
    )


def make_admin(email='formadmin@test.com'):
    return User.objects.create_user(
        email=email, password='Admin1234!', full_name='Admin User',
        role='admin', is_staff=True,
    )


def make_director(email='dir@test.com'):
    return User.objects.create_user(
        email=email, password='Dir1234!', full_name='Director User', role='director',
    )


def make_program(creator):
    return Program.objects.create(title='Test Program', description='Desc', created_by=creator)


def make_form(creator, program=None, title='Test Form'):
    prog = program or make_program(creator)
    return Form.objects.create(title=title, program=prog, created_by=creator)


def make_form_with_fields(creator):
    form = make_form(creator)
    f1 = FormField.objects.create(form=form, label='Full Name', field_type='text', order=1)
    f2 = FormField.objects.create(form=form, label='Tuition', field_type='number', order=2)
    return form, [f1, f2]


def make_submission(form, student):
    return FormSubmission.objects.create(form=form, student=student)


def make_full_submission(form, student, field_answers=None):
    submission = FormSubmission.objects.create(form=form, student=student)
    for field in form.fields.all():
        answer = (field_answers or {}).get(field.label, 'test answer')
        SubmissionAnswer.objects.create(submission=submission, field=field, answer_text=answer)
    return submission


# ===========================================================================
# 1. Form CRUD Tests
# ===========================================================================

class FormCRUDTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.student = make_user('formstud@test.com')
        self.program = make_program(self.admin)

    def test_list_forms_authenticated(self):
        self.client.force_authenticate(user=self.student)
        resp = self.client.get('/api/forms/forms/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create_form(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            '/api/forms/forms/',
            {'title': 'New Form', 'program': self.program.id, 'purpose': 'application'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Form.objects.filter(title='New Form').count(), 1)

    def test_student_cannot_create_form(self):
        self.client.force_authenticate(user=self.student)
        resp = self.client.post(
            '/api/forms/forms/',
            {'title': 'Hack Form', 'program': self.program.id, 'purpose': 'application'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_form(self):
        form = make_form(self.admin, self.program)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            f'/api/forms/forms/{form.id}/',
            {'title': 'Updated Title'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        form.refresh_from_db()
        self.assertEqual(form.title, 'Updated Title')

    def test_admin_can_delete_form(self):
        form = make_form(self.admin, self.program)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'/api/forms/forms/{form.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_retrieve_form_includes_fields(self):
        form, fields = make_form_with_fields(self.admin)
        self.client.force_authenticate(user=self.student)
        resp = self.client.get(f'/api/forms/forms/{form.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('fields', resp.data)
        self.assertEqual(len(resp.data['fields']), 2)

    def test_unauthenticated_cannot_list_forms(self):
        resp = self.client.get('/api/forms/forms/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# 2. Form Submission Tests
# ===========================================================================

class FormSubmissionTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.student = make_user('substu@test.com')
        self.form, self.fields = make_form_with_fields(self.admin)

    def test_student_can_submit_form(self):
        self.client.force_authenticate(user=self.student)
        answers = [
            {'field_label': 'Full Name', 'answer_text': 'John Doe'},
            {'field_label': 'Tuition', 'answer_text': '4500'},
        ]
        resp = self.client.post(
            f'/api/forms/forms/{self.form.id}/submit/',
            {'answers': answers},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(FormSubmission.objects.filter(student=self.student, form=self.form).exists())

    def test_submission_creates_notification_for_student(self):
        self.client.force_authenticate(user=self.student)
        self.client.post(
            f'/api/forms/forms/{self.form.id}/submit/',
            {'answers': [{'field_label': 'Full Name', 'answer_text': 'Test'}]},
            format='json'
        )
        self.assertTrue(
            Notification.objects.filter(user=self.student, title='Application Received').exists()
        )

    def test_submission_default_status_is_pending(self):
        submission = make_submission(self.form, self.student)
        self.assertEqual(submission.status, 'pending')

    def test_student_can_view_own_submissions(self):
        make_submission(self.form, self.student)
        self.client.force_authenticate(user=self.student)
        resp = self.client.get('/api/forms/submissions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(len(resp.data['results']), 0)

    def test_student_cannot_see_other_submissions(self):
        other = make_user('subother@test.com')
        make_submission(self.form, other)
        self.client.force_authenticate(user=self.student)
        resp = self.client.get('/api/forms/submissions/')
        for sub in resp.data.get('results', []):
            self.assertEqual(sub['student'], self.student.id)

    def test_admin_can_see_all_submissions(self):
        make_submission(self.form, self.student)
        other = make_user('subother2@test.com')
        make_submission(self.form, other)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/forms/submissions/')
        self.assertGreaterEqual(len(resp.data['results']), 2)


# ===========================================================================
# 3. Submission Status Lifecycle Tests
# ===========================================================================

class SubmissionStatusTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.director = make_director()
        self.student = make_user('lifecycle@test.com')
        form = make_form(self.admin)
        self.submission = make_submission(form, self.student)

    def test_admin_can_review_submission(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'reviewed'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'reviewed')
        self.assertIsNotNone(self.submission.reviewed_at)
        self.assertEqual(self.submission.reviewed_by, self.admin)

    def test_admin_can_forward_submission(self):
        self.client.force_authenticate(user=self.admin)
        self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'reviewed'}, format='json'
        )
        resp = self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'forwarded'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'forwarded')
        self.assertIsNotNone(self.submission.forwarded_at)

    def test_director_can_accept_submission(self):
        self.client.force_authenticate(user=self.director)
        resp = self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'accepted', 'decision_notes': 'Looks great'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'accepted')
        self.assertIsNotNone(self.submission.decided_at)

    def test_director_can_reject_submission(self):
        self.client.force_authenticate(user=self.director)
        resp = self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'rejected', 'reason': 'Missing documents'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'rejected')

    def test_acceptance_notifies_student(self):
        self.client.force_authenticate(user=self.director)
        self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'accepted'}, format='json'
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.student,
                title__icontains='Application Update'
            ).exists()
        )

    def test_student_cannot_update_status(self):
        self.client.force_authenticate(user=self.student)
        resp = self.client.put(
            f'/api/forms/submissions/{self.submission.id}/status/',
            {'status': 'accepted'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 4. Submission Note Tests
# ===========================================================================

class SubmissionNoteTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.student = make_user('notestu@test.com')
        form = make_form(self.admin)
        self.submission = make_submission(form, self.student)

    def test_admin_can_add_note(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/notes/',
            {'text': 'Internal review note'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(
            SubmissionNote.objects.filter(submission=self.submission, author=self.admin).exists()
        )

    def test_add_note_requires_text(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/notes/',
            {'text': ''},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_cannot_add_note(self):
        self.client.force_authenticate(user=self.student)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/notes/',
            {'text': 'Student note attempt'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 5. Eligibility Check Endpoint Tests
# ===========================================================================

class EligibilityCheckEndpointTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.student = make_user('eligstu@test.com')
        Profile.objects.create(
            user=self.student, indian_status='Status 1', beneficiary_number='BN777',
        )
        form = make_form(self.admin)
        self.submission = make_submission(form, self.student)

    def test_admin_can_check_eligibility(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/check-eligibility/'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertIn('eligible_streams', data)
        self.assertIn('ineligible_streams', data)

    def test_director_can_check_eligibility(self):
        director = make_director()
        self.client.force_authenticate(user=director)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/check-eligibility/'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ===========================================================================
# 6. Duplicate Detection Endpoint Tests
# ===========================================================================

class DuplicateDetectionEndpointTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.student = make_user('dupstu@test.com')
        form = make_form(self.admin)
        self.submission = make_submission(form, self.student)

    def test_admin_can_check_duplicates(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/check-duplicates/'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertIn('is_flagged', data)
        self.assertIn('requires_review', data)

    def test_admin_can_mark_legitimate(self):
        from api.models import DuplicateDetectionLog
        DuplicateDetectionLog.objects.create(
            submission=self.submission, identifier_hash='test_hash', is_flagged=True,
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/mark-legitimate/',
            {'notes': 'Verified identity in person'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_mark_duplicate(self):
        from api.models import DuplicateDetectionLog
        DuplicateDetectionLog.objects.create(
            submission=self.submission, identifier_hash='dup_hash', is_flagged=True,
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/mark-duplicate/',
            {'notes': 'Confirmed duplicate via cross-referencing'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ===========================================================================
# 7. Share Link Tests (Submission)
# ===========================================================================

class SubmissionShareTests(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.student = make_user('sharestu@test.com')
        form = make_form(self.admin)
        self.submission = make_submission(form, self.student)

    def test_admin_can_generate_share_link(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/share/'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('token', resp.data['data'])
        self.assertTrue(
            ShareableLink.objects.filter(submission=self.submission).exists()
        )

    def test_student_cannot_generate_share_link(self):
        self.client.force_authenticate(user=self.student)
        resp = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/share/'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 8. Model Tests
# ===========================================================================

class FormModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='fmod@test.com', password='p', full_name='F Mod'
        )
        self.program = make_program(self.user)

    def test_form_str(self):
        form = Form.objects.create(
            title='Test Form', program=self.program,
            purpose='application', created_by=self.user
        )
        self.assertIn('Test Form', str(form))
        self.assertIn('application', str(form))

    def test_form_field_ordering(self):
        form = make_form(self.user)
        FormField.objects.create(form=form, label='B', field_type='text', order=2)
        FormField.objects.create(form=form, label='A', field_type='text', order=1)
        fields = list(form.fields.all())
        self.assertEqual(fields[0].label, 'A')
        self.assertEqual(fields[1].label, 'B')

    def test_submission_str(self):
        form = make_form(self.user)
        submission = FormSubmission.objects.create(form=form, student=self.user)
        result = str(submission)
        self.assertIn('fmod@test.com', result)

    def test_submission_note_ordering(self):
        form = make_form(self.user)
        submission = FormSubmission.objects.create(form=form, student=self.user)
        SubmissionNote.objects.create(submission=submission, author=self.user, text='Note A')
        SubmissionNote.objects.create(submission=submission, author=self.user, text='Note B')
        notes = list(submission.notes.all())
        # Ordered by -created_at (newest first)
        self.assertEqual(notes[0].text, 'Note B')


class MidSemesterChangeModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='midchg@test.com', password='p', full_name='Mid Change'
        )
        prog = make_program(self.user)
        form = make_form(self.user, prog)
        self.submission = FormSubmission.objects.create(form=form, student=self.user)

    def test_create_mid_semester_change(self):
        chg = MidSemesterChange.objects.create(
            submission=self.submission,
            change_type='enrollment_status',
            old_value='Full-Time',
            new_value='Part-Time',
            submitted_by=self.user,
        )
        self.assertEqual(chg.status, 'pending')
        self.assertIn('enrollment_status', str(chg))

    def test_all_change_types_valid(self):
        for ct, _ in MidSemesterChange.CHANGE_TYPE_CHOICES:
            chg = MidSemesterChange.objects.create(
                submission=self.submission,
                change_type=ct,
                old_value='old',
                new_value='new',
                submitted_by=self.user,
            )
            self.assertEqual(chg.change_type, ct)


class ApplicationDeadlineModelTests(TestCase):

    def test_create_deadline(self):
        dl = ApplicationDeadline.objects.create(
            funding_stream='PSSSP',
            semester='Fall 2025',
            deadline_date=timezone.now() + timezone.timedelta(days=30),
        )
        self.assertIn('PSSSP', str(dl))
        self.assertIn('Fall 2025', str(dl))

    def test_unique_together_funding_stream_semester(self):
        from django.db import IntegrityError
        ApplicationDeadline.objects.create(
            funding_stream='DGGR',
            semester='Winter 2026',
            deadline_date=timezone.now() + timezone.timedelta(days=60),
        )
        with self.assertRaises(IntegrityError):
            ApplicationDeadline.objects.create(
                funding_stream='DGGR',
                semester='Winter 2026',
                deadline_date=timezone.now() + timezone.timedelta(days=90),
            )

    def test_all_funding_stream_choices_valid(self):
        for i, (stream, _) in enumerate(ApplicationDeadline.STREAM_CHOICES):
            dl = ApplicationDeadline.objects.create(
                funding_stream=stream,
                semester=f'Semester {i}',
                deadline_date=timezone.now() + timezone.timedelta(days=i + 1),
            )
            self.assertEqual(dl.funding_stream, stream)


# ===========================================================================
# 9. Serializer Tests
# ===========================================================================

class FormSerializerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='sertest@test.com', password='p', full_name='Ser Test'
        )
        self.program = make_program(self.user)

    def test_form_serializer_valid_data(self):
        data = {
            'title': 'My Form',
            'program': self.program.id,
            'purpose': 'application',
        }
        serializer = FormSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_form_serializer_invalid_purpose(self):
        data = {
            'title': 'My Form',
            'program': self.program.id,
            'purpose': 'invalid_purpose',
        }
        serializer = FormSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class FormSubmissionSerializerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='subsertest@test.com', password='p', full_name='Sub Ser'
        )
        prog = make_program(self.user)
        self.form = make_form(self.user, prog)

    def test_serializer_includes_form_title(self):
        submission = FormSubmission.objects.create(form=self.form, student=self.user)
        serializer = FormSubmissionSerializer(submission)
        self.assertEqual(serializer.data['form_title'], self.form.title)

    def test_serializer_includes_student_name(self):
        submission = FormSubmission.objects.create(form=self.form, student=self.user)
        serializer = FormSubmissionSerializer(submission)
        self.assertEqual(serializer.data['student_name'], 'Sub Ser')
