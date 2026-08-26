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

from collections.abc import Callable
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
    PERCENT = 'percent'
    CHOICE = 'choice'
    BOOLEAN = 'boolean'
    # A declaration the applicant must actively agree to. Deliberately not a
    # BOOLEAN: 'no' is a valid answer to a question about a fact, and never a
    # valid answer to "do you confirm this is true". A required BOOLEAN accepts
    # False — it is non-empty, so it satisfies `required` — which meant a
    # declaration could be filed with the box explicitly unticked.
    CONFIRM = 'confirm'
    FILE = 'file'
    # Several files answering one question. A travel claim is the case that
    # forced it: a trip has a boarding pass, a hotel folio and four taxi
    # receipts, and a single-file question means the applicant either photographs
    # them all onto one page or leaves most of them out. Stored as a list of the
    # same `document:N` references a single FILE stores one of.
    FILES = 'files'
    # Rows of the same few questions, entered as many times as the applicant
    # needs. An expense breakdown is the case: a description and an amount,
    # repeated. Not modelled as expense_1_amount … expense_6_amount, which caps
    # the claim at whatever number was guessed and puts the row number into the
    # field's identity.
    TABLE = 'table'
    SIGNATURE = 'signature'
    # A government identifier. Validated like any other field, but never stored
    # in `answers` and never returned to a client — see
    # funding.services.identifiers and ApplicationSchema.sensitive_keys.
    SIN = 'sin'


class SchemaError(Exception):
    """A schema is defined incorrectly. Raised at import, never at runtime."""


class ValidationError(Exception):
    """Submitted answers do not satisfy the schema."""

    def __init__(self, errors: dict[str, str]):
        self.errors = dict(errors)
        super().__init__(
            f"{len(self.errors)} invalid field(s): {', '.join(sorted(self.errors))}"
        )


def _clean_sin(text: str, label: str) -> str:
    """A Social Insurance Number, or a message explaining why it is not one.

    Checked properly rather than merely counted. A SIN carries a Luhn check
    digit, so a transposed pair — the commonest typing mistake — is detectable.
    A wrong SIN that passes validation is worse than a missing one: it is filed
    against a real person who is not the applicant.
    """
    digits = ''.join(character for character in text if character.isdigit())
    if len(digits) != 9:
        raise ValueError(f'{label} must be exactly 9 digits.')
    if digits[0] == '0':
        raise ValueError(f'{label} does not start with 0 in any valid range.')

    total = 0
    for index, digit in enumerate(int(character) for character in digits):
        if index % 2:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += digit
    if total % 10 != 0:
        raise ValueError(
            f'{label} is not valid. Check the digits — one may be mistyped or '
            'two transposed.'
        )
    return digits


def _is_blank(value) -> bool:
    """Whether a cell was left alone.

    False counts as blank *for this purpose only* — an untouched checkbox in an
    otherwise empty row does not make it a row. Everywhere else a `False` is a
    real answer, which is the distinction `isAnswered` draws on the client and
    the one `FieldType.CONFIRM` exists to protect.
    """
    return value is None or value is False or str(value).strip() == ''


# Types that cannot be a column of a table.
#
# A file is uploaded and referenced, not typed, and a per-row upload is a
# different interaction from the one this renders. A SIN or a declaration inside
# a repeating row is a category error: neither is a thing you have several of.
NOT_A_COLUMN = frozenset({
    FieldType.FILE, FieldType.FILES, FieldType.TABLE,
    FieldType.SIN, FieldType.CONFIRM, FieldType.SIGNATURE,
})


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

    # Asked, validated, and then kept out of `answers` entirely.
    #
    # `Application.answers` is returned whole by the detail endpoint, printed on
    # the paper form and copied into the enrolment verification sent to the
    # institution. Anything here is split off before the row is written and
    # routed to where it belongs — a SIN to an encrypted identifier, bank
    # details to the account record finance actually pays from. A SIN is
    # private whatever this says; see `private_keys`.
    private: bool = False

    # The questions one row of a TABLE asks. Ordinary Fields, so a column cleans
    # its own cell by exactly the rules the same type obeys anywhere else —
    # there is no second, weaker notion of "an amount" that applies only inside
    # a table.
    columns: tuple['Field', ...] = ()

    # The most rows, or files, this will accept. Not a design limit but a
    # refusal: `answers` is a JSON column and a client that can post an
    # unbounded list can post a million of them.
    max_items: int = 0

    # Worked out by the server from the other answers, never asked.
    #
    # A travel claim's total is the sum of its expense lines. Asking for it as
    # well means two figures that can disagree, and the one the rules engine
    # reads is the one that gets paid — so the applicant could be paid against a
    # total nothing on their form adds up to. See `ApplicationSchema.derive`.
    computed: bool = False

    # Opens with today's date.
    #
    # For the one thing a date field is used for that is not a fact being
    # reported: the date a declaration was signed, which is always the day it is
    # being filled in. Filled by the client, so it works for a guest submission
    # too — the practicum report is claimed by an employer with no account, and
    # a server-side prefill would leave exactly those people typing it.
    #
    # It stays editable and the server validates it like any other date; nothing
    # downstream trusts it. `submitted_at` is the record of when this actually
    # arrived, and it is written by the server.
    defaults_to_today: bool = False

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
        # An optional declaration is a contradiction: nothing would be declared
        # by leaving it blank, and the form would submit anyway.
        if self.type is FieldType.CONFIRM and not self.required:
            raise SchemaError(f'confirm field {self.key!r} must be required')

        if self.type is FieldType.TABLE and not self.columns:
            raise SchemaError(f'table field {self.key!r} declares no columns')
        if self.columns and self.type is not FieldType.TABLE:
            raise SchemaError(
                f'field {self.key!r} has columns but type {self.type.value!r}'
            )
        for column in self.columns:
            if column.type in NOT_A_COLUMN:
                raise SchemaError(
                    f'{self.key}.{column.key}: {column.type.value!r} cannot be a '
                    'table column'
                )
            if column.private or column.computed:
                raise SchemaError(
                    f'{self.key}.{column.key}: a column cannot be private or computed'
                )

        # A computed field is never rendered and never submitted, so a renderer
        # counting it among the unanswered required questions would disable the
        # submit button on a question nobody can answer.
        if self.computed and self.required:
            raise SchemaError(
                f'computed field {self.key!r} cannot also be required'
            )

        if self.defaults_to_today and self.type is not FieldType.DATE:
            raise SchemaError(
                f'field {self.key!r} defaults to today but is a '
                f'{self.type.value!r}, not a date'
            )

    @property
    def choice_values(self) -> tuple[str, ...]:
        return tuple(c.value for c in self.choices)

    def _clean_files(self, raw) -> list[str] | None:
        """The references for a many-file question.

        Accepts one reference or several. Duplicates are dropped rather than
        rejected: attaching the same receipt twice is a slip, not an error, and
        it would be reviewed as two receipts.
        """
        if raw is None or raw == '':
            items: list = []
        elif isinstance(raw, (list, tuple)):
            items = list(raw)
        else:
            items = [raw]

        references: list[str] = []
        for item in items:
            text = str(item).strip()
            if text and text not in references:
                references.append(text)

        if not references:
            if self.required:
                raise ValueError(f'{self.label} is required.')
            return None
        if self.max_items and len(references) > self.max_items:
            raise ValueError(
                f'{self.label}: {len(references)} files attached, and the limit '
                f'is {self.max_items}.'
            )
        return references

    def _clean_rows(self, raw) -> list[dict] | None:
        """The rows of a table, each cleaned by its own columns.

        Blank rows are dropped, not refused: the form offers empty rows to type
        into and a claim with three expenses should not be rejected for leaving
        the fourth alone.

        Cell problems are gathered into one message against the table. The error
        contract is flat — one message per field key — and inventing a nested
        one here would mean every client that renders errors has to learn a
        second shape for a single field type.
        """
        if raw is None or raw == '':
            rows: list = []
        elif isinstance(raw, (list, tuple)):
            rows = list(raw)
        else:
            raise ValueError(f'{self.label} must be a list of rows.')

        cleaned: list[dict] = []
        problems: list[str] = []

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError(f'{self.label}: row {index} is not a set of answers.')
            unknown = set(row) - {column.key for column in self.columns}
            if unknown:
                raise ValueError(
                    f'{self.label}: row {index} has no '
                    f'{", ".join(sorted(unknown))} column.'
                )
            if all(_is_blank(row.get(column.key)) for column in self.columns):
                continue

            values: dict = {}
            for column in self.columns:
                try:
                    value = column.clean(row.get(column.key))
                except ValueError as exc:
                    problems.append(f'Row {index}: {exc}')
                    continue
                if value is not None:
                    values[column.key] = value
            cleaned.append(values)

        if problems:
            raise ValueError(' '.join(problems))
        if not cleaned:
            if self.required:
                raise ValueError(f'{self.label} needs at least one row.')
            return None
        if self.max_items and len(cleaned) > self.max_items:
            raise ValueError(
                f'{self.label}: {len(cleaned)} rows entered, and the limit is '
                f'{self.max_items}.'
            )
        return cleaned

    def clean(self, raw):
        """Normalise one submitted value. Raises ValueError with a message for the applicant."""
        # Both hold a list, so neither can go through the stringifying below:
        # str(['document:1']) is a plausible-looking answer that means nothing.
        if self.type is FieldType.FILES:
            return self._clean_files(raw)
        if self.type is FieldType.TABLE:
            return self._clean_rows(raw)

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

        if self.type is FieldType.CONFIRM:
            if text.lower() in ('true', 'yes', 'y', '1', 'on'):
                return True
            # Never falls through to the boolean branch: returning False here
            # would file the application with the declaration refused.
            raise ValueError(f'{self.label} must be confirmed before submitting.')

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

        if self.type is FieldType.SIN:
            return _clean_sin(text, self.label)

        return text


@dataclass(frozen=True)
class ApplicationSchema:
    """The questions one application type asks.

    `slug` matches the ApplicationType value it belongs to, so there is exactly
    one name for a thing across the schema, the model and the API.
    """

    slug: str
    fields: tuple[Field, ...]

    # One line telling an applicant what this is for. Nine similar official
    # names in a list is not a choice most people can make; this is what turns
    # it into one.
    summary: str = ''

    # Whether a student may start this themselves.
    #
    # The enrolment verification is the registrar's form, reached only from an
    # emailed single-use link. Offering it in the portal's "apply for funding"
    # list invites a student to file the institution's declaration about
    # themselves — the answers cannot reach their award (see
    # verification.CONFIRMABLE_KEYS) but the record is nonsense and lands in the
    # staff queue as work.
    apply_in_portal: bool = True

    # Answers the server works out from the others, run after validation.
    #
    # Takes the cleaned answers and returns the values to add. Every key it
    # returns must be declared as a `computed` field, so the derived answer has
    # a label, a type and a place on the review screen like any other — it is
    # not a value that appears from nowhere at pricing time.
    derive: Callable[[dict], dict] | None = dataclass_field(default=None)

    def __post_init__(self):
        seen = set()
        for f in self.fields:
            if f.key in seen:
                raise SchemaError(f'{self.slug}: duplicate field key {f.key!r}')
            seen.add(f.key)

        if self.computed_keys and self.derive is None:
            raise SchemaError(
                f'{self.slug}: computed field(s) '
                f'{", ".join(self.computed_keys)} and nothing derives them'
            )
        if self.derive is not None and not self.computed_keys:
            raise SchemaError(f'{self.slug}: derives answers but declares none computed')

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields)

    @property
    def computed_keys(self) -> tuple[str, ...]:
        """Answers the server works out. Never asked, never accepted."""
        return tuple(f.key for f in self.fields if f.computed)

    @property
    def sensitive_keys(self) -> tuple[str, ...]:
        """Government identifiers. Encrypted, and read only with a reason."""
        return tuple(f.key for f in self.fields if f.type is FieldType.SIN)

    @property
    def private_keys(self) -> tuple[str, ...]:
        """Answers that must never reach the `answers` column.

        Validated with everything else and then split off before the
        application is written, so there is no path by which one lands in a
        JSON blob that the detail endpoint returns whole.

        A SIN qualifies by its type — that cannot be forgotten when a schema
        declares one. Everything else says so for itself.
        """
        return tuple(f.key for f in self.fields
                     if f.private or f.type is FieldType.SIN)

    def split_private(self, answers: dict) -> tuple[dict, dict]:
        """Separate what may be stored as an answer from what may not.

        Called between validation and writing, so a withheld value is never in
        the dictionary that becomes `Application.answers` — not even briefly,
        and not on an error path that might log it.
        """
        private = set(self.private_keys)
        return (
            {k: v for k, v in answers.items() if k not in private},
            {k: v for k, v in answers.items() if k in private},
        )

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

    def clean(self, answers: dict, *, revising: bool = False,
              private_on_file: frozenset[str] = frozenset()) -> dict:
        """Validate submitted answers, returning values keyed by field key.

        Reports every problem at once rather than the first, and rejects unknown
        keys instead of storing an answer nothing will ever read.

        `revising` is for an application that already exists. A private answer —
        a SIN, a bank account — is split off at submission and is never returned
        by anything, so re-posting a stored application means posting it without
        them. Required, they were then reported missing on every edit of every
        form that asks for one: the office could not correct such an
        application, and neither could the student answering a request for more
        information. Absent means unchanged; a value that *is* sent is validated
        exactly as at submission.

        `private_on_file` names private answers the server already holds for
        this applicant - in practice the banking fields, when the student has a
        current `BankAccount`. Banking is required on every form that pays out,
        and `account_number` is deliberately never returned by anything, so a
        student who gave it once would be asked to type it again on every later
        application and be unable to submit without it. Blank means "use what is
        on file"; a value that *is* sent replaces it and is validated exactly as
        at submission.
        """
        errors: dict[str, str] = {}
        cleaned: dict = {}

        for key in answers:
            if key not in self.keys:
                errors[key] = f'Unknown field {key!r} for {self.slug}.'

        for f in self.fields:
            # Matched the way `private_keys` matches — a SIN qualifies by its
            # type, and a rule that checked only the flag would leave exactly
            # the field this exists for still required.
            if (_is_blank(answers.get(f.key)) and f.key in self.private_keys
                    and (revising or f.key in private_on_file)):
                continue
            # A computed answer is worked out below from the others. A value
            # submitted for one is discarded rather than refused: a client that
            # re-posts an application it fetched would otherwise be rejected for
            # sending back a figure the server itself produced — and accepting
            # it is how the paid total comes to disagree with the lines it is
            # supposed to be the sum of.
            if f.computed:
                continue
            try:
                value = f.clean(answers.get(f.key))
            except ValueError as exc:
                errors[f.key] = str(exc)
                continue
            if value is not None:
                cleaned[f.key] = value

        if errors:
            raise ValidationError(errors)

        if self.derive is not None:
            for key, value in self.derive(cleaned).items():
                if key not in self.computed_keys:
                    raise SchemaError(
                        f'{self.slug}: derived {key!r}, which is not a computed field'
                    )
                cleaned[key] = value
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
from . import travel              # noqa: E402,F401
from . import remaining           # noqa: E402,F401
