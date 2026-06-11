"""
Management command: send_deadline_reminders
§3.1.F: Students receive deadline reminders before semester application deadlines.

Schedule via cron (run daily):
  0 9 * * *   python manage.py send_deadline_reminders

Sends reminders at 30 days and 7 days before each deadline to students who have
NOT yet submitted for that semester.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Send deadline reminder emails to students with upcoming application deadlines. (§3.1.F)"

    REMINDER_DAYS = [30, 7]  # days before deadline to send reminder

    def handle(self, *args, **options):
        from forms.models import ApplicationDeadline, FormSubmission
        from django.contrib.auth import get_user_model
        from notifications.utils import send_email_notification, _base_template

        User = get_user_model()
        today = timezone.now().date()
        sent_count = 0

        for days_ahead in self.REMINDER_DAYS:
            target_date = today + timedelta(days=days_ahead)

            deadlines = ApplicationDeadline.objects.filter(
                deadline_date__date=target_date,
            )

            for deadline in deadlines:
                self.stdout.write(
                    f"Sending {days_ahead}-day reminders for {deadline} (due {deadline.deadline_date.date()})"
                )

                # Notify all active students who have NOT yet submitted for this semester
                role_filter = User.objects.filter(role='student', is_active=True)
                for student in role_filter:
                    # Skip if already submitted for this stream/semester
                    already_submitted = FormSubmission.objects.filter(
                        student=student,
                        status__in=['pending', 'reviewed', 'forwarded', 'accepted'],
                    ).exists()
                    if already_submitted:
                        continue

                    if not student.email:
                        continue

                    stream_display = deadline.get_funding_stream_display()
                    deadline_date_str = deadline.deadline_date.strftime('%B %d, %Y')
                    body = f"""
                    <h2 style="color: #1e293b;">Application Deadline Reminder</h2>
                    <p>This is a reminder that the application deadline for <strong>{stream_display}</strong>
                    is coming up in <strong>{days_ahead} day(s)</strong>.</p>
                    <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px;
                                padding: 16px; margin: 24px 0;">
                      <p style="margin: 0; font-weight: 700; color: #92400e;">
                        Deadline: {deadline_date_str}
                      </p>
                    </div>
                    <p>If you have not yet submitted your application, please do so as soon as possible
                    to avoid late application processing.</p>
                    <p>Visit the DGG Student Funding Portal to apply.</p>
                    """

                    try:
                        send_email_notification(
                            recipient_email=student.email,
                            subject=f"Reminder: {stream_display} Application Due in {days_ahead} Day(s)",
                            html_body=_base_template(body),
                            plain_body=(
                                f"Reminder: Your {stream_display} application is due in {days_ahead} day(s) "
                                f"({deadline_date_str}). Please submit via the DGG Student Funding Portal."
                            ),
                        )
                        sent_count += 1
                    except Exception as exc:
                        self.stderr.write(f"Failed to email {student.email}: {exc}")

        from api.models import AuditLog
        AuditLog.objects.create(
            action=f"Deadline reminders sent — {sent_count} emails",
            performed_by=None,
            details=f"Run date: {today}",
        )
        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} deadline reminder email(s)."))
