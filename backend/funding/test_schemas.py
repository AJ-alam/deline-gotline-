"""Tests for the application schemas."""

from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from funding.api.serializers import schema_payload
from funding.models import ApplicationType
from funding.test_fixtures import admission_answers, answers_for
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
        # Built from the schema, so a newly required field does not turn every
        # validation test into a failure about a field it is not testing.
        return admission_answers()

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
        # Three spellings, because three things are being asked. Most forms
        # collect a name in parts; the enrollment verification is a registrar
        # writing about a student; the continuing-funding renewal shows the name
        # already on file as one string for confirmation.
        for schema in all_schemas():
            keys = set(schema.keys)
            identifies = (
                {'first_name', 'last_name'} <= keys
                or 'student_name' in keys
                or 'full_name' in keys
            )
            self.assertTrue(identifies, f'{schema.slug} identifies nobody')

    def test_every_name_spelling_resolves_to_a_readable_name(self):
        """Whatever a schema calls it, services.verification.student_name finds it.

        The guard above only proves a schema asks for a name. This proves the
        code that puts one in a registrar's email can actually read it — the two
        drifted apart the moment a schema stopped using first_name/last_name.
        """
        from funding.services.verification import student_name

        for schema in all_schemas():
            keys = set(schema.keys)
            if 'student_name' in keys:
                answers = {'student_name': 'Reg Istrar'}
            elif 'full_name' in keys:
                answers = {'full_name': 'Majid Khan'}
            else:
                answers = {'first_name': 'Majid', 'last_name': 'Khan'}
            application = SimpleNamespace(answers=answers, student=None)
            self.assertTrue(
                student_name(application),
                f'{schema.slug}: student_name() reads nothing from its answers',
            )

    def test_every_schema_is_signed(self):
        """Someone puts their name to every form.

        Not always under the key `signature`: on the summer student / practicum
        award the person signing is the supervisor, not the applicant, and
        calling that `signature` would make one key mean "the applicant signed"
        in nine schemas and "somebody else did" in the tenth.
        """
        for schema in all_schemas():
            signed = [f.key for f in schema.fields if f.type is FieldType.SIGNATURE]
            self.assertTrue(signed, f'{schema.slug} is signed by nobody')

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
        for slug in ('travel', 'emergency_relief', 'hardship_bursary'):
            field = get_schema(slug).field('amount_requested')
            self.assertEqual(field.type, FieldType.MONEY, slug)

    def test_the_practicum_award_asks_for_no_amount(self):
        """It is a flat published rate, so there is no figure to request —
        and `practicum_allowance` is a `flat_rate` rule to match."""
        with self.assertRaises(KeyError):
            get_schema('practicum').field('amount_requested')

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


class PracticumReportTests(SimpleTestCase):
    """The employer's half of the summer student / practicum award.

    The award is released against what the supervisor reports, not against what
    the applicant asserts — so every part of that report is required, and the
    form cannot be filed with the employer's declaration refused.
    """

    schema = staticmethod(lambda: get_schema('practicum'))

    def test_it_asks_the_office_s_questions_and_no_others(self):
        """The content the office supplied, plus the two answers a claim cannot
        be paid without: where the decision goes, and where the money goes."""
        self.assertEqual(
            set(self.schema().keys),
            {
                'employer_name', 'supervisor_title',
                'full_name', 'email', 'placement_start', 'placement_end',
                'roles_and_responsibilities', 'performance_summary',
                'employer_declaration', 'supervisor_signature',
                'report_completed_on',
                'account_holder', 'transit_number', 'institution_number',
                'account_number',
            },
        )

    def test_the_report_says_who_is_answering_for_the_placement(self):
        for key in ('employer_name', 'supervisor_title'):
            with self.subTest(key=key):
                field = self.schema().field(key)
                self.assertEqual(field.type, FieldType.TEXT)
                self.assertTrue(field.required, f'{key} is not required')

    def test_roles_and_performance_are_required_prose(self):
        for key in ('roles_and_responsibilities', 'performance_summary'):
            with self.subTest(key=key):
                field = self.schema().field(key)
                self.assertEqual(field.type, FieldType.LONG_TEXT)
                self.assertTrue(field.required, f'{key} is not required')

    def test_the_employer_declaration_cannot_be_answered_no(self):
        """A CONFIRM, never a BOOLEAN: a required BOOLEAN accepts False, which
        would file the claim with the employer's attestation refused."""
        field = self.schema().field('employer_declaration')
        self.assertEqual(field.type, FieldType.CONFIRM)
        with self.assertRaises(ValueError):
            field.clean('false')
        self.assertIs(field.clean('true'), True)

    def test_the_supervisor_signs_and_the_report_is_dated(self):
        field = self.schema().field('supervisor_signature')
        self.assertEqual(field.type, FieldType.SIGNATURE)
        self.assertTrue(field.required)
        completed = self.schema().field('report_completed_on')
        self.assertEqual(completed.type, FieldType.DATE)
        self.assertTrue(completed.required)

    def test_the_date_opens_on_today(self):
        """It is the day the supervisor is signing, not a fact to look up.

        Filled by the client rather than by `services/prefill`, because this
        award is claimable with no account and a server-side prefill returns
        nothing for a guest — which is most of the people who file it.
        """
        self.assertTrue(self.schema().field('report_completed_on').defaults_to_today)

    def test_the_declaration_is_worded_as_the_office_words_it(self):
        """The sentence the employer is held to, quoted rather than tidied."""
        self.assertEqual(
            self.schema().field('employer_declaration').help_text,
            'The employer confirms that the information provided is accurate '
            'and complete. Award is contingent on regular attendance and '
            'satisfactory performance.',
        )

    def test_the_form_falls_into_the_three_steps_the_office_asked_for(self):
        """Section names are what the client groups steps by.

        A section renamed here and not in Apply.tsx renders as a step that lost
        its questions, so the names are asserted rather than left to agree by
        habit.
        """
        self.assertEqual(
            self.schema().sections,
            ('Employer information', 'Student information',
             'Performance and roles', 'Payment', 'Declaration'),
        )

    def test_a_claim_without_the_employer_report_is_refused(self):
        """Every missing answer at once, so a supervisor is not told about them
        one at a time."""
        report_keys = {
            'employer_name', 'supervisor_title',
            'roles_and_responsibilities', 'performance_summary',
            'employer_declaration', 'supervisor_signature',
            'report_completed_on',
        }
        student_half = {key: value for key, value in answers_for('practicum').items()
                        if key not in report_keys}
        with self.assertRaises(ValidationError) as caught:
            self.schema().clean(student_half)
        self.assertEqual(sorted(caught.exception.errors), sorted(report_keys))

    def test_a_complete_claim_is_accepted(self):
        cleaned = self.schema().clean(answers_for('practicum'))
        self.assertIs(cleaned['employer_declaration'], True)
        self.assertEqual(cleaned['supervisor_title'], 'Test value')


class ApplyInPortalTests(TestCase):
    """Which forms a student may start themselves.

    The enrolment verification is the institution's declaration about a
    student, reached from a single-use emailed link. Offering it in the
    portal's "apply for funding" list invites a student to file it about
    themselves. Their answers cannot reach their own award — only the token
    route copies CONFIRMABLE_KEYS onto an application — but the record is
    nonsense and arrives in the staff queue as work.
    """

    def test_the_registrars_form_is_not_offered_in_the_portal(self):
        self.assertFalse(get_schema('enrollment_verification').apply_in_portal)

    def test_everything_a_student_applies_for_is_offered(self):
        for slug in ('admission', 'continuing_funding', 'appeal', 'travel',
                     'practicum', 'graduation_bursary', 'emergency_relief',
                     'hardship_bursary', 'academic_scholarship'):
            with self.subTest(slug=slug):
                self.assertTrue(get_schema(slug).apply_in_portal)

    def test_every_schema_says_what_it_is_for(self):
        """Nine similar official names in a list is not a choice most people
        can make."""
        for schema in all_schemas():
            with self.subTest(slug=schema.slug):
                self.assertTrue(schema.summary.strip(), schema.slug)

    def test_the_api_carries_both_so_the_client_holds_no_list_of_exceptions(self):
        payload = schema_payload()
        by_slug = {entry['slug']: entry for entry in payload}

        self.assertFalse(by_slug['enrollment_verification']['apply_in_portal'])
        self.assertTrue(by_slug['admission']['apply_in_portal'])
        self.assertIn('Start here', by_slug['admission']['summary'])


class ContactRulesTests(SimpleTestCase):
    """How the portal may insist on being able to reach somebody.

    The office's rule: an email address is required, a phone number is not.
    Email is how every notice this portal sends arrives, so it is the one
    contact detail an application cannot do without; a phone number is a second
    way of being reached, and requiring it turns a preference into a refusal.

    Asserted across every schema rather than against the two forms that were
    wrong. A test naming those two passes the day a third is written — which is
    exactly how `doc_supporting` came to be a single file on three forms and
    plural on the rest.
    """

    # The one form that may insist, and why. Emergency relief is same-day
    # hardship: the office may need to reach somebody today, and an email
    # address is not a way to do that. Recorded here so that requiring a phone
    # number anywhere else is a test failure rather than a habit.
    MAY_REQUIRE_PHONE = {'emergency_relief'}

    def applicant_fields(self, schema, field_type):
        """The applicant's own contact details.

        Not the institution's or the registrar's: `registrar_email` is where the
        enrolment request is sent, so it is required for a reason that has
        nothing to do with reaching the applicant.
        """
        return [
            field for field in schema.fields
            if field.type is field_type
            and not field.key.startswith(('institution_', 'registrar_', 'employer_',
                                          'supervisor_'))
        ]

    def test_no_form_requires_a_phone_number_but_emergency_relief(self):
        offenders = {
            schema.slug: [f.key for f in self.applicant_fields(schema, FieldType.PHONE)
                          if f.required]
            for schema in all_schemas()
            if schema.slug not in self.MAY_REQUIRE_PHONE
        }
        offenders = {slug: keys for slug, keys in offenders.items() if keys}
        self.assertEqual(offenders, {}, f'these forms still require a phone: {offenders}')

    def test_emergency_relief_still_requires_one(self):
        """The exception is an exception, not an oversight that drifted back.

        A rule with an exception nothing asserts is a rule that quietly loses
        its exception the next time somebody applies it flat.
        """
        self.assertTrue(get_schema('emergency_relief').field('phone').required)

    def test_every_form_that_asks_for_an_email_requires_it(self):
        weak = {
            schema.slug: [f.key for f in self.applicant_fields(schema, FieldType.EMAIL)
                          if not f.required]
            for schema in all_schemas()
            # The registrar fills this one in from an emailed link; the student's
            # details on it are carried over for checking, not collected.
            if schema.slug != 'enrollment_verification'
        }
        weak = {slug: keys for slug, keys in weak.items() if keys}
        self.assertEqual(weak, {}, f'these forms ask for an email without requiring it: {weak}')

    def test_the_two_forms_that_were_wrong(self):
        """Named as well as swept, so a failure says which screen changed."""
        for slug in ('admission', 'graduation_bursary'):
            with self.subTest(slug=slug):
                schema = get_schema(slug)
                self.assertFalse(schema.field('phone').required)
                self.assertTrue(schema.field('email').required)


class BankingIsAskedWhereverMoneyIsPaidTests(SimpleTestCase):
    """Every form that can produce an award asks where to pay it.

    The rule was previously written as "required on every form that collects
    it", and enforced by reading the five forms that collected it. Three that
    pay money collected none at all and so were never in scope:
    `continuing_funding` (tuition and a living allowance, every semester),
    `academic_scholarship` and `hardship_bursary`.

    What that cost is at the far end of the money path. Nothing but a filled-in
    banking section creates a `BankAccount`, so a student whose *first*
    application was one of those three had no account; the award was priced,
    approved, and then held out of the payment file reading "has no bank account
    on file" — on a screen the applicant never sees, weeks after they could have
    answered in a second. That is the wall of red the payment run exists to not
    be.

    Derived from the seeded rules rather than from a list kept by hand. The rule
    set is the authority on which application types produce money, so a rule
    added for a new type tomorrow fails this test until that form asks — which
    is precisely what a hand-kept list of five did not do.
    """

    BANKING = ('account_holder', 'transit_number', 'institution_number',
               'account_number')

    def paying_types(self):
        from funding.management.commands.seed_rules import RULES

        types = set()
        for rule in RULES:
            types.update(rule.get('applies_to_types') or ())
        return types

    def test_the_rule_set_pays_out_on_more_than_five_forms(self):
        """Guards the guard.

        If `RULES` were ever read wrongly and came back empty, every assertion
        below would pass by iterating nothing — the residency-count fault, in a
        test file.
        """
        self.assertGreaterEqual(len(self.paying_types()), 8, self.paying_types())

    def test_every_paying_form_asks_where_to_pay_it(self):
        missing = {}
        for slug in sorted(self.paying_types()):
            keys = set(get_schema(slug).keys)
            absent = [key for key in self.BANKING if key not in keys]
            if absent:
                missing[slug] = absent
        self.assertEqual(
            missing, {},
            'these forms produce an award and ask for nowhere to send it, so '
            f'every award on them is held in the payment run: {missing}')

    def test_and_requires_it(self):
        """Optional is the same failure one step later — a student who skips it
        is a student whose award is held."""
        weak = {}
        for slug in sorted(self.paying_types()):
            schema = get_schema(slug)
            keys = set(schema.keys)
            optional = [key for key in self.BANKING
                        if key in keys and not schema.field(key).required]
            if optional:
                weak[slug] = optional
        self.assertEqual(weak, {}, f'banking is optional on: {weak}')

    def test_and_keeps_it_out_of_answers(self):
        """`answers` is returned whole by the detail endpoint, printed on the
        paper form and copied into the registrar's copy. A form that asked for
        banking without marking it private would put an account number in all
        three."""
        leaking = {}
        for slug in sorted(self.paying_types()):
            schema = get_schema(slug)
            keys = set(schema.keys)
            public = [key for key in self.BANKING
                      if key in keys and not schema.field(key).private]
            if public:
                leaking[slug] = public
        self.assertEqual(leaking, {}, f'banking would land in answers on: {leaking}')

    def test_the_three_that_were_missed(self):
        """Named as well as swept, so a failure says which screen changed."""
        for slug in ('continuing_funding', 'academic_scholarship', 'hardship_bursary'):
            with self.subTest(slug=slug):
                schema = get_schema(slug)
                for key in self.BANKING:
                    field = schema.field(key)
                    self.assertTrue(field.required, f'{slug}.{key}')
                    self.assertTrue(field.private, f'{slug}.{key}')

    def test_appeal_is_not_expected_to_ask(self):
        """The exception, pinned. An appeal asks for a decision to be revisited
        and prices nothing, so it has no rule and no payment section — and a
        test that swept every *form* rather than every paying form would have
        demanded banking on it."""
        self.assertNotIn('appeal', self.paying_types())
        self.assertNotIn('account_number', set(get_schema('appeal').keys))
