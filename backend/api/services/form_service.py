from django.utils import timezone
from django.contrib.auth import get_user_model
from notifications.models import Notification
from forms.models import FormSubmission, SubmissionNote

User = get_user_model()

class FormService:
    @staticmethod
    def send_submission_notifications(submission):
        form = submission.form
        student = submission.student
        
        # Notify Student
        if student:
            Notification.objects.create(
                user=student,
                title="Application Received",
                message=f"Your application for '{form.title}' has been successfully submitted.",
                link="/dashboard"
            )
        
        # Notify Admins
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

        if new_status == 'reviewed':
            submission.reviewed_at = timezone.now()
            submission.reviewed_by = performed_by
        elif new_status == 'forwarded':
            submission.forwarded_at = timezone.now()
            submission.forwarded_by = performed_by
        elif new_status in ['accepted', 'rejected']:
            submission.decided_at = timezone.now()
            submission.decided_by = performed_by
            submission.decision_reason = extra_data.get('reason', '')
            
            # AUTOMATED CALCULATION & PAYMENT GENERATION
            if new_status == 'accepted':
                from api.services.calculation_service import CalculationService
                CalculationService.calculate_and_pay(submission)
        
        submission.save()
        
        # Status Change Notification
        if submission.student:
            FormService._send_status_notification(submission, new_status)
            
        return submission

    @staticmethod
    def _send_status_notification(submission, new_status):
        title = f"Application Update: {new_status.capitalize()}"
        msg = f"Your application for '{submission.form.title}' is now '{new_status}'."
        
        if new_status == 'accepted':
            msg = f"Congratulations! Your application has been APPROVED for ${submission.amount}."
        elif new_status == 'rejected':
            msg = f"Your application was not approved. Reason: {submission.decision_reason}"

        Notification.objects.create(
            user=submission.student,
            title=title,
            message=msg,
            link=f"/dashboard"
        )
