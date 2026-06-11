"""
Management command: send_monthly_finance_report
§3.1.E: Finance receives master list before end of month (last Friday before month end).

Schedule via Render/Heroku cron job:
  0 8 * * 5   python manage.py send_monthly_finance_report
  (runs every Friday at 08:00; command self-checks whether this is the last Friday of the month)

Or trigger manually: python manage.py send_monthly_finance_report --force
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import calendar


def _is_last_friday_of_month(d=None):
    if d is None:
        d = timezone.now().date()
    if d.weekday() != 4:  # 4 = Friday
        return False
    # True if no other Friday exists later this month
    next_friday = d.day + 7
    last_day = calendar.monthrange(d.year, d.month)[1]
    return next_friday > last_day


class Command(BaseCommand):
    help = "Send the monthly Finance master list email (§3.1.E). Runs automatically on the last Friday of each month."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Send regardless of whether today is the last Friday of the month.',
        )

    def handle(self, *args, **options):
        today = timezone.now().date()
        force = options.get('force', False)

        if not force and not _is_last_friday_of_month(today):
            self.stdout.write(self.style.WARNING(
                f"{today} is not the last Friday of the month. Use --force to send anyway."
            ))
            return

        self.stdout.write(f"Generating Finance master list for {today}...")

        try:
            from api.views import _build_full_csv
            from email_sender import send_finance_report
            import uuid
            from datetime import timedelta

            csv_bytes, row_count = _build_full_csv(
                all_statuses=False,
                unsent_only=False,  # master list = ALL approved, including already-sent
            )

            # Create a finance confirm token for this batch
            confirm_url = ''
            try:
                from api.models import FinanceConfirmToken
                tok = FinanceConfirmToken.objects.create(
                    token=uuid.uuid4().hex,
                    expires_at=timezone.now() + timedelta(days=30),
                )
                from django.conf import settings
                base = getattr(settings, 'SITE_URL', '').rstrip('/')
                confirm_url = f"{base}/api/finance-confirm/{tok.token}/"
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not create confirm token: {e}"))

            ok = send_finance_report(
                csv_bytes=csv_bytes,
                total_students=row_count,
                triggered_by=f"Automated monthly report ({today})",
                confirm_url=confirm_url,
            )

            if ok:
                from api.models import AuditLog
                AuditLog.objects.create(
                    action=f"Automated monthly Finance report sent — {row_count} records",
                    performed_by=None,
                    details=f"Scheduled run on {today}",
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Finance master list sent: {row_count} records."
                ))
            else:
                self.stderr.write("Email send failed — check FINANCE_EMAIL and SMTP settings.")

        except Exception as exc:
            self.stderr.write(f"Error: {exc}")
            raise
