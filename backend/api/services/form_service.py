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


def pretty_form_title(raw: str) -> str:
    """Map any DB/frontend form title variant to a clean human-readable name."""
    t = (raw or '').lower()
    if any(x in t for x in ('form a', 'forma', 'psssp', 'c-dfn', 'new student', 'admission')):
        return 'New Student Application'
    if any(x in t for x in ('form b', 'formb', 'enrollment verif', 'enrolment verif', 'profile update')):
        return 'Enrollment Verification'
    if any(x in t for x in ('form c', 'formc', 'continuing fund')):
        return 'Continuing Funding Application'
    if any(x in t for x in ('form d', 'formd', 'appeal', 'reconsider', 'specialized train')):
        return 'Appeal & Reconsideration'
    if any(x in t for x in ('form e', 'forme', 'travel', 'emergency fund')):
        return 'Travel & Relocation Claim'
    if any(x in t for x in ('form f', 'formf', 'practicum', 'placement')):
        return 'Practicum Placement Allowance'
    if any(x in t for x in ('form g', 'formg', 'graduation')):
        return 'Graduation Bursary'
    if any(x in t for x in ('form h', 'formh', 'summer student')):
        return 'Summer Student Employment'
    if 'hardship' in t:
        return 'Hardship Bursary'
    if 'scholarship' in t:
        return 'Academic Scholarship'
    return raw  # unknown form — return as-is


class FormService:
    @staticmethod
    def send_submission_notifications(submission):
        form = submission.form
        student = submission.student
        form_title_lower = form.title.lower() if form else ''
        display_title = pretty_form_title(form.title) if form else 'Application'

        # In-app notification for logged-in students
        if student:
            Notification.objects.create(
                user=student,
                title="Application Received",
                message=f"Your {display_title} has been successfully submitted.",
                link=None
            )
            if student.email:
                email_application_received(
                    student.email, student.full_name, display_title,
                    submission_id=submission.id,
                    submitted_at=submission.submitted_at,
                )

        # Trigger enrollment verification email for Form A / PSSSP submissions
        if ('new student application' in form_title_lower or 'psssp' in form_title_lower
                or 'form a' in form_title_lower or 'admission' in form_title_lower):
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
            # Calculate award amount immediately from policy
            # BUT do not auto-forward to director anymore. Admin must review first.
            try:
                from api.services.calculation_service import CalculationService
                # Calculate award amount but DO NOT create payments yet (Director must approve first)
                results = CalculationService.calculate_and_pay(submission, create_payments=False)
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

        # Notify Admins only — directors see applications only after admin forwards them
        admins = User.objects.filter(role='admin')
        admin_emails = [u.email for u in admins if u.email]

        if admin_emails:
            answers = submission.answers.all()
            summary_lines = []
            for ans in answers[:10]:
                label = ans.field.label if ans.field else (getattr(ans, 'field_label', '') or 'Field')
                summary_lines.append(f"<strong>{label}:</strong> {ans.answer_text or '—'}")
            summary_html = "<br>".join(summary_lines)
            if len(answers) > 10:
                summary_html += "<br><em>... and more details available in the dashboard.</em>"

            email_new_submission_staff(
                staff_emails=admin_emails,
                student_name=student.full_name if student else 'Guest Applicant',
                form_title=display_title,
                submission_id=submission.id,
                answers_summary=summary_html
            )

        for admin in admins:
            Notification.objects.create(
                user=admin,
                title="New Application Received",
                message=f"New {display_title} from {student.full_name if student else 'Guest Applicant'}.",
                link=None
            )

    @staticmethod
    def update_submission_status(submission, new_status, performed_by, extra_data=None):
        if not extra_data:
            extra_data = {}

        # 0. Prevent redundant processing if status is unchanged
        if submission.status == new_status:
            return submission

        # 1. Role-based permission check
        if new_status in ['reviewed', 'forwarded'] and performed_by.role == 'director':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Directors cannot perform administrative review or forwarding actions.")

        # 2. Block transitions until Admin Review/Form B is complete
        if new_status in ['reviewed', 'forwarded']:
            # Special check for Form A: Form B must be received before Review OR Forwarding
            form_title_lower = (submission.form.title or '').lower()
            is_form_a = ('form a' in form_title_lower or 'psssp' in form_title_lower
                         or 'admission' in form_title_lower)
            
            if is_form_a:
                from forms.models import FormBResponse
                form_b = FormBResponse.objects.filter(submission=submission).first()
                if not form_b or form_b.status != 'received':
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError(
                        f"Cannot mark this Admission Application as '{new_status.title()}' — "
                        "Form B (Enrollment Verification) has not been received from the registrar yet."
                    )
            
            # Enforce that it must be reviewed before it can be forwarded
            if new_status == 'forwarded' and submission.status != 'reviewed':
                from rest_framework.exceptions import ValidationError
                raise ValidationError(
                    "This application must be marked as 'Reviewed' by an administrator before it can be forwarded to the Director."
                )
            
        submission.status = new_status
        
        if 'amount' in extra_data:
            submission.amount = extra_data.get('amount')

        if 'office_use_data' in extra_data:
            # Merge so partial updates (e.g. just funding_breakdown) don't clobber
            # unrelated keys like dateReceived/approvedBy/commitmentNum.
            current = submission.office_use_data or {}
            incoming = extra_data['office_use_data'] or {}
            if isinstance(current, dict) and isinstance(incoming, dict):
                submission.office_use_data = {**current, **incoming}
            else:
                submission.office_use_data = incoming

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

        display_title = pretty_form_title(submission.form.title) if submission.form else 'Application'
        status_labels = {
            'reviewed': 'Under Review',
            'forwarded': 'Forwarded to Director',
            'more_info_required': 'Additional Information Required',
            'accepted': 'Approved',
            'rejected': 'Not Approved',
        }
        title = f"Application Update: {status_labels.get(new_status, new_status.replace('_', ' ').title())}"
        msg = f"Your {display_title} status has been updated."

        if new_status == 'accepted':
            msg = f"Congratulations! Your {display_title} has been APPROVED for ${submission.amount}."
        elif new_status == 'rejected':
            msg = f"Your {display_title} was not approved. Reason: {submission.decision_reason}"
        elif new_status == 'more_info_required':
            notes = extra_data.get('notes', '')
            msg = f"Your {display_title} requires additional information. {notes}".strip()
        elif new_status == 'forwarded':
            msg = f"Your {display_title} has been reviewed and forwarded to the Director for final decision."

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
                display_title, float(submission.amount or 0),
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
                    funding_stream=display_title,
                    bank_name=getattr(student, 'bank_name', '') or '',
                    account_number=getattr(student, 'account_number', '') or '',
                    transit_number=getattr(student, 'transit_number', '') or '',
                    submission_id=submission.id,
                )
        elif new_status == 'rejected':
            email_application_rejected(
                student.email, student.full_name,
                display_title, submission.decision_reason or '',
                submission_id=submission.id,
            )
        elif new_status == 'more_info_required':
            notes = extra_data.get('notes', '')
            email_more_info_requested(
                student.email, student.full_name,
                display_title, notes
            )

    @staticmethod
    def _send_form_b_email(submission):
        """
        Send Form B (Enrollment Verification) to the registrar.
        - Reads registrar email from the student's form answers
        - Creates a FormBResponse record with a unique token
        - Emails the registrar a link to fill in the form online
        - Form A cannot be forwarded until Form B is received
        """
        import uuid
        from django.utils import timezone
        from datetime import timedelta
        from django.conf import settings as django_settings

        try:
            student = submission.student
            answers = {
                a.field.label.lower(): a.answer_text
                for a in submission.answers.select_related('field').all()
                if a.field
            }

            def get(keys):
                for k in keys:
                    v = answers.get(k.lower())
                    if v:
                        return v
                return ''

            registrar_email = get(['registrar email', 'registrar / official email', 'registrar_email'])
            if not registrar_email and student:
                # Fall back to PolicySetting
                from api.models import PolicySetting
                cfg = PolicySetting.objects.filter(section='system_config', field_key='registrar_email').first()
                registrar_email = cfg.unit if cfg else ''

            if not registrar_email:
                import logging
                logging.getLogger(__name__).warning(
                    "No registrar email found for submission %s — Form B not sent", submission.id
                )
                return

            institution = get(['institution name', 'institution', 'school']) or (student.institution_name if student else '')
            program     = get(['program', 'program name']) or (student.program_credential if student else '')
            sem_start   = get(['semester start date', 'semester start', 'start date'])
            sem_end     = get(['semester end date', 'semester end', 'end date'])
            student_dob = str(student.dob or '') if student else ''
            student_id  = get(['student id', 'student number', 'student #']) or (student.upi or student.beneficiary_number or '') if student else ''

            # Create FormBResponse record
            from forms.models import FormBResponse
            token = uuid.uuid4().hex
            expires_at = timezone.now() + timedelta(days=21)  # 21 days to respond

            form_b, _ = FormBResponse.objects.update_or_create(
                submission=submission,
                defaults={
                    'token': token,
                    'registrar_email': registrar_email,
                    'status': 'sent',
                    'student_name': student.full_name if student else '',
                    'institution': institution,
                    'program': program,
                    'sem_start': sem_start,
                    'sem_end': sem_end,
                    'expires_at': expires_at,
                }
            )

            # Build the public Form B link — use FRONTEND_URL from settings
            from django.conf import settings as django_settings
            frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173')
            form_b_link = f"{frontend_url}/form-b/{token}"

            # Send email to registrar
            from notifications.utils import email_form_b_registrar_with_link
            email_form_b_registrar_with_link(
                registrar_email=registrar_email,
                student_name=student.full_name if student else 'Student',
                student_dob=student_dob,
                student_id=student_id,
                institution=institution,
                program=program,
                sem_start=sem_start,
                sem_end=sem_end,
                submission_id=submission.id,
                form_b_link=form_b_link,
            )

        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Form B email failed for submission %s: %s", submission.id, e, exc_info=True)

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
                        form_title=pretty_form_title(submission.form.title) if submission.form else 'Application',
                        amount=float(submission.amount or 0),
                        submission_id=submission.id,
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error("Director approval email failed: %s", e)
