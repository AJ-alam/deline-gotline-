"""Install the office's published configuration. Nothing else.

    python manage.py seed_policies

The rates every award is computed from, the published deadlines, and a rule set
in force. This is what a database needs before it can price anything, and it is
all a *production* database should be given: `seed_demo` adds accounts and is
for local work, and its accounts share one published password.

Written because `migrate` deliberately installs no rates. Migration 0013 returns
early on a database with none, so that a test proving what happens when a rate
is missing finds one missing rather than passing for the wrong reason — correct
for the suite, and it leaves a fresh deployment with an empty policy table and
no way to price an application.

`build.sh` has called this command since before it existed, which is its own
small lesson: a deploy step naming a command nobody had written fails at the
moment of cut-over, and nothing before then says so.

Idempotent — every write is an update_or_create and a rule set is published only
when none is — so a deploy hook can run it unconditionally.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from funding.models import Application
from funding.office_config import install


class Command(BaseCommand):
    help = "Install the office's funding rates, deadlines and rule set."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Run against a database that already holds applications.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # A rate reset under a decision that was priced with it is not something
        # to do by accident. `install` resets every rate to the seeded figure,
        # which is right for a fresh database and wrong for a running one — after
        # cut-over the policy screen is how a rate changes, because that records
        # who changed it and when it takes effect.
        count = Application.objects.count()
        if count and not options['force']:
            raise SystemExit(
                self.style.ERROR(
                    f'This database holds {count} application(s). seed_policies '
                    'resets every rate to its seeded figure, which would '
                    'overwrite anything the office has edited on the policy '
                    'screen. Pass --force if that is what you mean.'
                )
            )

        self.stdout.write(self.style.MIGRATE_HEADING(
            "The office's configuration"))
        result = install(stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {result['rates']} rates, {result['deadlines']} deadlines, "
            f"rule set {'published' if result['rule_set_published'] else 'already in force'}."
        ))
