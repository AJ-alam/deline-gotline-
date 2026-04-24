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
)
from forms.models import FormSubmission, SubmissionNote

User = get_user_model()

class FormService:
    @staticmethod
    def send_submission_notifications(submission):
        form = submission.form
        student = submission.student

        # In-app notification
        if student:
            Notification.objects.create(
                user=student,
                title="Application Received",
                message=f"Your application for '{form.title}' has been successfully submitted.",
                link="/dashboard"
            )
            # Task 9.3: Email notification
            if student.email:
                email_application_received(student.email, student.full_name, form.title)

        # Trigger Form B (Enrollment Verification) for Form A submissions
        if 'form a' in form.title.lower() or 'forma' in form.title.lower().replace(' ', ''):
            FormService._send_form_b_email(submission)

        # Notify Admins (in-app only)
        admins = User.objects.filter(role='admin')
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title="New Application Received",
                message=f"A new submission for '{form.title}' from {student.full_name if student else 'Guest'}.",
                link="/staff/applications"
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
            pass  # No timestamp needed; status update + notification is sufficient
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
            link="/dashboard"
        )

        student = submission.student
        if not student or not student.email:
            return

        if new_status == 'accepted':
            email_application_approved(
                student.email, student.full_name,
                submission.form.title, float(submission.amount or 0)
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
                submission.form.title, submission.decision_reason or ''
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
                email_director_approval_request(
                    director_email=director.email,
                    student_name=submission.student.full_name if submission.student else 'Student',
                    form_title=submission.form.title,
                    amount=float(submission.amount or 0),
                    submission_id=submission.id,
                )
