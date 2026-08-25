"""The approval letter across every shape of award, not one worked example.

A single worked example proves the layout, not the rules. These sweep the
combinations that actually differ: the three programme templates — including
UCEPP, which nothing assigns automatically and had therefore never been
rendered at all — both course loads, both dependant states, every semester, a
hand-set award, a category no template has a row for, and the awkward data an
office really holds.

Each case is checked against the same invariants rather than against a
transcript of what it happened to produce, because the point is that a letter
holds up whatever produced it.
"""

import itertools
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from reportlab.pdfbase.pdfmetrics import stringWidth

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, Award, FundingStream,
)
from funding.services import approval_letter as letters
from funding.services import letter_pdf
from funding.services.decisions import record_decision, record_manual_decision
from funding.test_fixtures import confirm_enrolment
from funding.test_rules import seed_rates

_ids = itertools.count(1)


def money(text: str) -> Decimal:
    return Decimal(text.replace('$', '').replace(',', ''))


def page_count(content: bytes) -> int:
    """How many pages the PDF really has.

    Through the parser: counting occurrences of `/Type /Page` in the bytes also
    matches `/Type /Pages`, the page-tree node, so every count came back one
    too high and the expected figures looked wrong when the document was right.
    """
    import io as _io

    from pypdf import PdfReader

    return len(PdfReader(_io.BytesIO(content)).pages)


class LetterScenarioTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = self.student(Role.ADMIN)
        # Measuring a string needs the font registered, and registration
        # normally happens on the first render. Without this the sweep passed
        # or errored depending on whether another test had rendered first.
        letter_pdf._register_fonts()

    def student(self, role=Role.STUDENT, **kw):
        n = next(_ids)
        return User.objects.create_user(
            f'scenario{n}@test.com', 'pw12345678', first_name='Sweep',
            last_name=f'Case{n}', role=role, is_deline_beneficiary=True,
            is_indian_act_registered=True, **kw)

    def approved(self, stream=FundingStream.PSSSP, course_load='full_time',
                 dependants=False, semester='fall', student=None,
                 tuition='9000'):
        student = student or self.student(beneficiary_number='B-9001',
                                          treaty_number='T-9001')
        application = Application.objects.create(
            student=student, type=ApplicationType.ADMISSION, stream=stream,
            schema_slug='admission', status=ApplicationStatus.SUBMITTED,
            semester=semester, academic_year='2026-2027',
            answers={
                'course_load': course_load, 'confirmed_tuition': tuition,
                'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
                'first_name': 'Sweep', 'last_name': 'Case',
                'has_dependents': 'yes' if dependants else 'no',
                'street_address': '12 Bear Rock Road', 'city': 'Délı̨nę',
                'province': 'NT', 'postal_code': 'X0E 0G0',
            })
        # Through the registrar, because the registrar's answers are what
        # govern the course load and the tuition — setting them on the
        # application alone changes nothing, and a sweep written that way
        # priced every case as full-time without noticing.
        confirm_enrolment(application, course_load=course_load,
                          confirmed_tuition=tuition)
        record_decision(application, actor=self.admin)
        Application.objects.filter(pk=application.pk).update(
            status=ApplicationStatus.APPROVED)
        application.refresh_from_db()
        return application

    def assert_sound(self, application):
        """Every invariant a letter has to satisfy, whatever produced it."""
        produced = letters.letters_for(application)
        self.assertTrue(produced)

        self.assertEqual(sum(money(one['total']) for one in produced),
                         application.awarded_total,
                         'the letters do not add up to the award')

        for letter in produced:
            code = letter['programme_code']
            with self.subTest(programme=code):
                self.assertEqual(sum(money(r['amount']) for r in letter['rows']),
                                 money(letter['total']), 'rows do not add up')
                self.assertTrue(letter['recipient'].strip())
                self.assertNotIn('$0.00', letter['footnote'])

                # Nothing drawn without wrapping may run past the margin.
                for line in [
                    f"{letter['identifier']['label']} {letter['identifier']['value']}",
                    *letter['address_lines'],
                    letter['signatory']['organisation'],
                    f"Email: {letter['signatory']['email']}",
                ]:
                    width = stringWidth(line, letter_pdf.BODY, letter_pdf.BODY_SIZE)
                    self.assertLessEqual(
                        width, letter_pdf.RIGHT - letter_pdf.LEFT,
                        f'runs off the page: {line}')

        content = letter_pdf.render(produced)
        self.assertTrue(content.startswith(b'%PDF-'))
        pages = page_count(content)
        self.assertTrue(1 <= pages <= 8, f'{pages} pages')
        return produced

    # ── The three templates ────────────────────────────────────────────────

    def test_every_stream_produces_a_sound_letter(self):
        for stream in (FundingStream.PSSSP, FundingStream.UCEPP, FundingStream.DGGR):
            with self.subTest(stream=stream):
                self.assert_sound(self.approved(stream=stream))

    def test_the_ucepp_template_renders(self):
        """Nothing assigns UCEPP, so this template had never been rendered at
        all — it existed and had never once been produced."""
        produced = self.assert_sound(self.approved(stream=FundingStream.UCEPP))
        ucepp = next(one for one in produced if one['programme_code'] == 'DGG-UCEPP')
        self.assertEqual(ucepp['total_label'], '')
        tuition_row = next(r for r in ucepp['rows'] if 'Program Costs' in r['label'])
        self.assertIn('upon university/college invoicing', tuition_row['note'])

    # ── Rates ──────────────────────────────────────────────────────────────

    def test_each_rate_combination_reaches_the_letter(self):
        """Four different monthly rates, and the letter has to name the one
        that was actually used."""
        from funding.models import PolicySetting

        cases = {
            ('full_time', False): 'fulltime_no_dependents',
            ('full_time', True): 'fulltime_with_dependents',
            ('part_time', False): 'parttime_no_dependents',
            ('part_time', True): 'parttime_with_dependents',
        }
        for (load, dependants), key in cases.items():
            with self.subTest(load=load, dependants=dependants):
                application = self.approved(course_load=load, dependants=dependants)
                produced = self.assert_sound(application)
                rate = PolicySetting.objects.get(section='psssp_living', key=key).value
                row = next(r for one in produced for r in one['rows']
                           if r['label'] == 'Monthly Allowance' and r['note'])
                self.assertIn(f'${rate:,.2f}/month', row['note'])

    # ── Terms ──────────────────────────────────────────────────────────────

    def test_every_semester_the_form_offers(self):
        for semester, expected in (('fall', 'Fall'), ('winter', 'Winter'),
                                   ('spring', 'Spring'), ('summer', 'Summer')):
            with self.subTest(semester=semester):
                produced = self.assert_sound(self.approved(semester=semester))
                self.assertEqual(produced[0]['semester'], expected)
                self.assertTrue(produced[0]['term'].startswith(expected))

    def test_an_application_with_no_semester_still_produces_a_letter(self):
        produced = self.assert_sound(self.approved(semester=''))
        self.assertEqual(produced[0]['semester'], '')
        self.assertEqual(produced[0]['term'], '2026-2027')

    # ── Awkward data ───────────────────────────────────────────────────────

    def test_an_account_with_no_identifiers_leaves_the_line_blank(self):
        bare = self.student()
        produced = self.assert_sound(self.approved(student=bare))
        self.assertEqual(produced[0]['identifier']['value'], '')
        self.assertTrue(produced[0]['identifier']['label'])

    def test_a_very_long_name_does_not_run_off_the_page(self):
        person = self.student(beneficiary_number='B-1', treaty_number='T-1')
        application = self.approved(student=person)
        application.answers = {
            **application.answers,
            'first_name': 'Christopher Alexander',
            'last_name': 'Montgomery-Fitzgerald-Wentworth',
        }
        application.save(update_fields=['answers'])
        self.assert_sound(application)

    # ── Awards that are not the ordinary case ──────────────────────────────

    def test_a_hand_set_award_produces_a_letter_that_adds_up(self):
        """`manual_N` belongs to no rule, so nothing can attribute it to a
        programme. It lands on the one the application was filed under."""
        application = self.approved()
        record_manual_decision(application, [
            {'category': 'tuition', 'amount': Decimal('4321.00'),
             'description': 'Agreed at the counter'},
            {'category': 'living', 'amount': Decimal('1000.00'),
             'description': 'Allowance'},
        ], actor=self.admin, note='A fee no rate covers')
        application.refresh_from_db()

        produced = self.assert_sound(application)
        self.assertEqual([one['programme_code'] for one in produced], ['DGG-CDFN'])
        # No rate behind it, so no monthly note is invented.
        allowance = next(r for r in produced[0]['rows']
                         if r['label'] == 'Monthly Allowance')
        self.assertEqual(allowance['note'], '')

    def test_a_category_the_template_has_no_row_for_is_still_accounted_for(self):
        """Dropping it would produce a letter adding up to less than the
        award, which is the office understating what it granted."""
        application = self.approved()
        decision = application.decisions.filter(is_current=True).first()
        Award.objects.create(
            application=application, decision=decision,
            rule_code='travel_assistance', category=Award.Category.TRAVEL,
            amount=Decimal('500.00'))
        application.awarded_total += Decimal('500.00')
        application.save(update_fields=['awarded_total'])

        produced = self.assert_sound(application)
        labels = [r['label'] for one in produced for r in one['rows']]
        self.assertIn('Travel', labels)

    # ── Statuses ───────────────────────────────────────────────────────────

    def test_no_undecided_or_declined_application_gets_a_letter(self):
        for status in (ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW,
                       ApplicationStatus.AWAITING_DECISION,
                       ApplicationStatus.DECLINED):
            with self.subTest(status=status):
                application = self.approved()
                Application.objects.filter(pk=application.pk).update(status=status)
                application.refresh_from_db()
                with self.assertRaises(letters.LetterUnavailable):
                    letters.letters_for(application)

    def test_an_application_already_sent_to_finance_keeps_its_letter(self):
        application = self.approved()
        Application.objects.filter(pk=application.pk).update(
            status=ApplicationStatus.SENT_TO_FINANCE)
        application.refresh_from_db()
        self.assert_sound(application)

    def test_one_off_awards_produce_no_letter(self):
        for kind, slug, answers in (
                (ApplicationType.GRADUATION_BURSARY, 'graduation_bursary',
                 {'credential': 'bachelors_degree'}),
                (ApplicationType.HARDSHIP_BURSARY, 'hardship_bursary',
                 {'amount_requested': '400'}),
        ):
            with self.subTest(kind=kind):
                application = Application.objects.create(
                    student=self.student(beneficiary_number='B-2'), type=kind,
                    stream=FundingStream.DGGR, schema_slug=slug,
                    status=ApplicationStatus.SUBMITTED, semester='fall',
                    academic_year='2026-2027', answers=answers)
                record_decision(application, actor=self.admin)
                Application.objects.filter(pk=application.pk).update(
                    status=ApplicationStatus.APPROVED)
                application.refresh_from_db()
                with self.assertRaises(letters.LetterUnavailable):
                    letters.letters_for(application)

    # ── The page the office actually posts ─────────────────────────────────

    def test_each_template_runs_to_the_length_the_office_s_own_does(self):
        """CDFN and UCEPP are one page on the supplied templates and DGGR is
        two. A letter that spills onto a second sheet carrying nothing but a
        signature is the mark of a generated document, and it happened twice:
        once on the sign-off, and again when a student with a real postal
        address added two lines to the block.
        """
        expected = {'DGG-CDFN': 1, 'DGG-UCEPP': 1, 'DGGR-SFSP': 2}
        produced = letters.letters_for(self.approved(stream=FundingStream.UCEPP))
        seen = {one['programme_code']: page_count(letter_pdf.render([one]))
                for one in produced}
        for code, pages in expected.items():
            if code in seen:
                with self.subTest(programme=code):
                    self.assertEqual(seen[code], pages,
                                     f'{code} is {seen[code]} page(s), expected {pages}')
