from django.utils import timezone
from django.contrib.auth import get_user_model
from notifications.models import Notification
from notifications.utils import (
    email_application_received,
    email_application_approved,
    email_application_rejected,
    email_director_approval_request,
    email_finance_payment_details,
    email_form_b_registrar,
    email_more_info_requested,
    email_new_submission_staff,
)
from forms.models import FormSubmission, SubmissionNote

User = get_user_model()

class FormService:
    @staticmethod
    def send_submission_notifications(submission):
        form = submission.form
        student = submission.student
        form_title_lower = form.title.lower() if form else ''

        # In-app notification for logged-in students
        if student:
            Notification.objects.create(
                user=student,
                title="Application Received",
                message=f"Your application for '{form.title}' has been successfully submitted.",
                link=None
            )
            if student.email:
                email_application_received(
                    student.email, student.full_name, form.title,
                    submission_id=submission.id,
                    submitted_at=submission.submitted_at,
                )

        # Trigger enrollment verification email for new student applications
        if 'new student application' in form_title_lower or 'psssp' in form_title_lower:
            FormService._send_form_b_email(submission)

        # Auto-forward one-off awards directly to director queue
        is_one_off = (
            'practicum' in form_title_lower or
            'placement allowance' in form_title_lower or
            'graduation bursary' in form_title_lower or
            'summer student' in form_title_lower or
            'scholarship' in form_title_lower or
            'hardship' in form_title_lower
        )
        if is_one_off:
            from django.utils import timezone
            submission.status = 'forwarded'
            submission.forwarded_at = timezone.now()
            submission.save(update_fields=['status', 'forwarded_at'])
            # Calculate award amount immediately from policy
            try:
                from api.services.calculation_service import CalculationService
                results = CalculationService.calculate_and_pay(submission)
                # Store breakdown in office_use_data for director review
                if results:
                    submission.office_use_data = {
                        **(submission.office_use_data or {}),
                        'auto_calculated': True,
                        'award_type': results.get('award_type', ''),
                        'breakdown': {k: str(v) for k, v in results.items() if k not in ('payment_items',)},
                    }
                    submission.save(update_fields=['office_use_data'])
            except Exception as e:
                import logging
                logging.getLogger(__name__).error("Automatic calculation failed for submission %s: %s", submission.id, e)

        # Notify Admins & Directors
        admins_and_directors = User.objects.filter(role__in=['admin', 'director'])
        staff_emails = [u.email for u in admins_and_directors if u.email]

        if staff_emails:
            answers = submission.answers.all()
            summary_lines = []
            for ans in answers[:10]:
                label = ans.field.label if ans.field else (getattr(ans, 'field_label', '') or 'Field')
                summary_lines.append(f"<strong>{label}:</strong> {ans.answer_text or '—'}")
            summary_html = "<br>".join(summary_lines)
            if len(answers) > 10:
                summary_html += "<br><em>... and more details available in the dashboard.</em>"

            email_new_submission_staff(
                staff_emails=staff_emails,
                student_name=student.full_name if student else 'Guest Applicant',
                form_title=form.title,
                submission_id=submission.id,
                answers_summary=summary_html
            )

        for staff in admins_and_directors:
            Notification.objects.create(
                user=staff,
                title="New Application Received",
                message=f"A new submission for '{form.title}' from {student.full_name if student else 'Guest Applicant'}.",
                link=None
            )

    @staticmethod
    def update_submission_status(submission, new_status, performed_by, extra_data=None):
        if not extra_data:
            extra_data = {}
            
        submission.status = new_status
        
        if 'amount' in extra_data:
            submission.amount = extra_data.get('amount')

        if 'office_use_data' in extra_data:
            submission.office_use_data = extra_data['office_use_data']

        if new_status == 'more_info_required':
            submission.more_info_requested_at = timezone.now()
            submission.more_info_requested_by = performed_by
            submission.more_info_request_notes = extra_data.get('notes', '')
        elif new_status == 'reviewed':
            submission.reviewed_at = timezone.now()
            submission.reviewed_by = performed_by
        elif new_status == 'forwarded':
            submission.forwarded_at = timezone.now()
            submission.forwarded_by = performed_by
        elif new_status in ['accepted', 'rejected']:
            submission.decided_at = timezone.now()
            submission.decided_by = performed_by
            submission.decision_reason = extra_data.get('decision_notes', extra_data.get('reason', ''))

            # AUTOMATED CALCULATION & PAYMENT GENERATION
            if new_status == 'accepted':
                from api.services.calculation_service import CalculationService
                CalculationService.calculate_and_pay(submission)

        submission.save()

        # Status change notifications
        if submission.student:
            FormService._send_status_notification(submission, new_status, extra_data)

        # Task 9.7: Director approval request when forwarded
        if new_status == 'forwarded':
            FormService._notify_directors_for_approval(submission)
            
        return submission

    @staticmethod
    def _send_status_notification(submission, new_status, extra_data=None):
        if extra_data is None:
            extra_data = {}

        status_labels = {
            'reviewed': 'Under Review',
            'forwarded': 'Forwarded to Director',
            'more_info_required': 'Additional Information Required',
            'accepted': 'Approved',
            'rejected': 'Not Approved',
        }
        title = f"Application Update: {status_labels.get(new_status, new_status.replace('_', ' ').title())}"
        msg = f"Your application for '{submission.form.title}' status has been updated."

        if new_status == 'accepted':
            msg = f"Congratulations! Your application has been APPROVED for ${submission.amount}."
        elif new_status == 'rejected':
            msg = f"Your application was not approved. Reason: {submission.decision_reason}"
        elif new_status == 'more_info_required':
            notes = extra_data.get('notes', '')
            msg = f"Your application for '{submission.form.title}' requires additional information. {notes}".strip()
        elif new_status == 'forwarded':
            msg = f"Your application for '{submission.form.title}' has been reviewed and forwarded to the Director for final decision."

        Notification.objects.create(
            user=submission.student,
            title=title,
            message=msg,
            link=None
        )

        student = submission.student
        if not student or not student.email:
            return

        if new_status == 'accepted':
            email_application_approved(
                student.email, student.full_name,
                submission.form.title, float(submission.amount or 0),
                submission_id=submission.id,
            )
            from api.models import PolicySetting
            finance_cfg = PolicySetting.objects.filter(
                section='system_config', field_key='finance_email'
            ).first()
            finance_email = finance_cfg.unit if finance_cfg else ''
            if finance_email:
                email_finance_payment_details(
                    finance_email=finance_email,
                    student_name=student.full_name,
                    amount=float(submission.amount or 0),
                    payment_type='Student Funding',
                    funding_stream=submission.form.title or 'DGGR',
                    bank_name=getattr(student, 'bank_name', '') or '',
                    account_number=getattr(student, 'account_number', '') or '',
                    transit_number=getattr(student, 'transit_number', '') or '',
                    submission_id=submission.id,
                )
        elif new_status == 'rejected':
            email_application_rejected(
                student.email, student.full_name,
                submission.form.title, submission.decision_reason or '',
                submission_id=submission.id,
            )
        elif new_status == 'more_info_required':
            notes = extra_data.get('notes', '')
            email_more_info_requested(
                student.email, student.full_name,
                submission.form.title, notes
            )

    @staticmethod
    def _send_form_b_email(submission):
        """Send enrollment verification (Form B) to institution registrar on Form A submission."""
        try:
            from api.models import PolicySetting
            registrar_cfg = PolicySetting.objects.filter(
                section='system_config', field_key='registrar_email'
            ).first()
            registrar_email = registrar_cfg.unit if registrar_cfg else ''
            if not registrar_email:
                return

            student = submission.student
            answers = {a.field.label.lower(): a.answer_text for a in submission.answers.select_related('field').all()}

            institution = (
                answers.get('institution name') or answers.get('institution') or
                getattr(student, 'institution_name', '') or 'Not specified'
            )
            program = (
                answers.get('program') or answers.get('program name') or
                getattr(student, 'program_credential', '') or 'Not specified'
            )
            sem_start = answers.get('semester start') or answers.get('start date') or 'Not specified'
            sem_end = answers.get('semester end') or answers.get('end date') or 'Not specified'
            student_dob = str(getattr(student, 'dob', '') or '')
            student_id = (
                answers.get('student id') or answers.get('studentid') or
                answers.get('student number') or answers.get('student #') or
                str(getattr(student, 'upi', '') or getattr(student, 'beneficiary_number', '') or '')
            )

            email_form_b_registrar(
                registrar_email=registrar_email,
                student_name=student.full_name,
                student_dob=student_dob,
                student_id=student_id,
                institution=institution,
                program=program,
                sem_start=sem_start,
                sem_end=sem_end,
                submission_id=submission.id,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Form B email failed: %s", e)

    @staticmethod
    def _notify_directors_for_approval(submission):
        """Task 9.7: Notify directors when application is forwarded."""
        directors = User.objects.filter(role='director')
        for director in directors:
            Notification.objects.create(
                user=director,
                title="Application Awaiting Approval",
                message=f"#{submission.id} — {submission.student.full_name if submission.student else 'Student'} needs your decision.",
                link="/staff/director-queue"
            )
            if director.email:
                try:
                    email_director_approval_request(
                        director_email=director.email,
                        student_name=submission.student.full_name if submission.student else 'Student',
                        form_title=submission.form.title,
                        amount=float(submission.amount or 0),
                        submission_id=submission.id,
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error("Director approval email failed: %s", e)
