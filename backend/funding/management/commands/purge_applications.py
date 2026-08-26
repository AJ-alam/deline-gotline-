"""Clear case data out of a database before it starts taking real applications.

    python manage.py purge_applications                        # report only
    python manage.py purge_applications --drop-test-accounts   # report only
    python manage.py purge_applications --drop-test-accounts --yes

    # Cut down to a named set of accounts. Deletes staff. Report first.
    python manage.py purge_applications --keep-only=admin@x.ca,director@x.ca
    python manage.py purge_applications --keep-only=admin@x.ca,director@x.ca --yes

Reporting is the default and `--yes` is the only thing that writes, because this
is run twice against two different databases — the local one and production —
and the difference between them is a connection string in the environment. The
banner names the database it is pointed at every time, including on a dry run.

What is removed and what is kept is decided in `core.purge` — it spans three
apps, and `funding/` is barred from reading the enrolment profile at all
(`accounts.test_profile.test_only_prefill_reads_the_profile`). The reasoning
lives there.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import purge as purge_service


class Command(BaseCommand):
    help = 'Delete applications and their case data, keeping accounts and office setup.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help='Actually delete. Without it nothing is written.',
        )
        parser.add_argument(
            '--drop-test-accounts', action='store_true',
            help=('Also delete student accounts on a throwaway domain '
                  f'({", ".join(purge_service.DEFAULT_TEST_DOMAINS)}). '
                  'Staff accounts are never deleted.'),
        )
        parser.add_argument(
            '--test-domains', default='',
            help='Comma-separated domains to treat as throwaway. Overrides the default.',
        )
        parser.add_argument(
            '--keep-outbox', action='store_true',
            help='Leave queued email alone. By default the outbox is emptied.',
        )
        parser.add_argument(
            '--keep-only', default='',
            help=('Comma-separated addresses. Every other account is deleted, '
                  'staff included. Refused if an address matches nothing, or if '
                  'no administrator would survive. Cannot be combined with '
                  '--drop-test-accounts.'),
        )

    def handle(self, *args, **options):
        write = options['yes']
        drop_users = options['drop_test_accounts']
        purge_outbox = not options['keep_outbox']
        domains = tuple(
            d.strip().lstrip('@') for d in options['test_domains'].split(',') if d.strip()
        ) or purge_service.DEFAULT_TEST_DOMAINS
        keep_emails = tuple(
            e.strip() for e in options['keep_only'].split(',') if e.strip()
        )

        database = settings.DATABASES['default']
        target = database.get('NAME') or ''
        if database.get('HOST'):
            target = f"{database['HOST']}/{target}"

        self.stdout.write('')
        self.stdout.write(self.style.WARNING(f'Database: {database["ENGINE"]}'))
        self.stdout.write(self.style.WARNING(f'Target:   {target}'))
        self.stdout.write('')

        try:
            report = (purge_service.purge if write else purge_service.survey)(
                drop_test_accounts=drop_users,
                test_domains=domains,
                purge_outbox=purge_outbox,
                keep_emails=keep_emails,
            )
        except purge_service.PurgeRefused as refusal:
            raise CommandError(str(refusal)) from refusal

        verb = 'Deleted' if write else 'Would delete'
        for label, count in report.counts.items():
            self.stdout.write(f'  {count:>8}  {label}')
        self.stdout.write('')
        self.stdout.write(f'{verb} {report.total} row(s).')

        if drop_users or keep_emails:
            self.stdout.write(
                f'{len(report.users_deleted)} account(s) '
                f'{"deleted" if write else "would go"}; '
                f'{len(report.users_kept)} kept:'
            )
            # Named in full rather than truncated when a keep list is in play:
            # this path deletes staff, and a list that stops at twenty hides
            # exactly the account somebody would have wanted to see on it.
            for email in report.users_kept:
                self.stdout.write(self.style.SUCCESS(f'    keep    {email}'))
            for email in report.users_deleted if keep_emails else report.users_deleted[:20]:
                self.stdout.write(f'    delete  {email}')
            if not keep_emails and len(report.users_deleted) > 20:
                self.stdout.write(f'    ... and {len(report.users_deleted) - 20} more')

        cleared = {k: v for k, v in report.attributions_cleared.items() if v}
        if cleared:
            self.stdout.write('')
            # Plain ASCII deliberately: this is read in a Windows console,
            # where cp1252 turns an em dash into a replacement character. The
            # same encoding that broke 143 queued emails (PROJECT_STATE §6).
            self.stdout.write(self.style.WARNING(
                'Office history is kept, but loses whose name is on it. The '
                'account that acted is being deleted and these columns are '
                'SET_NULL:'
            ))
            for label, count in cleared.items():
                self.stdout.write(f'  {count:>8}  {label}')

        if report.documents_left_on_disk:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'{report.documents_left_on_disk} document row(s) '
                f'{"went" if write else "would go"}, but Django deletes rows and '
                'never the files. The uploads themselves stay under MEDIA_ROOT '
                f'({settings.MEDIA_ROOT}) or in the storage bucket.'
            ))

        self.stdout.write('')
        if write:
            self.stdout.write(self.style.SUCCESS('Done. Office configuration untouched.'))
        else:
            self.stdout.write('Nothing was written. Re-run with --yes to apply.')
