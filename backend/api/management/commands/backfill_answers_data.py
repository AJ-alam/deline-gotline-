"""Convert SubmissionAnswer rows onto stable schema keys in FormSubmission.answers_data.

Existing answers are keyed by display string ('Enrollment Status', 'Course Load',
'courseLoad' — all the same field). forms.schema records every historical label
per field, so this maps them onto one stable key instead of guessing.

Read-only unless --apply is passed. Always reports what it could not map rather
than dropping it, because an unmapped answer is a field the schema is missing.

    python manage.py backfill_answers_data                    # dry run, all forms
    python manage.py backfill_answers_data --slug form-a
    python manage.py backfill_answers_data --slug form-a --apply
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from forms.answer_ingest import map_legacy_answers
from forms.models import FormSubmission
from forms.schema import ValidationError, all_schemas, get_schema


class Command(BaseCommand):
    help = "Backfill FormSubmission.answers_data from legacy SubmissionAnswer rows."

    def add_arguments(self, parser):
        parser.add_argument('--slug', help='Only this schema slug (e.g. form-a).')
        parser.add_argument('--apply', action='store_true',
                            help='Write the results. Without it, nothing is saved.')
        parser.add_argument('--limit', type=int, help='Process at most N submissions.')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        slug = options.get('slug')

        schemas = [get_schema(slug)] if slug else list(all_schemas())
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nBackfilling {len(schemas)} schema(s){' — DRY RUN' if not apply_changes else ''}"
        ))

        for schema in schemas:
            self._backfill_schema(schema, apply_changes, options.get('limit'))

    def _backfill_schema(self, schema, apply_changes, limit):
        # Match submissions to a schema by the form title they were filed under.
        # Title matching is exactly what this migration exists to remove, so it is
        # used once here, deliberately, and never at runtime.
        title_token = schema.slug.replace('-', ' ')
        qs = (FormSubmission.objects
              .filter(form__title__icontains=title_token)
              .select_related('form')
              .prefetch_related('answers__field')
              .order_by('id'))
        if limit:
            qs = qs[:limit]

        total = qs.count() if not limit else len(qs)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n== {schema.slug} ({schema.title}) =="))
        self.stdout.write(f"  matching submissions: {total}")
        if not total:
            return

        mapped = skipped = invalid = 0
        unmapped_labels: dict[str, int] = {}

        with transaction.atomic():
            for submission in qs:
                # Same mapping the live submit path uses — one implementation, so
                # the backfill and the dual-write cannot disagree.
                raw, unmapped = map_legacy_answers(schema, submission.answers.all())
                for label, count in unmapped.items():
                    unmapped_labels[label] = unmapped_labels.get(label, 0) + count

                if not raw:
                    skipped += 1
                    continue

                try:
                    cleaned = schema.clean(raw)
                except ValidationError as exc:
                    # Report rather than write partial data — these are the rows a
                    # human needs to look at before cutover.
                    invalid += 1
                    self.stdout.write(self.style.WARNING(
                        f"  submission #{submission.id}: "
                        + '; '.join(f'{k}: {v}' for k, v in sorted(exc.errors.items()))
                    ))
                    continue

                if apply_changes:
                    submission.answers_data = {
                        k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                        for k, v in cleaned.items()
                    }
                    submission.schema_slug = schema.slug
                    submission.save(update_fields=['answers_data', 'schema_slug'])
                mapped += 1

            if not apply_changes:
                transaction.set_rollback(True)

        verb = 'mapped' if apply_changes else 'would map'
        self.stdout.write(f"  {verb}: {mapped}   no answers: {skipped}   needs review: {invalid}")

        if unmapped_labels:
            self.stdout.write(self.style.WARNING(
                "\n  Labels with no schema field (add them to the schema before cutover):"))
            for label, count in sorted(unmapped_labels.items(), key=lambda kv: -kv[1]):
                self.stdout.write(f"    {count:>5}x  {label!r}")
        else:
            self.stdout.write(self.style.SUCCESS("  every stored label mapped to a field"))
