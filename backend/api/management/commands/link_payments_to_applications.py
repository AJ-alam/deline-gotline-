"""Backfill Payment.application for existing rows that only carry a submission FK.

Older payments (created before calculation_service started auto-linking) carry
a `submission` reference but no `application`, which makes them appear as
"No application linked" on the Payments dashboard. This command walks every
Payment with submission set + application null, derives the matching
Application (creating one if needed), and updates the FK.

Idempotent: re-running the command is safe — rows already linked are skipped.

Usage:
    python manage.py link_payments_to_applications
    python manage.py link_payments_to_applications --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Payment
from api.services.calculation_service import _resolve_or_create_application


class Command(BaseCommand):
    help = "Link existing payments to their matching Application row."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        qs = Payment.objects.filter(application__isnull=True, submission__isnull=False).select_related('submission', 'submission__form', 'user')
        total = qs.count()
        self.stdout.write(f"Found {total} payment(s) with submission but no application.")

        linked = 0
        skipped = 0
        with transaction.atomic():
            for p in qs.iterator():
                app = _resolve_or_create_application(p.submission)
                if not app:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(
                        f"  skip payment #{p.id} — could not resolve application "
                        f"(submission #{p.submission_id}, form='{p.submission.form.title if p.submission.form else '?'}')"
                    ))
                    continue
                if not dry_run:
                    p.application = app
                    p.save(update_fields=['application'])
                linked += 1
                self.stdout.write(
                    f"  payment #{p.id} -> application #{app.id} ({app.form_type})"
                )
            if dry_run:
                transaction.set_rollback(True)

        action = "would link" if dry_run else "linked"
        self.stdout.write(self.style.SUCCESS(f"Done — {action} {linked}, skipped {skipped}."))
