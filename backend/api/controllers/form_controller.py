from rest_framework import viewsets, permissions, status, decorators, parsers
from forms.models import Form, FormSubmission, SubmissionNote
from forms.serializers import FormSerializer, FormSubmissionSerializer, SubmissionNoteSerializer
from api.services.form_service import FormService
from api.services.eligibility_service import EligibilityService
from api.services.duplicate_detection_service import DuplicateDetectionService
from api.utils.responses import api_response
from api.models import ShareableLink
from users.permissions import IsAdminUser, IsOwnerOrAdmin
from django.utils import timezone
import uuid

class FormController(viewsets.ModelViewSet):
    queryset = Form.objects.all()
    serializer_class = FormSerializer
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        form = self.get_object()
        data = request.data.dict() if hasattr(request.data, 'dict') else request.data.copy()
        data['form'] = form.id

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

        serializer = FormSubmissionSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            submission = serializer.save(form=form, student=request.user)
            FormService.send_submission_notifications(submission)
            return api_response(True, serializer.data, "Form submitted successfully", status.HTTP_201_CREATED)
        return api_response(False, serializer.errors, "Submission failed", status.HTTP_400_BAD_REQUEST)

class SubmissionController(viewsets.ModelViewSet):
    queryset = FormSubmission.objects.all()
    serializer_class = FormSubmissionSerializer
    
    def get_permissions(self):
        if self.action in ['update_status', 'add_note', 'share']:
            return [IsAdminUser()]
        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'director']:
            return FormSubmission.objects.all().order_by('-submitted_at')
        return FormSubmission.objects.filter(student=user).order_by('-submitted_at')

    @decorators.action(detail=True, methods=['put'], url_path='status')
    def update_status(self, request, pk=None):
        submission = self.get_object()
        new_status = request.data.get('status')
        FormService.update_submission_status(submission, new_status, request.user, request.data)
        return api_response(True, FormSubmissionSerializer(submission).data, "Submission updated")

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

    @decorators.action(detail=True, methods=['post'], url_path='log-banking-access')
    def log_banking_access(self, request, pk=None):
        """Log when a director views banking details for a submission (Requirement 12.3)."""
        from users.permissions import IsDirectorUser
        
        # Only directors can log banking access
        if getattr(request.user, 'role', None) != 'director':
            return api_response(
                False,
                None,
                "Only directors can access banking details",
                status.HTTP_403_FORBIDDEN
            )
        
        submission = self.get_object()
        
        from api.models import AuditLog
        AuditLog.objects.create(
            action=f"Director viewed banking details for submission #{submission.id}",
            performed_by=request.user,
            role=request.user.role,
            details=f"Banking details accessed for student: {submission.student.full_name} (ID: {submission.student.id})"
        )
        
        return api_response(
            True,
            None,
            "Banking details access logged",
            status.HTTP_200_OK
        )
