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
from rest_framework.test import APITestCase, APIClient
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


# Minimum policy configuration required to price a generic submission. Accepting
# a submission now refuses to write an award when a setting it depends on is
# absent, so any test that walks the acceptance path has to seed these — the
# same way a real deployment must before it can approve anything.
BASE_POLICY_SETTINGS = [
    ('system_config', 'book_allowance', Decimal('500.00')),
    ('psssp_tuition', 'max_per_semester', Decimal('7000.00')),
    ('psssp_living', 'fulltime_no_dependents', Decimal('1800.00')),
    ('eligibility_rules', 'fulltime_min_load_percent', Decimal('60')),
]


def seed_base_policies():
    from api.models import PolicySetting
    for section, field_key, value in BASE_POLICY_SETTINGS:
        PolicySetting.objects.get_or_create(
            section=section, field_key=field_key,
            defaults=dict(field_label=field_key, value=value, unit='$'),
        )


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
        # Forms list is public so guest applicants can discover form templates
        resp = self.client.get('/api/forms/forms/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


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
        seed_base_policies()
        self.admin = make_admin()
        self.director = make_director()
        self.student = make_user('lifecycle@test.com')
        form = make_form(self.admin)
        self.submission = make_submission(form, self.student)
        # Pre-populate reviewed/forwarded state so director's queryset includes this submission
        self.submission.status = 'forwarded'
        self.submission.reviewed_at = timezone.now()
        self.submission.reviewed_by = self.admin
        self.submission.forwarded_at = timezone.now()
        self.submission.forwarded_by = self.admin
        self.submission.save()

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
        # Director's queryset only shows forwarded/accepted/rejected
        self.submission.status = 'forwarded'
        self.submission.save()

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
        self.assertIn('Enrollment Status', str(chg))

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


# ===========================================================================
# Residency Declaration Mismatch
# ===========================================================================

class ResidencyMismatchServiceTests(TestCase):
    """Unit-level checks on the declared-residency vs address comparison."""

    def _check(self, declared, **address):
        from api.services.residency_service import check_residency_mismatch
        return check_residency_mismatch(declared, **address)

    def test_non_nwt_declaration_with_nwt_address_is_flagged(self):
        result = self._check('outside', province='NT', town_city='Deline', postal_code='X0E 0G0')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['signals']), 3)

    def test_non_nwt_declaration_with_nwt_postal_code_only_is_flagged(self):
        result = self._check('outside', province='Alberta', town_city='Edmonton', postal_code='X1A2B3')
        self.assertIsNotNone(result)

    def test_nwt_community_in_free_text_address_is_flagged(self):
        result = self._check('other', mailing_address='12 Main St, Yellowknife, NT')
        self.assertIsNotNone(result)

    def test_matching_declaration_and_address_is_not_flagged(self):
        self.assertIsNone(self._check('outside', province='ON', town_city='Toronto', postal_code='M5V 1A1'))

    def test_nwt_resident_with_nwt_address_is_not_flagged(self):
        self.assertIsNone(self._check('nwt', province='NT', town_city='Deline', postal_code='X0E 0G0'))

    def test_nunavut_postal_code_is_not_treated_as_nwt(self):
        self.assertIsNone(self._check('outside', postal_code='X0A 0H0'))

    def test_declared_resident_with_southern_address_is_flagged_for_review(self):
        result = self._check('nwt', province='AB', town_city='Edmonton', postal_code='T5J 0N3')
        self.assertIsNotNone(result)
        self.assertEqual(result['kind'], 'declared_resident')

    def test_declared_resident_living_where_they_study_is_not_flagged(self):
        self.assertIsNone(self._check(
            'nwt', province='AB', town_city='Edmonton', postal_code='T5J 0N3',
            institution_location='Edmonton, Alberta',
        ))

    def test_declared_resident_with_nwt_address_is_not_flagged(self):
        self.assertIsNone(self._check('nwt', province='NT', town_city='Deline', postal_code='X0E 0G0'))

    def test_yukon_is_not_the_nwt(self):
        result = self._check('nwt', province='YT', postal_code='Y1A 1A1')
        self.assertIsNotNone(result)


class EditSubmittedAnswersTests(APITestCase):
    """SSW/admin correction of details a student submitted on a form."""

    URL = '/api/forms/submissions/{}/answers/'

    def setUp(self):
        self.admin = make_admin('editadmin@test.com')
        self.ssw = make_user('ssw@test.com', role='ssw', full_name='Support Worker')
        self.director = make_director('editdir@test.com')
        self.student = make_user('editstu@test.com')
        self.form = make_form(self.admin, title='Form A: Admission Application')
        FormField.objects.create(form=self.form, label='Transit Number', field_type='text')
        FormField.objects.create(form=self.form, label='City', field_type='text')
        self.submission = make_full_submission(self.form, self.student, {
            'Transit Number': '00123', 'City': 'Deline',
        })
        self.answer = self.submission.answers.get(field__label='Transit Number')

    def _patch(self, user, payload):
        self.client.force_authenticate(user=user)
        return self.client.patch(self.URL.format(self.submission.id), payload, format='json')

    def test_ssw_can_correct_an_answer(self):
        resp = self._patch(self.ssw, {
            'answers': [{'id': self.answer.id, 'answer_text': '00456'}],
            'reason': 'Corrected against the void cheque',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.answer_text, '00456')

    def test_admin_can_correct_an_answer(self):
        resp = self._patch(self.admin, {
            'answers': [{'field_label': 'City', 'answer_text': 'Tulita'}],
            'reason': 'Student moved communities',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.submission.answers.get(field__label='City').answer_text, 'Tulita'
        )

    def test_director_cannot_edit_submitted_details(self):
        resp = self._patch(self.director, {
            'answers': [{'id': self.answer.id, 'answer_text': '99999'}],
            'reason': 'Trying to edit',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.answer_text, '00123')

    def test_student_cannot_edit_their_own_submitted_details(self):
        resp = self._patch(self.student, {
            'answers': [{'id': self.answer.id, 'answer_text': '99999'}],
            'reason': 'Fixing my typo',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_reason_is_required(self):
        resp = self._patch(self.ssw, {
            'answers': [{'id': self.answer.id, 'answer_text': '00456'}],
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.answer_text, '00123')

    def test_missing_field_is_added_to_the_record(self):
        resp = self._patch(self.ssw, {
            'answers': [{'field_label': 'Postal Code', 'answer_text': 'X0E 0G0'}],
            'reason': 'Student left the postal code blank',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.submission.answers.get(field__label='Postal Code').answer_text, 'X0E 0G0'
        )

    def test_change_is_audited_and_noted(self):
        from api.models import AuditLog
        self._patch(self.ssw, {
            'answers': [{'id': self.answer.id, 'answer_text': '00456'}],
            'reason': 'Corrected against the void cheque',
        })
        note = self.submission.notes.first()
        self.assertIsNotNone(note)
        self.assertIn('00123', note.text)
        self.assertIn('00456', note.text)
        self.assertTrue(AuditLog.objects.filter(performed_by=self.ssw).exists())

    def test_student_is_notified_of_the_correction(self):
        self._patch(self.ssw, {
            'answers': [{'id': self.answer.id, 'answer_text': '00456'}],
            'reason': 'Corrected against the void cheque',
        })
        self.assertTrue(
            Notification.objects.filter(
                user=self.student, title='Your application details were corrected'
            ).exists()
        )

    def test_no_op_edit_is_rejected(self):
        resp = self._patch(self.ssw, {
            'answers': [{'id': self.answer.id, 'answer_text': '00123'}],
            'reason': 'No actual change',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_editing_is_blocked_after_finance_dispatch(self):
        self.submission.finance_sent_at = timezone.now()
        self.submission.save(update_fields=['finance_sent_at'])
        resp = self._patch(self.ssw, {
            'answers': [{'id': self.answer.id, 'answer_text': '00456'}],
            'reason': 'Too late',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.answer_text, '00123')

    def test_correction_reruns_the_residency_check(self):
        self.student.province_of_residence = 'outside'
        self.student.save(update_fields=['province_of_residence'])
        self._patch(self.ssw, {
            'answers': [{'field_label': 'Postal Code', 'answer_text': 'X0E 0G0'}],
            'reason': 'Adding the postal code from the void cheque',
        })
        self.submission.refresh_from_db()
        self.assertIn('Residency mismatch', self.submission.residency_flag or '')


class ApprovedBreakdownTests(TestCase):
    """
    An approved total must always be explainable. The student used to receive
    only "APPROVED for $X" with no indication of what made up the figure.
    """

    def setUp(self):
        self.admin = make_admin('breakdownadmin@test.com')
        self.student = make_user('breakdownstu@test.com', full_name='Break Down')
        self.form = make_form(self.admin, title='Form A: Admission Application')
        self.submission = make_submission(self.form, self.student)

    def test_uses_the_breakdown_staff_approved(self):
        from api.services.form_service import FormService
        self.submission.office_use_data = {'funding_breakdown': [
            {'label': 'Tuition (PSSSP)', 'amount': 4200},
            {'label': 'Living Allowance (PSSSP)', 'amount': 4800},
            {'label': 'Empty row', 'amount': 0},
        ]}
        self.submission.amount = Decimal('9000')
        self.submission.save()

        rows = FormService.approved_breakdown(self.submission)
        self.assertEqual([r['name'] for r in rows],
                         ['Tuition (PSSSP)', 'Living Allowance (PSSSP)'])
        self.assertEqual(sum(r['amount'] for r in rows), 9000)

    def test_falls_back_to_a_single_line_rather_than_nothing(self):
        from api.services.form_service import FormService
        self.submission.amount = Decimal('1500')
        self.submission.save()
        rows = FormService.approved_breakdown(self.submission)
        self.assertTrue(rows)
        self.assertEqual(sum(r['amount'] for r in rows), 1500)

    def test_approval_notification_lists_the_categories(self):
        from api.services.form_service import FormService
        self.submission.office_use_data = {'funding_breakdown': [
            {'label': 'Tuition (PSSSP)', 'amount': 4200},
            {'label': 'Living Allowance (PSSSP)', 'amount': 4800},
        ]}
        self.submission.amount = Decimal('9000')
        self.submission.save()

        FormService._send_status_notification(self.submission, 'accepted')

        note = Notification.objects.filter(user=self.student).order_by('-id').first()
        self.assertIsNotNone(note)
        self.assertIn('Tuition (PSSSP)', note.message)
        self.assertIn('4,200.00', note.message)
        self.assertIn('Living Allowance (PSSSP)', note.message)

    def test_student_can_see_the_approved_breakdown(self):
        self.submission.office_use_data = {'funding_breakdown': [
            {'label': 'Tuition (PSSSP)', 'amount': 4200, 'note': 'Registrar-confirmed program cost'},
        ]}
        self.submission.save()

        client = APIClient()
        client.force_authenticate(user=self.student)
        resp = client.get(f'/api/forms/submissions/{self.submission.id}/funding-breakdown/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        self.assertEqual(data['source'], 'approved')
        self.assertEqual(data['categories'][0]['category'], 'Tuition (PSSSP)')
        self.assertEqual(data['categories'][0]['rule'], 'Registrar-confirmed program cost')


class ResidencyScanCommandTests(TestCase):
    """The backfill command must be a no-op until --apply is passed."""

    def setUp(self):
        self.admin = make_admin('scanadmin@test.com')
        self.form = make_form(self.admin, title='Form A: Admission Application')
        for label in ('City', 'Province', 'Postal Code'):
            FormField.objects.create(form=self.form, label=label, field_type='text')
        self.student = make_user('scanstu@test.com', province_of_residence='outside')
        self.submission = make_full_submission(self.form, self.student, {
            'City': 'Deline', 'Province': 'NT', 'Postal Code': 'X0E 0G0',
        })

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('scan_residency_flags', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_but_does_not_write(self):
        output = self._run()
        self.assertIn('Flagged:   1', output)
        self.assertIn('Dry run', output)
        self.submission.refresh_from_db()
        self.assertIsNone(self.submission.residency_flag)

    def test_apply_writes_the_flag(self):
        self._run('--apply')
        self.submission.refresh_from_db()
        self.assertIn('Residency mismatch', self.submission.residency_flag)

    def test_backfill_does_not_notify_unless_asked(self):
        self._run('--apply')
        self.assertFalse(
            Notification.objects.filter(title='Residency Declaration Mismatch').exists()
        )

    def test_notify_flag_sends_to_staff(self):
        self._run('--apply', '--notify')
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin, title='Residency Declaration Mismatch'
            ).exists()
        )

    def test_clear_resolved_removes_a_stale_flag(self):
        self.submission.residency_flag = 'Residency mismatch: stale'
        self.submission.save(update_fields=['residency_flag'])
        self.student.province_of_residence = 'nwt'
        self.student.save(update_fields=['province_of_residence'])

        self._run('--apply', '--clear-resolved')
        self.submission.refresh_from_db()
        self.assertIsNone(self.submission.residency_flag)


class ResidencyMismatchSubmissionTests(APITestCase):
    """The flag must be raised when the contradicting address arrives on a form."""

    def setUp(self):
        self.admin = make_admin('resadmin@test.com')
        self.form = make_form(self.admin, title='Form A: Admission Application')
        for label in ('Address', 'City', 'Province', 'Postal Code'):
            FormField.objects.create(form=self.form, label=label, field_type='text')

    def _submit(self, student, city, province, postal_code):
        self.client.force_authenticate(user=student)
        return self.client.post(f'/api/forms/forms/{self.form.id}/submit/', {
            'answers': [
                {'field_label': 'Address', 'answer_text': '1 Main St'},
                {'field_label': 'City', 'answer_text': city},
                {'field_label': 'Province', 'answer_text': province},
                {'field_label': 'Postal Code', 'answer_text': postal_code},
            ],
        }, format='json')

    def test_declared_non_resident_with_nwt_address_sets_flag(self):
        student = make_user('outsider@test.com', province_of_residence='outside')
        resp = self._submit(student, 'Deline', 'NT', 'X0E 0G0')
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))

        submission = FormSubmission.objects.filter(student=student).first()
        self.assertIsNotNone(submission.residency_flag)
        self.assertIn('Residency mismatch', submission.residency_flag)

    def test_declared_non_resident_with_southern_address_has_no_flag(self):
        student = make_user('southerner@test.com', province_of_residence='outside')
        self._submit(student, 'Calgary', 'AB', 'T2P 1J9')

        submission = FormSubmission.objects.filter(student=student).first()
        self.assertIsNone(submission.residency_flag)

    def test_declared_nwt_resident_with_nwt_address_has_no_flag(self):
        student = make_user('resident@test.com', province_of_residence='nwt')
        self._submit(student, 'Deline', 'NT', 'X0E 0G0')

        submission = FormSubmission.objects.filter(student=student).first()
        self.assertIsNone(submission.residency_flag)

    def test_staff_are_notified_of_the_mismatch(self):
        student = make_user('notify-outsider@test.com', province_of_residence='outside')
        self._submit(student, 'Deline', 'NT', 'X0E 0G0')

        self.assertTrue(
            Notification.objects.filter(
                user=self.admin, title='Residency Declaration Mismatch'
            ).exists()
        )
