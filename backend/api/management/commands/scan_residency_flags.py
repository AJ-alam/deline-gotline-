"""
Re-run the residency consistency check over existing submissions.

The check runs automatically on every new submission, so this command exists for
the applications that were already in the database when it was introduced, and for
re-scanning after the detection rules change.

Dry-run by default:
    python manage.py scan_residency_flags
    python manage.py scan_residency_flags --apply
    python manage.py scan_residency_flags --apply --notify --status pending forwarded
"""

from django.core.management.base import BaseCommand

from forms.models import FormSubmission
from api.services.residency_service import evaluate_submission, notify_staff_of_mismatch


class Command(BaseCommand):
    help = 'Scan existing submissions for declared-residency vs address mismatches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write the results to submission.residency_flag. Without it, nothing is saved.',
        )
        parser.add_argument(
            '--notify', action='store_true',
            help='Also notify staff about newly raised flags. Off by default so a '
                 'historical backfill does not flood the notification list.',
        )
        parser.add_argument(
            '--status', nargs='+', default=None,
            help='Limit to these submission statuses (e.g. pending forwarded).',
        )
        parser.add_argument(
            '--clear-resolved', action='store_true',
            help='Also clear flags on submissions that no longer mismatch.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        notify = options['notify']

        qs = (FormSubmission.objects
              .select_related('form', 'student', 'student__profile')
              .prefetch_related('answers__field')
              .exclude(student=None)
              .order_by('id'))
        if options['status']:
            qs = qs.filter(status__in=options['status'])

        scanned = raised = cleared = unchanged = 0

        # chunk_size is required by iterator() once prefetch_related is in play
        for submission in qs.iterator(chunk_size=200):
            scanned += 1
            mismatch = evaluate_submission(submission)
            new_flag = mismatch['message'] if mismatch else None
            current = submission.residency_flag

            if new_flag and new_flag != current:
                raised += 1
                who = submission.student.email
                self.stdout.write(self.style.WARNING(
                    f"  #{submission.id:<6} {who:<34} {mismatch['kind']}"
                ))
                for signal in mismatch['signals']:
                    self.stdout.write(f"           · {signal}")
                if apply_changes:
                    submission.residency_flag = new_flag
                    submission.save(update_fields=['residency_flag'])
                    if notify:
                        notify_staff_of_mismatch(
                            submission.student, mismatch,
                            link=f"/staff/applications/{submission.id}",
                        )

            elif current and not new_flag and options['clear_resolved']:
                cleared += 1
                self.stdout.write(f"  #{submission.id:<6} flag no longer applies")
                if apply_changes:
                    submission.residency_flag = None
                    submission.save(update_fields=['residency_flag'])

            else:
                unchanged += 1

        self.stdout.write('')
        self.stdout.write(f"Scanned:   {scanned}")
        self.stdout.write(f"Flagged:   {raised}")
        self.stdout.write(f"Cleared:   {cleared}")
        self.stdout.write(f"Unchanged: {unchanged}")
        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                '\nDry run — nothing was saved. Re-run with --apply to store these flags.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('\nFlags written.'))
