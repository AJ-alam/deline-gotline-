"""Remove answers whose question no longer exists.

A schema is code, so a form can change between deploys — a field renamed, split
in two, or dropped. Applications filed before the change keep the old keys, and
nothing reads them: `answers` is rendered from the schema, so a key the schema
does not define is invisible on every screen while still being returned by the
API and printed into the decision `inputs` snapshot.

They are not harmless. They are answers to questions nobody can see, sitting in
the record an award is defended from.

Deliberately *not* pruned: keys the server itself writes. `confirmed_tuition`
and the semester dates come from the registrar's confirmation, and the
application's own schema has no question for them because the student is never
asked. Those are carried, not stale — see `verification.CONFIRMABLE_KEYS` and
the amendment path that preserves them.

Reports and changes nothing unless `--apply` is given, because this deletes
answers and the reason a key is unknown might be a schema someone is midway
through changing.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from funding.models import Application
from funding.schemas import get_schema
from funding.services.verification import CONFIRMABLE_KEYS


def stale_keys(application) -> list[str]:
    """Answers on this application that no question defines and nothing wrote."""
    try:
        schema = get_schema(application.type)
    except Exception:
        # An application of a type that no longer exists at all. Left alone:
        # that is a bigger thing than a stray answer and wants a person.
        return []
    return sorted(
        key for key in (application.answers or {})
        if key not in schema.keys and key not in CONFIRMABLE_KEYS
    )


class Command(BaseCommand):
    help = 'Remove answers whose question the schema no longer defines.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write the changes. Without it, nothing is modified.')

    def handle(self, *args, **options):
        by_type: dict[str, dict[str, int]] = {}
        affected = []

        for application in Application.objects.only('id', 'type', 'answers'):
            keys = stale_keys(application)
            if not keys:
                continue
            affected.append((application, keys))
            counts = by_type.setdefault(application.type, {})
            for key in keys:
                counts[key] = counts.get(key, 0) + 1

        if not affected:
            self.stdout.write(self.style.SUCCESS(
                'No stale answers. Every stored answer has a question.'))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'{len(affected)} application(s) carry answers no schema defines'))
        for application_type, counts in sorted(by_type.items()):
            self.stdout.write(f'  {application_type}')
            for key, count in sorted(counts.items(), key=lambda item: -item[1]):
                self.stdout.write(f'      {key:32} on {count} application(s)')

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                '\nNothing changed. Re-run with --apply to remove them.'))
            return

        with transaction.atomic():
            for application, keys in affected:
                answers = dict(application.answers or {})
                for key in keys:
                    answers.pop(key, None)
                application.answers = answers
                application.save(update_fields=['answers', 'updated_at'])

        self.stdout.write(self.style.SUCCESS(
            f'\nRemoved stale answers from {len(affected)} application(s).'))
