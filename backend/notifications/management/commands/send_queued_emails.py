"""Deliver queued email. Run on a schedule (cron, Vercel Cron, or a worker).

    python manage.py send_queued_emails
    python manage.py send_queued_emails --limit 200
"""

from django.core.management.base import BaseCommand

from notifications.delivery import deliver_pending


class Command(BaseCommand):
    help = 'Deliver pending outbound email.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50,
                            help='Maximum messages to attempt in this run.')

    def handle(self, *args, **options):
        result = deliver_pending(limit=options['limit'])
        self.stdout.write(
            self.style.SUCCESS(f"sent {result['sent']}, failed {result['failed']}")
        )
