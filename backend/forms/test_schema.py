"""Tests for the typed form schema layer.

These pin the properties whose absence caused silent money bugs: a field's
identity is a stable key, not a display string; unknown keys are rejected rather
than stored and ignored; and values are normalised once, at the edge.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from forms.schema import (
    Choice, Field, FieldType, FormSchema, FundingType, ValidationError,
    get_schema, all_schemas,
)


class FieldCleaningTests(SimpleTestCase):

    def test_money_accepts_the_free_text_shapes_users_actually_type(self):
        f = Field('tuition', 'Tuition', FieldType.MONEY)
        for raw, expected in [
            ('5200', Decimal('5200')),
            ('$5,200.00', Decimal('5200.00')),
            ('  $ 5200.50 ', Decimal('5200.50')),
        ]:
            self.assertEqual(f.clean(raw), expected, raw)

    def test_money_rejects_nonsense_instead_of_defaulting_to_zero(self):
        f = Field('tuition', 'Tuition', FieldType.MONEY)
        with self.assertRaises(ValueError):
            f.clean('about five thousand')

    def test_money_rejects_negative_amounts(self):
        f = Field('tuition', 'Tuition', FieldType.MONEY)
        with self.assertRaises(ValueError):
            f.clean('-100')

    def test_choice_normalises_label_or_value_to_the_stored_value(self):
        f = Field('course_load', 'Enrollment Status', FieldType.CHOICE,
                  choices=(Choice('full_time', 'Full-time'),
                           Choice('part_time', 'Part-time')))
        self.assertEqual(f.clean('Full-time'), 'full_time')
        self.assertEqual(f.clean('full_time'), 'full_time')
        self.assertEqual(f.clean('FULL-TIME'), 'full_time')

    def test_choice_rejects_an_unrecognised_answer(self):
        """The old code silently fell through to the cheapest award tier here."""
        f = Field('course_load', 'Enrollment Status', FieldType.CHOICE,
                  choices=(Choice('full_time', 'Full-time'),))
        with self.assertRaises(ValueError):
            f.clean('sort of full time')

    def test_boolean_accepts_yes_no(self):
        f = Field('has_dependents', 'Has Dependents', FieldType.BOOLEAN)
        self.assertIs(f.clean('Yes'), True)
        self.assertIs(f.clean('no'), False)

    def test_blank_optional_field_is_omitted_not_zeroed(self):
        f = Field('tuition', 'Tuition', FieldType.MONEY)
        self.assertIsNone(f.clean(''))

    def test_required_field_rejects_blank(self):
        f = Field('first_name', 'First Name', FieldType.TEXT, required=True)
        with self.assertRaises(ValueError):
            f.clean('   ')

    def test_choice_field_must_declare_choices(self):
        with self.assertRaises(ValueError):
            Field('x', 'X', FieldType.CHOICE)


class SchemaTests(SimpleTestCase):

    def _schema(self):
        return FormSchema(
            slug='demo', title='Demo', funding_type=FundingType.PSSSP,
            fields=(
                Field('first_name', 'First Name', FieldType.TEXT, required=True),
                Field('tuition', 'Tuition', FieldType.MONEY),
            ),
        )

    def test_duplicate_field_keys_are_rejected_at_definition_time(self):
        with self.assertRaises(ValueError):
            FormSchema(slug='dupe', title='Dupe', funding_type=FundingType.DGGR,
                       fields=(Field('a', 'A'), Field('a', 'A again')))

    def test_unknown_keys_are_rejected_rather_than_silently_stored(self):
        with self.assertRaises(ValidationError) as ctx:
            self._schema().clean({'first_name': 'Jane', 'tuiton': '100'})
        self.assertIn('tuiton', ctx.exception.errors)

    def test_all_errors_are_reported_at_once(self):
        with self.assertRaises(ValidationError) as ctx:
            self._schema().clean({'tuition': 'not money'})
        self.assertIn('first_name', ctx.exception.errors)
        self.assertIn('tuition', ctx.exception.errors)

    def test_clean_returns_values_keyed_by_field_key(self):
        cleaned = self._schema().clean({'first_name': 'Jane', 'tuition': '$1,000'})
        self.assertEqual(cleaned, {'first_name': 'Jane', 'tuition': Decimal('1000')})


class FormAIdentityTests(SimpleTestCase):
    """The core property the old design lacked."""

    def test_renaming_a_label_does_not_change_field_identity(self):
        schema = get_schema('form-a')
        field = schema.field('course_load')
        renamed = Field(
            key=field.key, label='Study Load This Term', type=field.type,
            required=field.required, choices=field.choices,
        )
        # Same key, same cleaning behaviour — the label is presentation only.
        self.assertEqual(renamed.key, 'course_load')
        self.assertEqual(renamed.clean('Full-time'), field.clean('Full-time'))

    def test_funding_type_is_declared_not_matched_from_the_title(self):
        self.assertEqual(get_schema('form-a').funding_type, FundingType.PSSSP)

    def test_every_historical_label_maps_to_exactly_one_key(self):
        """Guards the EAV migration: no legacy label may be ambiguous."""
        for schema in all_schemas():
            seen: dict[str, str] = {}
            for f in schema.fields:
                # A field repeating its own label in legacy_labels is fine; two
                # different fields claiming one label is what breaks the migration.
                for label in {l.lower() for l in (f.label, *f.legacy_labels)}:
                    owner = seen.get(label)
                    self.assertIn(
                        owner, (None, f.key),
                        f"{schema.slug}: label {label!r} claimed by both "
                        f"{owner!r} and {f.key!r}",
                    )
                    seen[label] = f.key

    def test_the_enrollment_status_label_still_resolves_to_course_load(self):
        # Existing SubmissionAnswer rows are stored under this display string.
        mapping = get_schema('form-a').legacy_label_map()
        self.assertEqual(mapping['enrollment status'], 'course_load')
        self.assertEqual(mapping['course load'], 'course_load')
        self.assertEqual(mapping['courseload'], 'course_load')

    def test_required_funding_inputs_are_present(self):
        schema = get_schema('form-a')
        for key in ('course_load', 'institution_name', 'program', 'signature'):
            self.assertTrue(schema.field(key).required, f"{key} should be required")
