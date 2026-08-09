import logging
from rest_framework import viewsets, permissions, status, decorators, parsers
from django.http import HttpResponse

from forms.models import Form, FormSubmission, SubmissionNote
from forms.serializers import FormSerializer, FormSubmissionSerializer, FormSubmissionListSerializer, SubmissionNoteSerializer
from api.services.form_service import FormService
from api.services.eligibility_service import EligibilityService
from api.services.duplicate_detection_service import DuplicateDetectionService
from api.utils.responses import api_response
from api.utils.pdf_generator import FormPDFGenerator
from api.models import ShareableLink
from users.permissions import IsAdminUser, IsOwnerOrAdmin, IsSSWOrAdmin
from django.utils import timezone
import uuid

logger = logging.getLogger(__name__)

class FormController(viewsets.ModelViewSet):

    queryset = Form.objects.all()
    serializer_class = FormSerializer
    parser_classes = (parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser)

    def get_queryset(self):
        # Public list shows only active forms — deduped/retired templates stay
        # retrievable by id so existing submissions keep rendering.
        qs = super().get_queryset()
        if self.action == 'list':
            qs = qs.filter(is_active=True)
        return qs


    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        # Submit, list, and retrieve are public so guest applicants (Hardship,
        # Practicum, Graduation, Appeals, Special Awards) can discover the form
        # template and post without logging in. All write actions still require
        # admin auth above.
        if self.action in ['submit', 'list', 'retrieve']:
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

    @decorators.action(detail=True, methods=['get'], url_path='prefill')
    def prefill(self, request, pk=None):
        """§5 Form C: Return pre-filled answers from the student's most recent
        accepted submission for any Form A/C, so Form C can auto-populate fields.
        Only accessible to the authenticated student (or staff).
        """
        form = self.get_object()
        if not request.user.is_authenticated:
            return api_response(False, None, "Authentication required", status.HTTP_401_UNAUTHORIZED)

        from forms.models import FormSubmission, SubmissionAnswer
        from forms.serializers import FormSubmissionSerializer

        # Find student's most recent accepted/approved submission (Form A or C)
        prior = (FormSubmission.objects
                 .filter(
                     student=request.user,
                     status__in=['accepted', 'forwarded', 'reviewed'],
                 )
                 .filter(
                     form__title__iregex=r'(form [ac]|new student|continuing|psssp|ucepp)'
                 )
                 .select_related('form')
                 .prefetch_related('answers__field')
                 .order_by('-submitted_at')
                 .first())

        if not prior:
            return api_response(True, {'prefill': {}, 'message': 'No prior application found.'})

        prefill_data = {}
        for ans in prior.answers.all():
            if ans.field:
                prefill_data[ans.field.label] = ans.answer_text or ''

        # Also include student profile fields
        u = request.user
        profile = getattr(u, 'profile', None)
        prefill_data.update({
            'Full Name': u.full_name or '',
            'Email': u.email or '',
            'Phone Number': u.phone or (profile.phone_number if profile else '') or '',
            'Beneficiary Number': u.beneficiary_number or (profile.beneficiary_number if profile else '') or '',
            'Institution Name': u.institution_name or '',
            'Program': u.program_credential or '',
            'Enrollment Status': u.enrollment_status or '',
        })

        return api_response(True, {
            'prefill': prefill_data,
            'source_submission_id': prior.id,
            'source_submitted_at': prior.submitted_at.isoformat() if prior.submitted_at else None,
        })

    @decorators.action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        try:
            return self._submit_inner(request, pk)
        except Exception as e:
            logger.exception("Unhandled exception in submit view for form pk=%s user=%s: %s",
                             pk, getattr(request.user, 'email', '?'), e)
            return api_response(False, None, f"Submission failed: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _submit_inner(self, request, pk):
        form = self.get_object()
        data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
        data['form'] = form.id

        # Check if this is Form A and if user already has a non-rejected submission
        if request.user.is_authenticated:
            form_title_lower = form.title.lower()
            is_form_a = ('form a' in form_title_lower or 'forma' in form_title_lower
                         or 'psssp' in form_title_lower or 'admission' in form_title_lower)

            if is_form_a:
                existing_submission = FormSubmission.objects.filter(
                    student=request.user,
                    form=form
                ).exclude(status='rejected').first()

                if existing_submission:
                    logger.warning("User %s attempted to resubmit Form A (existing submission: %s)",
                                   request.user.email, existing_submission.id)
                    return api_response(
                        False,
                        {'existing_submission_id': existing_submission.id},
                        "You have already submitted this form. Only one Form A submission is allowed unless your previous submission was rejected.",
                        status.HTTP_400_BAD_REQUEST
                    )

        # Map FormData indexed answers (multipart/form-data)
        if 'answers[0]field_label' in data:
            answers = []
            i = 0
            while f'answers[{i}]field_label' in data:
                ans = {
                    'field_label': data.get(f'answers[{i}]field_label'),
                    'answer_text': data.get(f'answers[{i}]answer_text') or '',
                }
                file_key = f'answers[{i}]answer_file'
                if file_key in request.FILES:
                    ans['answer_file'] = request.FILES[file_key]
                answers.append(ans)
                i += 1
            data['answers'] = answers

        logger.info("Submit attempt: form=%s user=%s answers=%d",
                    form.id, getattr(request.user, 'email', '?'), len(data.get('answers', [])))

        serializer = FormSubmissionSerializer(data=data, context={'request': request})
        if not serializer.is_valid():
            logger.warning("Submission validation failed for user %s: %s",
                           getattr(request.user, 'email', '?'), serializer.errors)
            return api_response(False, serializer.errors, "Submission failed", status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        try:
            submission = serializer.save(form=form, student=user)
        except Exception as e:
            logger.error("Error saving submission for user %s: %s", getattr(user, 'email', '?'), e, exc_info=True)
            return api_response(False, None, f"Could not save submission: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info("Submission %s created for user %s", submission.id, getattr(user, 'email', '?'))

        # Send notifications — synchronous in tests to avoid SQLite locking, async in production
        from django.conf import settings as _django_settings
        submission_id = submission.id
        def _notify():
            try:
                sub = FormSubmission.objects.select_related(
                    'form', 'student'
                ).prefetch_related('answers__field').get(pk=submission_id)
                FormService.send_submission_notifications(sub)
            except Exception as exc:
                logger.error("Background notification failed for submission %s: %s", submission_id, exc, exc_info=True)
        # Run inline, not in a daemon thread. On serverless the process is frozen
        # or reclaimed as soon as the response is returned, so a background thread
        # frequently never executed and the submission notifications were lost
        # silently. _notify already swallows and logs its own failures, so a mail
        # problem still cannot fail the submission itself.
        _notify()

        # Reload with prefetch to avoid N+1 in response serialization
        try:
            submission = FormSubmission.objects.select_related(
                'form', 'student', 'reviewed_by', 'forwarded_by', 'decided_by'
            ).prefetch_related('answers__field', 'notes__author').get(pk=submission.pk)
            resp_data = FormSubmissionSerializer(submission, context={'request': request}).data
        except Exception as e:
            logger.error("Error serializing submission %s after save: %s", submission_id, e, exc_info=True)
            return api_response(True, {'id': submission_id}, "Form submitted successfully", status.HTTP_201_CREATED)

        return api_response(True, resp_data, "Form submitted successfully", status.HTTP_201_CREATED)


class SubmissionController(viewsets.ModelViewSet):
    queryset = FormSubmission.objects.all()
    serializer_class = FormSubmissionSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return FormSubmissionListSerializer
        return FormSubmissionSerializer

    def get_permissions(self):
        # Directors can only approve/reject (update_status) — not SSW-only actions
        director_allowed = ['update_status']
        admin_only = ['add_note', 'share', 'check_eligibility', 'check_duplicates', 'mark_legitimate', 'mark_duplicate']

        # Correcting submitted details belongs to the SSW/admin who processes the
        # file, never to the director who rules on it.
        if self.action == 'edit_answers':
            return [IsSSWOrAdmin()]

        if self.action in admin_only:
            return [IsAdminUser()]  # admin + ssw + director can add notes/share/check eligibility

        if self.action in director_allowed:
            return [IsAdminUser()]  # both admin and director

        # respond_info is the student's own reply to a more-info request — owner
        # (or staff) only. The action body re-checks ownership before saving.
        if self.action == 'respond_info':
            return [IsOwnerOrAdmin()]

        # For list and retrieve, allow students to see their own + staff to see all
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]

        return [IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user

        # List view: minimal joins — only what FormSubmissionListSerializer reads.
        # Detail / action views: full record incl. reviewer/director names, answers, notes.
        if self.action == 'list':
            qs = (FormSubmission.objects
                  .select_related('form', 'student', 'form_b')
                  .order_by('-submitted_at'))
        else:
            qs = (FormSubmission.objects
                  .select_related(
                      'form', 'student', 'form_b',
                      'reviewed_by', 'forwarded_by', 'decided_by',
                      'more_info_requested_by',
                  )
                  .prefetch_related(
                      'answers__field',
                      'notes__author',
                  )
                  .order_by('-submitted_at'))

        if user.role == 'director':
            # Directors see forwarded + decided — in-progress review stays with SSW/admin
            return qs.filter(status__in=['forwarded', 'accepted', 'rejected'])

        if user.role in ('admin', 'ssw'):
            # All staff see every application + complete history (§3.1.B)
            return qs

        # Students only see their own
        return qs.filter(student=user)

    @decorators.action(detail=True, methods=['put'], url_path='status')
    def update_status(self, request, pk=None):
        submission = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return api_response(False, None, "Status field is required", status.HTTP_400_BAD_REQUEST)

        # The funding breakdown is saved through this endpoint, so the
        # program-cost ceiling is enforced here — being eligible for the cap
        # does not mean the cap is awarded, and later purchases (laptop,
        # supplies) have to fit inside whatever the confirmed tuition left.
        office_use = request.data.get('office_use_data') or {}
        if isinstance(office_use, dict) and office_use.get('funding_breakdown') is not None:
            from api.services.calculation_service import CalculationService
            error = CalculationService.check_program_cost_cap(
                submission, office_use.get('funding_breakdown')
            )
            if error:
                return api_response(False, None, error, status.HTTP_400_BAD_REQUEST)
        try:
            FormService.update_submission_status(submission, new_status, request.user, request.data)
        except Exception as e:
            msg = str(e)
            # DRF ValidationError wraps message in a list
            if hasattr(e, 'detail'):
                detail = e.detail
                if isinstance(detail, list) and detail:
                    msg = str(detail[0])
                elif isinstance(detail, dict):
                    msgs = []
                    for v in detail.values():
                        msgs.extend(v if isinstance(v, list) else [v])
                    msg = str(msgs[0]) if msgs else msg
                else:
                    msg = str(detail)
            http_status = status.HTTP_403_FORBIDDEN if 'permission' in msg.lower() or 'director' in msg.lower() else status.HTTP_400_BAD_REQUEST
            return api_response(False, None, msg, http_status)
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

    @decorators.action(detail=True, methods=['get'], url_path='funding-breakdown')
    def funding_breakdown(self, request, pk=None):
        """
        Amount eligible by category, computed by the same code that creates the
        payments. The staff dashboard used to recalculate this in the browser
        with its own set of rules, so the figures staff reviewed did not always
        match the payments that were generated.
        """
        from api.services.calculation_service import CalculationService

        submission = self.get_object()

        # Once staff have approved a breakdown, that is the answer — for the
        # student as well as for staff. Recalculating here would show the
        # applicant different numbers from the ones on their approval email.
        approved_rows = (submission.office_use_data or {}).get('funding_breakdown') or []
        if approved_rows:
            categories = [
                {
                    'category': row.get('label') or 'Funding',
                    'stream': row.get('stream') or None,
                    'amount': str(row.get('amount') or 0),
                    'rule': row.get('note') or '',
                }
                for row in approved_rows
            ]
            total = sum(float(row.get('amount') or 0) for row in approved_rows)
            return api_response(True, {
                'categories': categories,
                'total': str(total),
                'source': 'approved',
            }, "Approved funding breakdown")

        results = CalculationService.calculate_and_pay(submission, create_payments=False, commit=False)
        if not results:
            return api_response(True, {'categories': [], 'total': 0},
                                "No funding rules apply to this form")

        rows = results.get('breakdown')
        if rows is None:
            # The one-off awards (graduation, scholarship, practicum, hardship)
            # return payment items only — present them in the same shape.
            rows = [
                {'category': label, 'stream': None, 'amount': amount,
                 'rule': results.get('award_type', '')}
                for label, amount in results.get('payment_items', [])
            ]

        categories = [
            {
                'category': row['category'],
                'stream': row['stream'],
                'amount': str(row['amount']),
                'rule': row['rule'],
            }
            for row in rows
        ]
        return api_response(True, {
            'categories': categories,
            'total': str(results.get('total', 0)),
            'source': 'estimate',
            'ineligible_reason': results.get('ineligible_reason'),
            'stream': results.get('stream'),
            'enrollment': results.get('enrollment'),
            'months': results.get('months'),
            'has_dependents': results.get('has_dependents'),
            'tuition_confirmed': results.get('tuition_confirmed', False),
            'requested_tuition': str(results.get('requested_tuition', 0)),
            'unfunded_tuition': str(results.get('unfunded_tuition', 0)),
        }, "Funding breakdown calculated")

    @decorators.action(detail=True, methods=['patch'], url_path='answers')
    def edit_answers(self, request, pk=None):
        """
        SSW/admin correction of the details a student submitted on a form.

        Students routinely mistype a bank transit number, a postal code or an
        institution name, and until now the only fix was to reject the whole
        application and make them start again. Staff can now correct the values
        in place; every change is written to the audit log, summarised in an
        internal note, and reported to the student.

        Body:
            {
              "answers": [
                 {"id": 12, "answer_text": "corrected value"},
                 {"field_label": "Postal Code", "answer_text": "X0E 0G0"}
              ],
              "reason": "Transit number corrected from void cheque"
            }

        File answers are not editable here — a replacement document has to be
        uploaded so the original stays on the record.
        """
        from forms.models import FormField, SubmissionAnswer
        from api.models import AuditLog
        from notifications.utils import create_notification

        submission = self.get_object()

        if submission.finance_sent_at:
            return api_response(
                False, None,
                "This application has already been dispatched to Finance and can no "
                "longer be edited. Record a correction as an internal note instead.",
                status.HTTP_400_BAD_REQUEST,
            )

        edits = request.data.get('answers')
        if not isinstance(edits, list) or not edits:
            return api_response(False, None, "A non-empty 'answers' list is required",
                                status.HTTP_400_BAD_REQUEST)

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return api_response(False, None, "A reason for the correction is required",
                                status.HTTP_400_BAD_REQUEST)

        existing = list(submission.answers.select_related('field').all())
        by_id = {a.id: a for a in existing}
        by_label = {(a.field.label or '').strip().lower(): a for a in existing if a.field}

        changes = []
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            label = (edit.get('field_label') or '').strip()
            answer = by_id.get(edit.get('id')) or by_label.get(label.lower())

            if answer is None:
                if not label:
                    return api_response(False, None,
                                        "Each edit needs an 'id' or a 'field_label'",
                                        status.HTTP_400_BAD_REQUEST)
                # A field the student left off entirely — add it to the record.
                field, _ = FormField.objects.get_or_create(
                    form=submission.form, label=label, defaults={'field_type': 'text'},
                )
                answer = SubmissionAnswer.objects.create(submission=submission, field=field)
                by_label[label.lower()] = answer

            if answer.answer_file:
                return api_response(
                    False, None,
                    f"'{answer.field.label}' holds an uploaded file. Upload a replacement "
                    "document instead of editing the value.",
                    status.HTTP_400_BAD_REQUEST,
                )

            new_value = edit.get('answer_text')
            new_value = '' if new_value is None else str(new_value)
            old_value = answer.answer_text or ''
            if new_value == old_value:
                continue

            answer.answer_text = new_value
            answer.save(update_fields=['answer_text'])
            changes.append((answer.field.label, old_value, new_value))

        if not changes:
            return api_response(False, None, "No values were changed",
                                status.HTTP_400_BAD_REQUEST)

        summary = '; '.join(f"{label}: '{old or '—'}' → '{new or '—'}'" for label, old, new in changes)
        editor = request.user

        SubmissionNote.objects.create(
            submission=submission,
            author=editor,
            text=f"Submitted details corrected by {editor.full_name} ({editor.role}). "
                 f"Reason: {reason}. Changes — {summary}",
        )
        AuditLog.objects.create(
            action=f"Edited submitted answers on submission {submission.id}",
            performed_by=editor,
            role=editor.role,
            details=f"Reason: {reason}. Changes — {summary}",
        )

        # The student's own record must reflect what staff corrected, and the
        # correction can resolve or create a residency mismatch.
        try:
            from api.services.residency_service import apply_to_submission
            submission.refresh_from_db()
            apply_to_submission(submission)
        except Exception:
            logger.exception("Residency re-check failed after editing submission %s", submission.id)

        if submission.student:
            try:
                create_notification(
                    submission.student,
                    "Your application details were corrected",
                    f"{editor.full_name} updated information on your "
                    f"'{submission.form.title if submission.form else 'application'}': {summary}. "
                    f"Reason: {reason}. Contact the Education Department if this is not correct.",
                    link=f"/applications/{submission.id}",
                )
            except Exception:
                logger.exception("Could not notify student of correction on submission %s", submission.id)

        submission = FormSubmission.objects.select_related(
            'form', 'student', 'reviewed_by', 'forwarded_by', 'decided_by'
        ).prefetch_related('answers__field', 'notes__author').get(pk=submission.pk)

        return api_response(
            True,
            FormSubmissionSerializer(submission, context={'request': request}).data,
            f"{len(changes)} field{'s' if len(changes) != 1 else ''} updated",
        )

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

        from forms.models import FormField, SubmissionAnswer as SA
        from django.utils import timezone

        # Add a general response note if provided
        response_text = data.get('response_text', '')
        if response_text:
            field, _ = FormField.objects.get_or_create(
                form=submission.form,
                label='Student Response',
                defaults={'field_type': 'textarea', 'is_required': False, 'order': 100}
            )
            SA.objects.create(
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
            answer = SA(
                submission=submission,
                field=field,
                answer_text=ans_data.get('answer_text', '')
            )
            if 'answer_file' in ans_data:
                uploaded = ans_data['answer_file']
                answer.answer_file = uploaded
                answer.original_filename = getattr(uploaded, 'name', None)
            answer.save()

        # Update submission: mark responded, set status back to pending
        submission.more_info_responded_at = timezone.now()
        submission.status = 'pending'
        submission.save(update_fields=['more_info_responded_at', 'status'])

        # Notify staff
        from django.contrib.auth import get_user_model as _gum
        from notifications.models import Notification
        from api.models import AuditLog
        _User = _gum()

        # Notify admins only — directors are notified when admin re-forwards
        admins = _User.objects.filter(role='admin')
        for s in admins:
            Notification.objects.create(
                user=s,
                title="Student Responded — Info Provided",
                message=f"{submission.student.full_name} has submitted the requested information for '{submission.form.title}' (#{submission.id}).",
                link=f"/staff/applications?id={submission.id}"
            )

        AuditLog.objects.create(
            action=f"Student responded to info request for Submission #{submission.id}",
            performed_by=request.user,
            role=request.user.role,
        )

        # Return updated submission — use module-level FormSubmission (no local re-import)
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
        from django.utils import timezone as tz
        from notifications.models import Notification
        from django.contrib.auth import get_user_model as _gum
        from api.models import AuditLog
        _User = _gum()

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
        form_b.received_at = tz.now()
        form_b.save()

        submission = form_b.submission

        # ── Notify all admin staff ──
        staff = _User.objects.filter(role='admin')
        for s in staff:
            Notification.objects.create(
                user=s,
                title=f"📋 Form B Received — {form_b.student_name}",
                message=(
                    f"Enrollment verification received from {form_b.registrar_name or 'the registrar'} "
                    f"at {form_b.institution} for {form_b.student_name} "
                    f"(Ref: DGG-{form_b.submission_id:04d}). "
                    f"Enrolled: {'Yes' if form_b.is_enrolled else 'No'}, "
                    f"Status: {form_b.enrollment_status}, "
                    f"Tuition: ${form_b.official_tuition or 'N/A'}. "
                    f"You may now forward the Admission Application to the Director."
                ),
                link=f"/staff/applications?id={form_b.submission_id}",
            )

        # ── Audit log ──
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
