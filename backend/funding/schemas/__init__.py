"""What each kind of application asks for.

A field is identified by a stable machine key. `label` is presentation and can be
reworded without touching anything downstream. This replaces an arrangement where
a field's identity *was* its display string: the React form hand-mapped its state
onto labels, those became FormField rows, and award calculation resolved them
back by substring matching — so renaming a label could change what a student
was paid.

One definition per application type, feeding API validation, generated
TypeScript types, the rendered form and the PDF. There is no separate frontend
copy to drift out of step.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    PERCENT = 'percent'
    CHOICE = 'choice'
    BOOLEAN = 'boolean'
    FILE = 'file'
    SIGNATURE = 'signature'


class SchemaError(Exception):
    """A schema is defined incorrectly. Raised at import, never at runtime."""


class ValidationError(Exception):
    """Submitted answers do not satisfy the schema."""

    def __init__(self, errors: dict[str, str]):
        self.errors = dict(errors)
        super().__init__(
            f"{len(self.errors)} invalid field(s): {', '.join(sorted(self.errors))}"
        )


@dataclass(frozen=True)
class Choice:
    value: str      # stored — stable
    label: str      # displayed — free to reword


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: FieldType = FieldType.TEXT
    required: bool = False
    choices: tuple[Choice, ...] = ()
    help_text: str = ''
    section: str = ''       # groups fields for rendering; carries no logic

    def __post_init__(self):
        if self.type is FieldType.CHOICE and not self.choices:
            raise SchemaError(f'choice field {self.key!r} declares no choices')
        if self.choices and self.type is not FieldType.CHOICE:
            raise SchemaError(
                f'field {self.key!r} has choices but type {self.type.value!r}'
            )
        if self.key != self.key.lower() or ' ' in self.key or '-' in self.key:
            raise SchemaError(
                f'field key {self.key!r} must be lower_snake_case'
            )

    @property
    def choice_values(self) -> tuple[str, ...]:
        return tuple(c.value for c in self.choices)

    def clean(self, raw):
        """Normalise one submitted value. Raises ValueError with a message for the applicant."""
        if raw is None:
            text = ''
        elif isinstance(raw, bool):
            text = 'true' if raw else 'false'
        else:
            text = str(raw).strip()

        if not text:
            if self.required:
                raise ValueError(f'{self.label} is required.')
            return None

        if self.type is FieldType.MONEY:
            cleaned = text.replace('$', '').replace(',', '').replace(' ', '')
            try:
                value = Decimal(cleaned)
            except (InvalidOperation, ArithmeticError):
                raise ValueError(f'{self.label} must be an amount.')
            if value < 0:
                raise ValueError(f'{self.label} cannot be negative.')
            # Stored to the cent, so '6000' and '6000.00' cannot both exist as
            # representations of the same amount. Answers are compared as
            # strings once written to JSON, and two spellings of one figure
            # would not match.
            return value.quantize(Decimal('0.01'))

        if self.type in (FieldType.INTEGER, FieldType.PERCENT):
            try:
                value = Decimal(text.replace('%', '').strip())
            except (InvalidOperation, ArithmeticError):
                raise ValueError(f'{self.label} must be a number.')
            if self.type is FieldType.PERCENT:
                if not (0 <= value <= 100):
                    raise ValueError(f'{self.label} must be between 0 and 100.')
                return value
            return int(value)

        if self.type is FieldType.BOOLEAN:
            lowered = text.lower()
            if lowered in ('true', 'yes', 'y', '1', 'on'):
                return True
            if lowered in ('false', 'no', 'n', '0', 'off'):
                return False
            raise ValueError(f'{self.label} must be yes or no.')

        if self.type is FieldType.CHOICE:
            lowered = text.lower()
            for choice in self.choices:
                if lowered in (choice.value.lower(), choice.label.lower()):
                    return choice.value
            allowed = ', '.join(c.label for c in self.choices)
            # Never fall through to a default: doing so is what silently paid a
            # graduating Bachelor at the certificate rate.
            raise ValueError(f'{self.label} must be one of: {allowed}.')

        if self.type is FieldType.EMAIL and '@' not in text:
            raise ValueError(f'{self.label} must be an email address.')

        return text


@dataclass(frozen=True)
class ApplicationSchema:
    """The questions one application type asks.

    `slug` matches the ApplicationType value it belongs to, so there is exactly
    one name for a thing across the schema, the model and the API.
    """

    slug: str
    fields: tuple[Field, ...]

    def __post_init__(self):
        seen = set()
        for f in self.fields:
            if f.key in seen:
                raise SchemaError(f'{self.slug}: duplicate field key {f.key!r}')
            seen.add(f.key)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields)

    def field(self, key: str) -> Field:
        for f in self.fields:
            if f.key == key:
                return f
        raise KeyError(f'{self.slug} has no field {key!r}')

    @property
    def sections(self) -> tuple[str, ...]:
        ordered = []
        for f in self.fields:
            if f.section and f.section not in ordered:
                ordered.append(f.section)
        return tuple(ordered)

    def clean(self, answers: dict) -> dict:
        """Validate submitted answers, returning values keyed by field key.

        Reports every problem at once rather than the first, and rejects unknown
        keys instead of storing an answer nothing will ever read.
        """
        errors: dict[str, str] = {}
        cleaned: dict = {}

        for key in answers:
            if key not in self.keys:
                errors[key] = f'Unknown field {key!r} for {self.slug}.'

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


_REGISTRY: dict[str, ApplicationSchema] = {}


def register(schema: ApplicationSchema) -> ApplicationSchema:
    if schema.slug in _REGISTRY:
        raise SchemaError(f'duplicate schema slug {schema.slug!r}')
    _REGISTRY[schema.slug] = schema
    return schema


def get_schema(slug: str) -> ApplicationSchema:
    try:
        return _REGISTRY[slug]
    except KeyError:
        raise KeyError(f'no schema registered for {slug!r}')


def all_schemas() -> tuple[ApplicationSchema, ...]:
    return tuple(_REGISTRY[slug] for slug in sorted(_REGISTRY))


from . import admission          # noqa: E402,F401
from . import graduation_bursary  # noqa: E402,F401
from . import remaining           # noqa: E402,F401
