"""Tests for the application schemas."""

from decimal import Decimal

from django.test import SimpleTestCase

from funding.models import ApplicationType
from funding.schemas import (
    Choice, Field, FieldType, SchemaError, ValidationError, all_schemas, get_schema,
)


class SchemaIntegrityTests(SimpleTestCase):

    def test_every_schema_slug_is_an_application_type(self):
        """One name for a thing across the schema, the model and the API."""
        for schema in all_schemas():
            self.assertIn(schema.slug, ApplicationType.values, schema.slug)

    def test_field_keys_are_machine_names_not_prose(self):
        for schema in all_schemas():
            for field in schema.fields:
                self.assertEqual(field.key, field.key.lower())
                self.assertNotIn(' ', field.key)
                self.assertNotIn('-', field.key)

    def test_a_prose_key_is_rejected_at_definition_time(self):
        with self.assertRaises(SchemaError):
            Field('Course Load', 'Enrollment status')

    def test_duplicate_keys_are_rejected_at_definition_time(self):
        from funding.schemas import ApplicationSchema
        with self.assertRaises(SchemaError):
            ApplicationSchema(slug='x', fields=(Field('a', 'A'), Field('a', 'Again')))


class ValidationTests(SimpleTestCase):

    def setUp(self):
        self.schema = get_schema('admission')

    def _valid(self):
        return {
            'first_name': 'Jane', 'last_name': 'Doe',
            'date_of_birth': '2001-05-04', 'email': 'jane@example.com',
            'street_address': '1 Main St', 'city': 'Deline', 'province': 'NT',
            'institution_name': 'Aurora College', 'program': 'Nursing',
            'registrar_email': 'registrar@aurora.ca',
            'semester': 'Fall', 'semester_start': '2026-09-01',
            'semester_end': '2026-12-31', 'course_load': 'Full-time',
            'signature': 'Jane Doe',
            'doc_transcript': 'provided', 'doc_letter_of_intent': 'provided',
            'doc_status_card': 'provided', 'doc_void_cheque': 'provided',
        }

    def test_choices_normalise_to_stored_values(self):
        cleaned = self.schema.clean(self._valid())
        self.assertEqual(cleaned['course_load'], 'full_time')
        self.assertEqual(cleaned['semester'], 'fall')

    def test_money_accepts_what_applicants_type(self):
        data = self._valid() | {'tuition_requested': '$5,200.00'}
        self.assertEqual(self.schema.clean(data)['tuition_requested'], Decimal('5200.00'))

    def test_an_unrecognised_choice_is_refused_not_defaulted(self):
        data = self._valid() | {'course_load': 'sort of full time'}
        with self.assertRaises(ValidationError) as ctx:
            self.schema.clean(data)
        self.assertIn('course_load', ctx.exception.errors)

    def test_unknown_keys_are_refused(self):
        data = self._valid() | {'coarse_load': 'full_time'}
        with self.assertRaises(ValidationError) as ctx:
            self.schema.clean(data)
        self.assertIn('coarse_load', ctx.exception.errors)

    def test_every_missing_required_field_is_reported_at_once(self):
        with self.assertRaises(ValidationError) as ctx:
            self.schema.clean({})
        self.assertGreater(len(ctx.exception.errors), 5)

    def test_renaming_a_label_does_not_change_identity(self):
        field = self.schema.field('course_load')
        renamed = Field(field.key, 'Study load this term', field.type,
                        required=field.required, choices=field.choices)
        self.assertEqual(renamed.key, 'course_load')
        self.assertEqual(renamed.clean('Full-time'), field.clean('Full-time'))


class GraduationBursarySchemaTests(SimpleTestCase):

    def test_credential_is_a_closed_set(self):
        schema = get_schema('graduation_bursary')
        credential = schema.field('credential')
        self.assertIn('bachelors_degree', credential.choice_values)
        # 'BSc' used to fall through to the certificate rate.
        with self.assertRaises(ValueError):
            credential.clean('BSc')


class CoverageTests(SimpleTestCase):
    """Every application type must be answerable."""

    def test_every_application_type_has_a_schema(self):
        covered = {s.slug for s in all_schemas()}
        for value in ApplicationType.values:
            self.assertIn(value, covered, f'{value} has no schema')

    def test_no_schema_exists_without_an_application_type(self):
        declared = set(ApplicationType.values)
        for schema in all_schemas():
            self.assertIn(schema.slug, declared, schema.slug)

    def test_every_schema_asks_who_is_applying(self):
        # Enrollment verification is completed by a registrar about a student,
        # so it identifies the student rather than an applicant.
        for schema in all_schemas():
            keys = set(schema.keys)
            identifies = {'first_name', 'last_name'} <= keys or 'student_name' in keys
            self.assertTrue(identifies, f'{schema.slug} identifies nobody')

    def test_every_schema_is_signed(self):
        for schema in all_schemas():
            self.assertIn('signature', schema.keys, schema.slug)

    def test_every_schema_groups_its_fields_into_sections(self):
        for schema in all_schemas():
            self.assertTrue(schema.sections, schema.slug)
            for field in schema.fields:
                self.assertTrue(field.section, f'{schema.slug}.{field.key}')

    def test_shared_keys_mean_the_same_thing_everywhere(self):
        """One renderer and one set of generated types serve every schema."""
        seen: dict[str, tuple] = {}
        for schema in all_schemas():
            for field in schema.fields:
                signature = (field.type, field.choice_values)
                if field.key in seen:
                    self.assertEqual(
                        seen[field.key], signature,
                        f'{schema.slug}.{field.key} disagrees with another schema',
                    )
                else:
                    seen[field.key] = signature


class AwardInputTests(SimpleTestCase):
    """Fields the rules engine reads must exist, and be constrained."""

    def test_money_requests_are_typed_as_money(self):
        for slug in ('travel', 'emergency_relief', 'hardship_bursary', 'practicum'):
            field = get_schema(slug).field('amount_requested')
            self.assertEqual(field.type, FieldType.MONEY, slug)

    def test_scholarship_gpa_is_a_bounded_percentage(self):
        field = get_schema('academic_scholarship').field('gpa_achieved')
        self.assertEqual(field.type, FieldType.PERCENT)
        with self.assertRaises(ValueError):
            field.clean('160')

    def test_course_load_is_the_same_closed_set_wherever_it_appears(self):
        expected = ('full_time', 'part_time')
        for slug in ('admission', 'continuing_funding', 'enrollment_verification'):
            self.assertEqual(get_schema(slug).field('course_load').choice_values,
                             expected, slug)

    def test_enrollment_verification_captures_the_billed_tuition(self):
        """Tuition is funded against the registrar's figure, not the student's."""
        field = get_schema('enrollment_verification').field('confirmed_tuition')
        self.assertEqual(field.type, FieldType.MONEY)
        self.assertTrue(field.required)
