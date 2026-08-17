"""Move bank details out of `answers` on applications written before they were routed.

New submissions never put them there. Rows filed earlier still do, and
`Application.answers` is returned whole by the detail endpoint, rendered on the
printable form and copied into the enrolment verification an institution
receives — so those account numbers stay exposed until something moves them.

    python manage.py purge_banking_answers --dry-run
    python manage.py purge_banking_answers

Applications are walked oldest first, so the most recent one a student filed
ends up as their current account rather than whichever row happened to be last.
Nothing is discarded: details go to the account record finance pays from, or —
for a guest application with no account behind it — to the same encrypted store
a SIN uses, where `funding.services.banking.promote` will find them if the
office later attaches the application.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from funding.models import Application
from funding.services import banking


class Command(BaseCommand):
    help = 'Move bank details out of application answers and into account records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Oldest first: set_current retires the previous account each time the
        # details differ, so processing in filing order leaves the newest on top.
        applications = (Application.objects
                        .select_related('student')
                        .order_by('submitted_at', 'id'))

        moved_to_account = held_for_guest = incomplete = stripped = 0

        for application in applications:
            answers = dict(application.answers or {})
            present = [key for key in banking.KEYS if key in answers]
            if not present:
                continue

            values = banking.values_from(answers)
            complete = banking.is_complete(values)
            owner = 'guest' if application.student_id is None else application.student.email

            if not complete:
                incomplete += 1
                self.stdout.write(
                    f'  application {application.pk} ({owner}): partial '
                    f'({", ".join(present)}) — stripped, nothing to record'
                )
            elif application.student_id:
                moved_to_account += 1
                self.stdout.write(
                    f'  application {application.pk} ({owner}): '
                    f'account ****{values["account_number"][-4:]} -> account record'
                )
            else:
                held_for_guest += 1
                self.stdout.write(
                    f'  application {application.pk} (guest): '
                    f'account ****{values["account_number"][-4:]} -> held encrypted'
                )

            if dry_run:
                stripped += 1
                continue

            with transaction.atomic():
                if complete:
                    banking.record(application, values)
                for key in present:
                    answers.pop(key, None)
                application.answers = answers
                application.save(update_fields=['answers', 'updated_at'])
                stripped += 1

        verb = 'would be' if dry_run else 'were'
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{stripped} application(s) {verb} cleared of bank details in answers — '
            f'{moved_to_account} to an account record, {held_for_guest} held for a '
            f'guest application, {incomplete} incomplete and discarded.'
        ))
        if dry_run and stripped:
            self.stdout.write('Re-run without --dry-run to apply.')
