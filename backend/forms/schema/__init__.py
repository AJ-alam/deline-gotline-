"""Typed form schemas — the single source of truth for what a form contains.

Why this exists
---------------
A field's identity used to be its *display string*. The React form hand-mapped
its state onto labels ("Enrollment Status"), those labels became FormField rows,
and the calculation service resolved them back with substring matching:

    get_ans(['credential', 'degree', 'program type'])

Three independent definitions agreeing only by convention, with money at the end
of the chain. Renaming a label, or adding an unrelated field whose label happened
to contain 'degree', silently changed what a student was paid.

Here a field is identified by a stable machine key that never appears on screen.
`label` is presentation and can be reworded freely. `legacy_labels` records the
display strings a field was historically stored under, so existing
SubmissionAnswer rows can be migrated onto keys without guesswork.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from decimal import Decimal, InvalidOperation
from enum import Enum


class FieldType(str, Enum):
    TEXT = 'text'
    LONG_TEXT = 'long_text'
    EMAIL = 'email'
    PHONE = 'phone'
    DATE = 'date'
    MONEY = 'money'
    INTEGER = 'integer'
    CHOICE = 'choice'
    BOOLEAN = 'boolean'
    FILE = 'file'
    SIGNATURE = 'signature'


class FundingType(str, Enum):
    """Which funding stream a form draws from.

    Replaces `Q(form__title__icontains='FormA')`, which made the funding stream a
    property of a human-editable title and could not use an index.
    """

    PSSSP = 'psssp'
    DGGR = 'dggr'
    UCEPP = 'ucepp'


class ValidationError(Exception):
    """Raised when submitted answers do not satisfy the schema."""

    def __init__(self, errors: dict[str, str]):
        self.errors = dict(errors)
        super().__init__(f"{len(self.errors)} invalid field(s): {', '.join(sorted(self.errors))}")


@dataclass(frozen=True)
class Choice:
    value: str          # stored — stable
    label: str          # displayed — free to reword


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: FieldType = FieldType.TEXT
    required: bool = False
    choices: tuple[Choice, ...] = ()
    help_text: str = ''
    # Display strings this field was stored under before schemas existed. Used
    # only by the EAV migration; never for lookup at runtime.
    legacy_labels: tuple[str, ...] = ()

    def __post_init__(self):
        if self.type is FieldType.CHOICE and not self.choices:
            raise ValueError(f"choice field {self.key!r} declares no choices")
        if self.choices and self.type is not FieldType.CHOICE:
            raise ValueError(f"field {self.key!r} has choices but type {self.type.value!r}")

    @property
    def choice_values(self) -> tuple[str, ...]:
        return tuple(c.value for c in self.choices)

    def clean(self, raw):
        """Normalise one submitted value. Raises ValueError with a user-facing message."""
        if raw is None:
            text = ''
        elif isinstance(raw, bool):
            text = 'true' if raw else 'false'
        else:
            text = str(raw).strip()

        if not text:
            if self.required:
                raise ValueError(f"{self.label} is required.")
            return None

        if self.type is FieldType.MONEY:
            # Free-text money has always arrived as '$5,200.00'
            cleaned = text.replace('$', '').replace(',', '').replace(' ', '')
            try:
                value = Decimal(cleaned)
            except (InvalidOperation, ArithmeticError):
                raise ValueError(f"{self.label} must be an amount.")
            if value < 0:
                raise ValueError(f"{self.label} cannot be negative.")
            return value

        if self.type is FieldType.INTEGER:
            try:
                return int(Decimal(text))
            except (InvalidOperation, ArithmeticError, ValueError):
                raise ValueError(f"{self.label} must be a whole number.")

        if self.type is FieldType.BOOLEAN:
            lowered = text.lower()
            if lowered in ('true', 'yes', 'y', '1', 'on'):
                return True
            if lowered in ('false', 'no', 'n', '0', 'off'):
                return False
            raise ValueError(f"{self.label} must be yes or no.")

        if self.type is FieldType.CHOICE:
            lowered = text.lower()
            for choice in self.choices:
                if lowered in (choice.value.lower(), choice.label.lower()):
                    return choice.value
            allowed = ', '.join(c.label for c in self.choices)
            raise ValueError(f"{self.label} must be one of: {allowed}.")

        if self.type is FieldType.EMAIL and '@' not in text:
            raise ValueError(f"{self.label} must be an email address.")

        return text


@dataclass(frozen=True)
class FormSchema:
    slug: str                       # stable identity, e.g. 'form-a'
    title: str                      # display only
    funding_type: FundingType
    fields: tuple[Field, ...]
    description: str = ''

    def __post_init__(self):
        seen = set()
        for f in self.fields:
            if f.key in seen:
                raise ValueError(f"{self.slug}: duplicate field key {f.key!r}")
            seen.add(f.key)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields)

    def field(self, key: str) -> Field:
        for f in self.fields:
            if f.key == key:
                return f
        raise KeyError(f"{self.slug} has no field {key!r}")

    def legacy_label_map(self) -> dict[str, str]:
        """{historical display label (lowercased) -> field key}, for EAV migration."""
        mapping = {}
        for f in self.fields:
            mapping[f.label.lower()] = f.key
            for label in f.legacy_labels:
                mapping[label.lower()] = f.key
        return mapping

    def clean(self, answers: dict) -> dict:
        """Validate submitted answers. Returns cleaned data keyed by field key.

        Unknown keys are rejected rather than ignored — a typo used to become a
        silently-stored answer that nothing ever read.
        """
        errors: dict[str, str] = {}
        cleaned: dict = {}

        for key in answers:
            if key not in self.keys:
                errors[key] = f"Unknown field {key!r} for {self.slug}."

        for f in self.fields:
            try:
                value = f.clean(answers.get(f.key))
            except ValueError as exc:
                errors[f.key] = str(exc)
                continue
            if value is not None:
                cleaned[f.key] = value

        if errors:
            raise ValidationError(errors)
        return cleaned


_REGISTRY: dict[str, FormSchema] = {}


def register(schema: FormSchema) -> FormSchema:
    if schema.slug in _REGISTRY:
        raise ValueError(f"duplicate form schema slug {schema.slug!r}")
    _REGISTRY[schema.slug] = schema
    return schema


def get_schema(slug: str) -> FormSchema:
    try:
        return _REGISTRY[slug]
    except KeyError:
        raise KeyError(f"no form schema registered for {slug!r}")


def all_schemas() -> tuple[FormSchema, ...]:
    return tuple(_REGISTRY[slug] for slug in sorted(_REGISTRY))


from . import form_a  # noqa: E402,F401  (registers the schema)
