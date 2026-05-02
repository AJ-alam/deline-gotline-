import logging
from rest_framework import viewsets, permissions, status, decorators, parsers
from django.http import HttpResponse

from forms.models import Form, FormSubmission, SubmissionNote
from forms.serializers import FormSerializer, FormSubmissionSerializer, SubmissionNoteSerializer
from api.services.form_service import FormService
from api.services.eligibility_service import EligibilityService
from api.services.duplicate_detection_service import DuplicateDetectionService
from api.utils.responses import api_response
from api.utils.pdf_generator import FormPDFGenerator
from api.models import ShareableLink
from users.permissions import IsAdminUser, IsOwnerOrAdmin
from django.utils import timezone
import uuid

logger = logging.getLogger(__name__)

class FormController(viewsets.ModelViewSet):

    queryset = Form.objects.all()
    serializer_class = FormSerializer
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        if self.action == 'submit':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=['get'], url_path='download-pdf')
    def download_pdf(self, request, pk=None):
        """
        Download a blank PDF template of the form for manual completion
        """
        form = self.get_object()
        
        try:
            # Generate PDF
            pdf_content = FormPDFGenerator.generate_form_template(form)
            
            # Create response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            filename = f"{form.title.replace(' ', '_')}_Form.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Log the download
            from api.models import AuditLog
            AuditLog.objects.create(
                action=f"Downloaded PDF template for form: {form.title}",
                performed_by=request.user if request.user.is_authenticated else None,
                details=f"Form ID: {form.id}"
            )
            
            return response
        except Exception as e:
            logger.error(f"Error generating PDF for form {form.id}: {str(e)}", exc_info=True)
            return api_response(False, None, f"Failed to generate PDF: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @decorators.action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        form = self.get_object()
        data = request.data.dict() if hasattr(request.data, 'dict') else request.data.copy()
        data['form'] = form.id

        # Check if this is Form A and if user already has a non-rejected submission
        if request.user.is_authenticated:
            form_title_lower = form.title.lower()
            is_form_a = 'form a' in form_title_lower or 'forma' in form_title_lower or 'psssp' in form_title_lower or 'admission' in form_title_lower
            
            if is_form_a:
                # Check for existing Form A submissions that are not rejected
                existing_submission = FormSubmission.objects.filter(
                    student=request.user,
                    form=form
                ).exclude(status='rejected').first()
                
                if existing_submission:
                    logger.warning(f"User {request.user.email} attempted to resubmit Form A (existing submission: {existing_submission.id})")
                    return api_response(
                        False, 
                        {'existing_submission_id': existing_submission.id},
                        "You have already submitted this form. Only one Form A submission is allowed unless your previous submission was rejected.",
                        status.HTTP_400_BAD_REQUEST
                    )

        # Map FormData indexed answers
        if 'answers[0]field_label' in data:
            answers = []
            i = 0
            while f'answers[{i}]field_label' in data:
                ans = {
                    'field_label': data.get(f'answers[{i}]field_label'),
                    'answer_text': data.get(f'answers[{i}]answer_text'),
                }
                file_key = f'answers[{i}]answer_file'
                if file_key in request.FILES:
                    ans['answer_file'] = request.FILES[file_key]
                answers.append(ans)
                i += 1
            data['answers'] = answers

        logger.debug(f"Form submission attempt for form {form.id} by user {request.user.email if request.user.is_authenticated else 'Anonymous'}")
        serializer = FormSubmissionSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            try:
                user = request.user if request.user.is_authenticated else None
                submission = serializer.save(form=form, student=user)
                logger.info(f"Successfully created submission {submission.id} for user {user.email if user else 'Anonymous'}")
                FormService.send_submission_notifications(submission)
                # Reload with prefetch to avoid N+1 in response serialization
                submission = FormSubmission.objects.select_related(
                    'form', 'student', 'reviewed_by', 'forwarded_by', 'decided_by'
                ).prefetch_related('answers__field', 'notes__author').get(pk=submission.pk)
                return api_response(True, FormSubmissionSerializer(submission, context={'request': request}).data, "Form submitted successfully", status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error during submission save/notify: {str(e)}", exc_info=True)
                return api_response(False, str(e), "Internal error during submission", status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.warning(f"Submission validation failed for user {request.user.email}: {serializer.errors}")
        logger.debug(f"Failed data: {data}")
        return api_response(False, serializer.errors, "Submission failed", status.HTTP_400_BAD_REQUEST)


class SubmissionController(viewsets.ModelViewSet):
    queryset = FormSubmission.objects.all()
    serializer_class = FormSubmissionSerializer
    
    def get_permissions(self):
        # Directors can only approve/reject (update_status) — not SSW-only actions
        director_allowed = ['update_status', 'respond_info']
        admin_only = ['add_note', 'share', 'check_eligibility', 'check_duplicates', 'mark_legitimate', 'mark_duplicate']

        if self.action in admin_only:
            from users.permissions import IsAdminUser as AdminOnly
            class StrictAdminOnly(permissions.BasePermission):
                def has_permission(self, request, view):
                    return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')
            return [StrictAdminOnly()]

        if self.action in director_allowed:
            return [IsAdminUser()]  # both admin and director

        # For list and retrieve, allow students to see their own + staff to see all
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]

        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = FormSubmission.objects.select_related(
            'form', 'student', 'reviewed_by', 'forwarded_by', 'decided_by',
            'more_info_requested_by'
        ).prefetch_related(
            'answers__field',
            'notes__author'
        ).order_by('-submitted_at')

        if user.role == 'director':
            # Directors only see submissions forwarded to them by admin/SSW
            # plus already decided ones (accepted/rejected) for their history
            return qs.filter(status__in=['forwarded', 'accepted', 'rejected'])

        if user.role == 'admin':
            return qs

        # Students only see their own
        return qs.filter(student=user)

    @decorators.action(detail=True, methods=['put'], url_path='status')
    def update_status(self, request, pk=None):
        submission = self.get_object()
        new_status = request.data.get('status')
        FormService.update_submission_status(submission, new_status, request.user, request.data)
        from api.models import AuditLog
        AuditLog.objects.create(
            action=f"Submission {submission.id} status changed to {new_status}",
            performed_by=request.user,
            role=request.user.role,
            details=f"Submission {submission.id} — changed to {new_status} by {request.user.full_name}"
        )
        submission = FormSubmission.objects.select_related(
            'form', 'student', 'reviewed_by', 'forwarded_by', 'decided_by'
        ).prefetch_related('answers__field', 'notes__author').get(pk=submission.pk)
        return api_response(True, FormSubmissionSerializer(submission, context={'request': request}).data, "Submission updated")

    @decorators.action(detail=True, methods=['post'], url_path='notes')
    def add_note(self, request, pk=None):
        submission = self.get_object()
        text = request.data.get('text')
        if text:
            note = SubmissionNote.objects.create(submission=submission, author=request.user, text=text)
            return api_response(True, SubmissionNoteSerializer(note).data, "Internal note added")
        return api_response(False, None, "Note text is required", status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'], url_path='share')
    def share(self, request, pk=None):
        submission = self.get_object()
        # Create or update shareable link
        token = uuid.uuid4().hex
        expires_at = timezone.now() + timezone.timedelta(days=7)
        
        link = ShareableLink.objects.create(
            submission=submission,
            token=token,
            expires_at=expires_at,
            is_active=True
        )
        
        return api_response(True, { "token": token }, "Share link generated")

    @decorators.action(detail=True, methods=['post'], url_path='check-eligibility')
    def check_eligibility(self, request, pk=None):
        """Check eligibility for a submission against all funding streams."""
        submission = self.get_object()
        
        try:
            eligibility_result = EligibilityService.check_eligibility(submission)
            EligibilityService.log_eligibility_check(submission, eligibility_result, request.user)
            
            return api_response(
                True,
                eligibility_result,
                "Eligibility determination completed",
                status.HTTP_200_OK
            )
        except Exception as e:
            return api_response(
                False,
                None,
                f"Eligibility check failed: {str(e)}",
                status.HTTP_400_BAD_REQUEST
            )

    @decorators.action(detail=True, methods=['post'], url_path='check-duplicates')
    def check_duplicates(self, request, pk=None):
        """Check for potential duplicate applicants."""
        submission = self.get_object()
        
        try:
            duplicate_result = DuplicateDetectionService.check_for_duplicates(submission)
            
            # Return only flagged status to staff, no detection method details
            return api_response(
                True,
                {
                    'is_flagged': duplicate_result['is_flagged'],
                    'requires_review': duplicate_result['requires_review'],
                    'message': duplicate_result['message']
                },
                "Duplicate check completed",
                status.HTTP_200_OK
            )
        except Exception as e:
            return api_response(
                False,
                None,
                f"Duplicate check failed: {str(e)}",
                status.HTTP_400_BAD_REQUEST
            )

    @decorators.action(detail=True, methods=['post'], url_path='mark-legitimate')
    def mark_legitimate(self, request, pk=None):
        """Mark a flagged submission as legitimate."""
        submission = self.get_object()
        notes = request.data.get('notes', '')
        
        try:
            success = DuplicateDetectionService.mark_as_legitimate(
                submission.id,
                request.user,
                notes
            )
            
            if success:
                return api_response(
                    True,
                    None,
                    "Submission marked as legitimate",
                    status.HTTP_200_OK
                )
            else:
                return api_response(
                    False,
                    None,
                    "Duplicate log not found",
                    status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return api_response(
                False,
                None,
                f"Failed to mark as legitimate: {str(e)}",
                status.HTTP_400_BAD_REQUEST
            )

    @decorators.action(detail=True, methods=['post'], url_path='mark-duplicate')
    def mark_duplicate(self, request, pk=None):
        """Mark a flagged submission as a confirmed duplicate."""
        submission = self.get_object()
        notes = request.data.get('notes', '')
        
        try:
            success = DuplicateDetectionService.mark_as_confirmed_duplicate(
                submission.id,
                request.user,
                notes
            )
            
            if success:
                return api_response(
                    True,
                    None,
                    "Submission marked as confirmed duplicate",
                    status.HTTP_200_OK
                )
            else:
                return api_response(
                    False,
                    None,
                    "Duplicate log not found",
                    status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return api_response(
                False,
                None,
                f"Failed to mark as duplicate: {str(e)}",
                status.HTTP_400_BAD_REQUEST
            )

    @decorators.action(detail=True, methods=['post'], url_path='respond-info')
    def respond_info(self, request, pk=None):
        """
        Student submits additional information in response to a more_info_required request.
        Accepts new answers (text + files) and updates submission status back to 'pending'.
        """
        submission = self.get_object()

        # Only the submission owner can respond
        if submission.student != request.user:
            return api_response(False, None, "Not authorized", status.HTTP_403_FORBIDDEN)

        if submission.status != 'more_info_required':
            return api_response(False, None, "Submission is not awaiting additional information", status.HTTP_400_BAD_REQUEST)

        # Parse new answers from request
        data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)

        new_answers = []
        i = 0
        while f'answers[{i}]field_label' in data:
            ans = {
                'field_label': data.get(f'answers[{i}]field_label'),
                'answer_text': data.get(f'answers[{i}]answer_text', ''),
            }
            file_key = f'answers[{i}]answer_file'
            if file_key in request.FILES:
                ans['answer_file'] = request.FILES[file_key]
            new_answers.append(ans)
            i += 1

        # Also accept JSON body answers
        if not new_answers and 'answers' in request.data:
            new_answers = request.data.get('answers', [])

        if not new_answers and 'response_text' not in data:
            return api_response(False, None, "No information provided", status.HTTP_400_BAD_REQUEST)

        from forms.models import FormField, SubmissionAnswer
        from django.utils import timezone

        # Add a general response note if provided
        response_text = data.get('response_text', '')
        if response_text:
            field, _ = FormField.objects.get_or_create(
                form=submission.form,
                label='Student Response',
                defaults={'field_type': 'textarea', 'is_required': False, 'order': 100}
            )
            SubmissionAnswer.objects.create(
                submission=submission,
                field=field,
                answer_text=response_text
            )

        # Add each new answer
        for ans_data in new_answers:
            field_label = ans_data.get('field_label', 'Additional Information')
            field, _ = FormField.objects.get_or_create(
                form=submission.form,
                label=field_label,
                defaults={'field_type': 'text', 'is_required': False, 'order': 101}
            )
            answer = SubmissionAnswer(
                submission=submission,
                field=field,
                answer_text=ans_data.get('answer_text', '')
            )
            if 'answer_file' in ans_data:
                answer.answer_file = ans_data['answer_file']
            answer.save()

        # Update submission: mark responded, set status back to pending
        submission.more_info_responded_at = timezone.now()
        submission.status = 'pending'
        submission.save(update_fields=['more_info_responded_at', 'status'])

        # Notify staff
        from django.contrib.auth import get_user_model
        from notifications.models import Notification
        from api.models import AuditLog
        User = get_user_model()

        staff = User.objects.filter(role__in=['admin', 'director'])
        for s in staff:
            Notification.objects.create(
                user=s,
                title="Student Responded — Info Provided",
                message=f"{submission.student.full_name} has submitted the requested information for '{submission.form.title}' (#{submission.id}).",
                link=None
            )

        AuditLog.objects.create(
            action=f"Student responded to info request for Submission #{submission.id}",
            performed_by=request.user,
            role=request.user.role,
        )

        # Return updated submission
        submission = FormSubmission.objects.select_related(
            'form', 'student', 'reviewed_by', 'forwarded_by', 'decided_by', 'more_info_requested_by'
        ).prefetch_related('answers__field', 'notes__author').get(pk=submission.pk)

        return api_response(True, FormSubmissionSerializer(submission, context={'request': request}).data, "Information submitted successfully")

    @decorators.action(detail=True, methods=['get'], url_path='download-pdf')
    def download_pdf(self, request, pk=None):
        """
        Download a PDF of the submitted form with all answers filled in
        """
        submission = self.get_object()
        
        try:
            # Generate filled PDF
            pdf_content = FormPDFGenerator.generate_filled_form(submission)
            
            # Create response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            filename = f"Submission_FS-{submission.id}_{submission.form.title.replace(' ', '_')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Log the download
            from api.models import AuditLog
            AuditLog.objects.create(
                action=f"Downloaded PDF for submission: FS-{submission.id}",
                performed_by=request.user,
                details=f"Submission ID: {submission.id}, Form: {submission.form.title}"
            )
            
            return response
        except Exception as e:
            logger.error(f"Error generating PDF for submission {submission.id}: {str(e)}", exc_info=True)
            return api_response(False, None, f"Failed to generate PDF: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# PUBLIC FORM B VIEWS  (no authentication required — accessed via token link)
# ---------------------------------------------------------------------------

from rest_framework.views import APIView
from rest_framework.response import Response as DRFResponse
from rest_framework import permissions as drf_permissions


class FormBPublicView(APIView):
    """
    GET  /api/forms/form-b/<token>/   — return pre-filled Form B data for registrar
    POST /api/forms/form-b/<token>/   — registrar submits completed Form B
    """
    permission_classes = [drf_permissions.AllowAny]

    def get(self, request, token):
        from forms.models import FormBResponse
        try:
            form_b = FormBResponse.objects.select_related('submission__student').get(token=token)
        except FormBResponse.DoesNotExist:
            return DRFResponse({'error': 'Invalid or expired link.'}, status=404)

        if not form_b.is_valid():
            return DRFResponse({'error': 'This link has expired. Please contact education@deline.ca.'}, status=410)

        return DRFResponse({
            'token': token,
            'reference': f"DGG-{form_b.submission_id:04d}" if form_b.submission_id else '',
            'student_name': form_b.student_name,
            'institution': form_b.institution,
            'program': form_b.program,
            'sem_start': form_b.sem_start,
            'sem_end': form_b.sem_end,
            'status': form_b.status,
            'already_submitted': form_b.status == 'received',
        })

    def post(self, request, token):
        from forms.models import FormBResponse
        from django.utils import timezone
        from notifications.models import Notification
        from django.contrib.auth import get_user_model
        from api.models import AuditLog
        User = get_user_model()

        try:
            form_b = FormBResponse.objects.select_related('submission__student', 'submission__form').get(token=token)
        except FormBResponse.DoesNotExist:
            return DRFResponse({'error': 'Invalid or expired link.'}, status=404)

        if not form_b.is_valid():
            return DRFResponse({'error': 'This link has expired.'}, status=410)

        if form_b.status == 'received':
            return DRFResponse({'error': 'Form B has already been submitted for this student.'}, status=400)

        d = request.data

        # Save registrar's response
        form_b.is_enrolled = d.get('is_enrolled', True)
        form_b.enrollment_status = d.get('enrollment_status', '')
        form_b.course_load_percent = d.get('course_load_percent') or None
        form_b.confirmed_program = d.get('confirmed_program', form_b.program)
        form_b.confirmed_sem_start = d.get('confirmed_sem_start', form_b.sem_start)
        form_b.confirmed_sem_end = d.get('confirmed_sem_end', form_b.sem_end)
        form_b.official_tuition = d.get('official_tuition') or None
        form_b.registrar_notes = d.get('registrar_notes', '')
        form_b.registrar_name = d.get('registrar_name', '')
        form_b.registrar_title = d.get('registrar_title', '')
        form_b.status = 'received'
        form_b.received_at = timezone.now()
        form_b.save()

        submission = form_b.submission
        student = submission.student if submission else None

        # Notify all staff (admin) — Form B received, but Form A still cannot be forwarded
        staff = User.objects.filter(role='admin')
        for s in staff:
            Notification.objects.create(
                user=s,
                title=f"Form B Received — {form_b.student_name}",
                message=(
                    f"The registrar at {form_b.institution} has completed enrollment verification "
                    f"for {form_b.student_name} (Ref: DGG-{form_b.submission_id:04d}). "
                    f"Enrolled: {'Yes' if form_b.is_enrolled else 'No'}, "
                    f"Status: {form_b.enrollment_status}, "
                    f"Tuition: ${form_b.official_tuition or 'N/A'}. "
                    f"You may now review and forward the Admission Application."
                ),
                link=f"/staff/applications?id={form_b.submission_id}",
            )

        # Audit log
        if submission:
            AuditLog.objects.create(
                action=f"Form B received for Submission #{form_b.submission_id} from {form_b.registrar_email}",
                performed_by=None,
                details=(
                    f"Registrar: {form_b.registrar_name} ({form_b.registrar_title}), "
                    f"Enrolled: {form_b.is_enrolled}, "
                    f"Tuition: {form_b.official_tuition}"
                ),
            )

        return DRFResponse({
            'success': True,
            'message': (
                f"Thank you, {form_b.registrar_name or 'Registrar'}. "
                f"The enrollment verification for {form_b.student_name} has been received. "
                f"The DGG Education Department will be in touch if further information is needed."
            ),
        })
