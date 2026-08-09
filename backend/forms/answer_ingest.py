"""Convert legacy label-keyed answers into schema-keyed answers_data.

Shared by the live submit path (dual-write) and the backfill command, so the two
cannot drift. Drift between two copies of the same mapping is the exact failure
this whole migration exists to remove.

During migration SubmissionAnswer stays authoritative. A submission whose answers
cannot be cleaned is recorded as unconverted rather than rejected — the student's
application must not fail because the new schema is still catching up.
"""

import logging

from .schema import FormSchema, ValidationError, all_schemas

logger = logging.getLogger(__name__)


def resolve_schema_for_title(title: str) -> FormSchema | None:
    """Match a Form to its schema by title.

    Title matching is precisely what this migration removes, so it lives here,
    used once at the boundary, and never in pricing. Once a form carries a
    schema_slug of its own this function stops being called for it.
    """
    lowered = (title or '').lower().replace('—', ' ').replace('-', ' ')
    lowered = ' '.join(lowered.split())
    for schema in all_schemas():
        token = schema.slug.replace('-', ' ')          # 'form-a' -> 'form a'
        compact = schema.slug.replace('-', '')          # 'form-a' -> 'forma'
        if token in lowered or compact in lowered.replace(' ', ''):
            return schema
    return None


def map_legacy_answers(schema: FormSchema, answers) -> tuple[dict, dict[str, int]]:
    """Map SubmissionAnswer rows onto schema keys.

    Returns (raw values keyed by field key, {unmapped label: count}). Unmapped
    labels are returned rather than dropped — an unmapped label means the schema
    is missing a field, which a human needs to see.
    """
    label_map = schema.legacy_label_map()
    raw: dict = {}
    unmapped: dict[str, int] = {}

    for answer in answers:
        field = getattr(answer, 'field', None)
        if not field:
            continue
        label = (field.label or '').strip()
        key = label_map.get(label.lower())
        if not key:
            unmapped[label] = unmapped.get(label, 0) + 1
            continue
        value = answer.answer_text
        if not value and getattr(answer, 'answer_file', None):
            value = 'provided'      # a file answer carries no text
        if value:
            raw[key] = value

    return raw, unmapped


def _jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)       # Decimal, date — JSON needs a primitive


def capture_answers_data(submission, schema: FormSchema | None = None) -> bool:
    """Populate submission.answers_data from its SubmissionAnswer rows.

    Returns True when answers_data was written. Never raises: during migration a
    conversion problem must not break the submission that triggered it.
    """
    try:
        schema = schema or resolve_schema_for_title(
            submission.form.title if submission.form else ''
        )
        if schema is None:
            return False        # form has no schema yet — EAV only, as before

        raw, unmapped = map_legacy_answers(schema, submission.answers.all())
        if unmapped:
            logger.warning(
                "Submission %s: %d label(s) have no field in %s: %s",
                submission.id, len(unmapped), schema.slug,
                ', '.join(sorted(unmapped)),
            )
        if not raw:
            return False

        try:
            cleaned = schema.clean(raw)
        except ValidationError as exc:
            # Expected while the schema is still being tightened against real data.
            logger.warning(
                "Submission %s not converted to %s: %s",
                submission.id, schema.slug,
                '; '.join(f'{k}: {v}' for k, v in sorted(exc.errors.items())),
            )
            return False

        submission.answers_data = {k: _jsonable(v) for k, v in cleaned.items()}
        submission.schema_slug = schema.slug
        submission.save(update_fields=['answers_data', 'schema_slug'])
        return True

    except Exception:
        logger.exception(
            "Failed to capture answers_data for submission %s",
            getattr(submission, 'id', '?'),
        )
        return False
