"""The annual report the department sends its head office.

The figures on it go to a funder, so what matters is not that a number appears
but that it is the right number and that the reader can tell what it is: gross
against net, computed against hand-entered, classified against not.
"""

import itertools
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, Award, AwardRepayment,
    EnrollmentVerification, FundingStream, ReportedCost,
)
from funding.services import reporting
from funding.services.decisions import record_decision
from funding.test_fixtures import confirm_enrolment
from funding.test_rules import seed_rates

_ids = itertools.count(1)
YEAR = date(2026, 4, 1)


class ReportTestCase(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = self.person(Role.ADMIN)

    def person(self, role=Role.STUDENT, **kw):
        n = next(_ids)
        return User.objects.create_user(
            f'report{n}@test.com', 'pw12345678', first_name='Rep',
            last_name=f'Person{n}', role=role, is_deline_beneficiary=True,
            is_indian_act_registered=True, **kw)

    def approved(self, *, semester='fall', institution_type=None,
                 program_type=None, institution='Northern Lights College',
                 program='Practical Nursing', student=None, submitted=None,
                 tuition='9000', stream=FundingStream.PSSSP):
        """An approved, priced semester application, classified or not."""
        student = student or self.person()
        when = submitted or timezone.make_aware(
            timezone.datetime(YEAR.year, 9, 1))
        application = Application.objects.create(
            student=student, type=ApplicationType.ADMISSION,
            stream=stream, schema_slug='admission',
            status=ApplicationStatus.SUBMITTED, semester=semester,
            academic_year='2026-2027', submitted_at=when,
            answers={'course_load': 'full_time', 'confirmed_tuition': tuition,
                     'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
                     'institution_name': institution, 'program': program})
        extra = {}
        if institution_type:
            extra['institution_type'] = institution_type
        if program_type:
            extra['program_type'] = program_type
        confirm_enrolment(application, confirmed_tuition=tuition,
                          institution_name=institution, program=program, **extra)
        record_decision(application, actor=self.admin)
        Application.objects.filter(pk=application.pk).update(
            status=ApplicationStatus.APPROVED)
        application.refresh_from_db()
        return application

    def extracted(self, content: bytes) -> str:
        import io as _io

        from pypdf import PdfReader

        return '\n'.join(page.extract_text() or ''
                         for page in PdfReader(_io.BytesIO(content)).pages)

    def report(self):
        return reporting.annual_report(YEAR)


class FiscalYearTests(TestCase):

    def test_the_year_runs_april_to_march(self):
        """As the report's own title says."""
        self.assertEqual(reporting.fiscal_year_of(date(2026, 4, 1)), date(2026, 4, 1))
        self.assertEqual(reporting.fiscal_year_of(date(2026, 12, 31)), date(2026, 4, 1))
        self.assertEqual(reporting.fiscal_year_of(date(2027, 3, 31)), date(2026, 4, 1))
        self.assertEqual(reporting.fiscal_year_of(date(2027, 4, 1)), date(2027, 4, 1))


class EnrolmentTableTests(ReportTestCase):

    def test_students_are_counted_by_semester_and_institution_type(self):
        self.approved(semester='fall', institution_type='university')
        self.approved(semester='fall', institution_type='college')
        self.approved(semester='winter', institution_type='college')

        rows = {r['season']: r for r in self.report()['enrolment']['rows']}
        self.assertEqual(rows['Fall']['university'], 1)
        self.assertEqual(rows['Fall']['college'], 1)
        self.assertEqual(rows['Fall']['total'], 2)
        self.assertEqual(rows['Winter']['college'], 1)

    def test_trades_and_upgrading_are_subsets_not_extra_columns(self):
        """The office's own note on the table. A total that added them would
        report more students than attended."""
        self.approved(institution_type='college', program_type='trades')
        self.approved(institution_type='college', program_type='upgrading')

        total = self.report()['enrolment']['total']
        self.assertEqual(total['college'], 2)
        self.assertEqual(total['total'], 2, 'trades and upgrading were added twice')
        self.assertEqual(total['trades'], 1)
        self.assertEqual(total['upgrading'], 1)

    def test_an_unclassified_enrolment_is_counted_and_named(self):
        """Every enrolment confirmed before the question existed has no answer.
        Dropping them would report a year with fewer students than it had;
        guessing from the institution's name would be a display string deciding
        a figure the office sends its funder."""
        self.approved(institution_type=None)
        table = self.report()['enrolment']
        self.assertEqual(table['total']['unclassified'], 1)
        self.assertEqual(table['total']['total'], 1)
        self.assertEqual(table['unclassified'], 1)

    def test_the_total_counts_enrolments_and_adds_the_seasons_up(self):
        """The office's own table adds its seasons — 20 + 5 + 40 + 30 = 95 —
        and its summary calls that "95 semester enrolments". A total that
        counted distinct people instead came out smaller than the column above
        it, which on a report to a funder reads as an arithmetic mistake."""
        person = self.person()
        self.approved(semester='fall', institution_type='college', student=person)
        self.approved(semester='winter', institution_type='college', student=person)

        table = self.report()['enrolment']
        rows = {r['season']: r for r in table['rows']}
        self.assertEqual(rows['Fall']['college'], 1)
        self.assertEqual(rows['Winter']['college'], 1)
        self.assertEqual(table['total']['college'], 2, 'the seasons do not add up')
        self.assertEqual(table['total']['total'],
                         sum(r['total'] for r in table['rows']))

    def test_the_headcount_behind_those_enrolments_is_reported_separately(self):
        """Both figures are wanted; only one of them belongs in the table."""
        person = self.person()
        self.approved(semester='fall', institution_type='college', student=person)
        self.approved(semester='winter', institution_type='college', student=person)
        table = self.report()['enrolment']
        self.assertEqual(table['distinct_students'], 1)
        self.assertEqual(table['total']['total'], 2)

    def test_every_column_of_the_total_is_the_sum_of_its_column(self):
        self.approved(semester='fall', institution_type='university')
        self.approved(semester='winter', institution_type='college',
                      program_type='trades')
        table = self.report()['enrolment']
        for column in ('university', 'college', 'trades_school', 'unclassified',
                       'trades', 'upgrading', 'total'):
            with self.subTest(column=column):
                self.assertEqual(table['total'][column],
                                 sum(r[column] for r in table['rows']))

    def test_one_off_awards_are_not_enrolments(self):
        """A graduation bursary is not a semester of study."""
        student = self.person()
        application = Application.objects.create(
            student=student, type=ApplicationType.GRADUATION_BURSARY,
            stream=FundingStream.DGGR, schema_slug='graduation_bursary',
            status=ApplicationStatus.SUBMITTED, semester='fall',
            submitted_at=timezone.make_aware(timezone.datetime(YEAR.year, 9, 1)),
            answers={'credential': 'bachelors_degree'})
        record_decision(application, actor=self.admin)
        Application.objects.filter(pk=application.pk).update(
            status=ApplicationStatus.APPROVED)
        self.assertEqual(self.report()['enrolment']['total']['total'], 0)


class GraduateAwardTests(ReportTestCase):

    def grad(self, credential='bachelors_degree', city='Délı̨nę'):
        application = Application.objects.create(
            student=self.person(), type=ApplicationType.GRADUATION_BURSARY,
            stream=FundingStream.DGGR, schema_slug='graduation_bursary',
            status=ApplicationStatus.SUBMITTED, semester='fall',
            submitted_at=timezone.make_aware(timezone.datetime(YEAR.year, 9, 1)),
            answers={'credential': credential, 'city': city})
        record_decision(application, actor=self.admin)
        Application.objects.filter(pk=application.pk).update(
            status=ApplicationStatus.APPROVED)
        return application

    def test_awards_are_grouped_by_credential(self):
        self.grad('bachelors_degree')
        self.grad('diploma')
        self.grad('high_school_diploma')
        self.grad('red_seal')

        total = self.report()['graduate_awards']['total']
        self.assertEqual(total['university'], 1)
        self.assertEqual(total['college'], 1)
        self.assertEqual(total['high_school'], 1)
        self.assertEqual(total['trades'], 1)
        self.assertEqual(total['total'], 4)

    def test_residency_splits_deline_from_elsewhere(self):
        self.grad(city='Délı̨nę')
        self.grad(city='Edmonton')
        rows = {r['residency']: r for r in self.report()['graduate_awards']['rows']}
        self.assertEqual(rows['Délı̨nę residents']['total'], 1)
        self.assertEqual(rows['Beneficiaries outside Délı̨nę']['total'], 1)


class InstitutionTableTests(ReportTestCase):

    def test_institutions_are_grouped_with_their_programmes(self):
        self.approved(institution='Northern Lights College', program='Practical Nursing',
                      institution_type='college')
        self.approved(institution='Northern Lights College', program='Business Admin',
                      institution_type='college')
        self.approved(institution='Mackenzie University', program='BSc Nursing',
                      institution_type='university')

        sections = {s['label']: s for s in self.report()['institutions']['sections']}
        college = sections['College or polytechnic']['rows'][0]
        self.assertEqual(college['name'], 'Northern Lights College')
        self.assertEqual(college['students'], 2)
        self.assertEqual(sorted(college['programs']),
                         ['Business Admin', 'Practical Nursing'])
        self.assertEqual(sections['University']['students'], 1)


class FinancialTableTests(ReportTestCase):

    def test_money_is_split_by_the_categories_the_office_asked_for(self):
        self.approved(institution_type='college')
        financial = self.report()['financial']
        keys = [c['key'] for c in financial['categories']]
        for expected in ('tuition', 'living', 'graduate_awards',
                         'summer_awards', 'achievement_awards'):
            self.assertIn(expected, keys)
        self.assertGreater(Decimal(financial['total']['net']), 0)

    def test_a_repayment_reduces_the_net_and_leaves_the_gross_alone(self):
        """The office reconciles against a financial statement: it needs what
        went out, what came back, and the difference."""
        application = self.approved(institution_type='college')
        line = Award.objects.current().filter(application=application).first()
        AwardRepayment.objects.create(
            award=line, amount=Decimal('250.00'), reason='Withdrew in October',
            repaid_on=date(YEAR.year, 11, 2), recorded_by=self.admin)

        total = self.report()['financial']['total']
        self.assertEqual(Decimal(total['repaid']), Decimal('250.00'))
        self.assertEqual(Decimal(total['net']),
                         Decimal(total['gross']) - Decimal('250.00'))

    def test_a_repayment_never_edits_the_award_it_came_from(self):
        """`Award.amount` is what was decided and what an approval letter
        already told the student they were granted."""
        application = self.approved(institution_type='college')
        line = Award.objects.current().filter(application=application).first()
        before = line.amount
        AwardRepayment.objects.create(
            award=line, amount=Decimal('100.00'), reason='Returned',
            repaid_on=date(YEAR.year, 11, 2))
        line.refresh_from_db()
        self.assertEqual(line.amount, before)

    def test_a_hand_entered_cost_is_kept_apart_from_what_was_computed(self):
        """Folded silently into a total, it is a total nobody can check."""
        self.approved(institution_type='college')
        ReportedCost.objects.create(
            fiscal_year_start=YEAR, label='Administration — Staff Wages/Benefits',
            amount=Decimal('25000.00'), recorded_by=self.admin)

        financial = self.report()['financial']
        self.assertEqual(Decimal(financial['entered_total']), Decimal('25000.00'))
        self.assertEqual(
            Decimal(financial['grand_total']),
            Decimal(financial['total']['net']) + Decimal('25000.00'))
        self.assertEqual(financial['entered'][0]['recorded_by'],
                         self.admin.full_name)

    def test_last_years_entered_cost_does_not_reach_this_years_report(self):
        self.approved(institution_type='college')
        ReportedCost.objects.create(
            fiscal_year_start=date(YEAR.year - 1, 4, 1), label='Staff wages',
            amount=Decimal('9999.00'))
        self.assertEqual(Decimal(self.report()['financial']['entered_total']),
                         Decimal('0.00'))

    def test_an_application_from_another_year_is_not_counted(self):
        self.approved(institution_type='college',
                      submitted=timezone.make_aware(timezone.datetime(2025, 9, 1)))
        self.assertEqual(self.report()['enrolment']['total']['total'], 0)
        self.assertEqual(Decimal(self.report()['financial']['total']['gross']),
                         Decimal('0.00'))


class ProgrammeBreakdownTests(ReportTestCase):
    """The funding programme breakdown.

    The office asked which programme paid for what. That question has two
    honest answers depending on whether you are counting people or money, and
    the table gives both rather than picking one and hoping nobody checks.
    """

    def rows(self):
        return {r['stream']: r for r in self.report()['programmes']['rows']}

    def test_an_application_is_counted_against_its_primary_programme(self):
        self.approved(stream=FundingStream.PSSSP)
        self.approved(stream=FundingStream.DGGR)
        self.approved(stream=FundingStream.DGGR)
        rows = self.rows()
        self.assertEqual(rows[FundingStream.PSSSP]['applications'], 1)
        self.assertEqual(rows[FundingStream.DGGR]['applications'], 2)
        self.assertEqual(rows[FundingStream.UCEPP]['applications'], 0)

    def test_two_applications_from_one_student_are_one_student(self):
        student = self.person()
        self.approved(student=student, semester='fall')
        self.approved(student=student, semester='winter')
        rows = self.rows()
        self.assertEqual(rows[FundingStream.PSSSP]['applications'], 2)
        self.assertEqual(rows[FundingStream.PSSSP]['students'], 1)

    def test_money_follows_the_rule_that_paid_it_not_the_application(self):
        """The point of the whole table.

        A PSSSP application whose pricing includes a DGGR top-up has spent
        from two programmes. Reporting all of it under PSSSP would tell the
        funder DGGR paid for nothing.
        """
        application = self.approved(stream=FundingStream.PSSSP)
        codes = set(
            Award.objects.awarded().filter(application=application)
            .values_list('rule_code', flat=True))
        self.assertTrue(
            any(code.startswith('dggr_') for code in codes),
            'expected this fixture to draw on DGGR; it priced %s'
            % sorted(codes))

        rows = self.rows()
        self.assertGreater(Decimal(rows[FundingStream.DGGR]['gross']), 0)
        self.assertEqual(rows[FundingStream.DGGR]['applications'], 0,
                         'no application is filed under DGGR here')

    def test_money_from_a_rule_naming_no_programme_is_not_guessed_at(self):
        """Bursaries, travel and scholarships apply to everybody.

        Pushing them into the applicant's primary programme would report money
        against a programme that did not pay it.
        """
        application = self.approved()
        award = Award.objects.awarded().filter(application=application).first()
        Award.objects.create(
            application=application, decision=award.decision,
            category=award.category, rule_code='graduation_bursary',
            amount=Decimal('1500.00'))

        rows = self.rows()
        self.assertEqual(rows['shared']['gross'], '1500.00')
        self.assertEqual(rows['shared']['applications'], 0)

    def test_the_breakdown_adds_back_up_to_the_report(self):
        """Two different columns, one answer.

        The financial table sums award lines; this sums the rules behind them.
        If they ever disagree the report is wrong somewhere and this says so.
        """
        self.approved(stream=FundingStream.PSSSP)
        self.approved(stream=FundingStream.DGGR, tuition='4000')
        report = self.report()
        breakdown = sum(Decimal(r['net']) for r in report['programmes']['rows'])
        self.assertEqual(breakdown, Decimal(report['financial']['total']['net']))

    def test_a_repayment_comes_off_the_programme_that_paid(self):
        application = self.approved()
        award = Award.objects.awarded().filter(
            application=application, rule_code='psssp_tuition').first()
        AwardRepayment.objects.create(
            award=award, amount=Decimal('500.00'), reason='Withdrew',
            repaid_on=date(YEAR.year, 11, 2), recorded_by=self.admin)

        rows = self.rows()
        psssp = rows[FundingStream.PSSSP]
        self.assertEqual(psssp['repaid'], '500.00')
        self.assertEqual(Decimal(psssp['net']),
                         Decimal(psssp['gross']) - Decimal('500.00'))
        self.assertEqual(rows[FundingStream.DGGR]['repaid'], '0.00')

    def test_an_empty_year_still_names_every_programme(self):
        """A programme that funded nothing is a fact, not an absence."""
        rows = self.rows()
        for stream, _ in FundingStream.choices:
            self.assertIn(stream, rows)
            self.assertEqual(rows[stream]['net'], '0.00')
        self.assertNotIn(
            'shared', rows,
            'the shared row appears only when there is shared money')


class StreamFilterTests(ReportTestCase):
    """Narrowing the report to one funding programme.

    By the application's primary stream -- the same column the review queue
    filters on -- so "DGGR" means one thing across the portal.
    """

    def test_the_filter_narrows_every_table_not_only_the_breakdown(self):
        self.approved(stream=FundingStream.PSSSP, tuition='9000')
        self.approved(stream=FundingStream.DGGR, tuition='4000')

        whole = reporting.annual_report(YEAR)
        only = reporting.annual_report(YEAR, stream=FundingStream.DGGR)

        self.assertEqual(only['students']['students'], 1)
        self.assertLess(Decimal(only['financial']['total']['gross']),
                        Decimal(whole['financial']['total']['gross']))
        self.assertEqual(only['enrolment']['distinct_students'], 1)
        self.assertEqual(only['filter']['stream'], FundingStream.DGGR)

    def test_a_filtered_report_still_reconciles(self):
        self.approved(stream=FundingStream.PSSSP)
        self.approved(stream=FundingStream.DGGR, tuition='4000')
        report = reporting.annual_report(YEAR, stream=FundingStream.DGGR)
        breakdown = sum(Decimal(r['net']) for r in report['programmes']['rows'])
        self.assertEqual(breakdown, Decimal(report['financial']['total']['net']))

    def test_no_filter_is_every_programme(self):
        self.approved(stream=FundingStream.PSSSP)
        self.approved(stream=FundingStream.DGGR)
        self.assertEqual(
            reporting.annual_report(YEAR)['students']['students'], 2)

    def test_the_endpoint_accepts_a_programme(self):
        self.approved(stream=FundingStream.DGGR)
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get('/api/reports/annual/',
                              {'year': YEAR.year, 'stream': FundingStream.DGGR})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['filter']['stream'],
                         FundingStream.DGGR)

    def test_the_endpoint_refuses_a_programme_that_is_not_one(self):
        """A typo must not silently report an empty year."""
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get('/api/reports/annual/',
                              {'year': YEAR.year, 'stream': 'psspp'})
        self.assertEqual(response.status_code, 400)

    def test_the_export_takes_the_same_filter(self):
        self.approved(stream=FundingStream.DGGR)
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get('/api/reports/annual/pdf/',
                              {'year': YEAR.year, 'stream': FundingStream.DGGR})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        bad = client.get('/api/reports/annual/pdf/',
                         {'year': YEAR.year, 'stream': 'nonsense'})
        self.assertEqual(bad.status_code, 400)


class HighlightsTests(ReportTestCase):

    def test_the_summary_figures_are_computed_from_the_tables(self):
        """The office quotes these in its executive summary. Typed by hand
        they are a second copy that can disagree with the table above them."""
        self.approved(institution_type='college')
        report = self.report()
        highlights = report['highlights']
        self.assertEqual(highlights['semester_enrolments'],
                         report['enrolment']['total']['total'])
        self.assertEqual(highlights['grand_total'],
                         report['financial']['grand_total'])
        self.assertEqual(highlights['direct_funding_net'],
                         report['financial']['total']['net'])


class ReportEndpointTests(ReportTestCase):

    def setUp(self):
        super().setUp()
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')

    def test_only_the_roles_that_see_money_may_read_it(self):
        expected = {Role.ADMIN: 200, Role.DIRECTOR: 200, Role.FINANCE: 200,
                    Role.SUPPORT_WORKER: 403, Role.STUDENT: 403}
        for role, code in expected.items():
            with self.subTest(role=role):
                self.client.force_authenticate(self.person(role))
                self.assertEqual(
                    self.client.get('/api/reports/annual/').status_code, code)

    def test_a_stranger_may_not(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/reports/annual/').status_code, 401)

    def test_a_year_that_is_not_a_year_is_refused(self):
        """A report headed with the wrong year is worse than an error."""
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get('/api/reports/annual/?year=abc').status_code, 400)

    def test_only_an_administrator_may_enter_a_cost(self):
        payload = {'fiscal_year_start': '2026-04-01', 'label': 'Staff wages',
                   'amount': '25000.00'}
        self.client.force_authenticate(self.person(Role.DIRECTOR))
        self.assertEqual(
            self.client.post('/api/reports/costs/', payload, format='json').status_code,
            403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post('/api/reports/costs/', payload, format='json').status_code,
            201)

    def test_entering_the_same_cost_again_corrects_it_rather_than_adding_one(self):
        """Two staff-wage rows in one year make a grand total that depends on
        which the reader adds up."""
        self.client.force_authenticate(self.admin)
        payload = {'fiscal_year_start': '2026-04-01', 'label': 'Staff wages',
                   'amount': '25000.00'}
        self.client.post('/api/reports/costs/', payload, format='json')
        self.client.post('/api/reports/costs/',
                         {**payload, 'amount': '26000.00'}, format='json')
        costs = ReportedCost.objects.filter(fiscal_year_start=YEAR, label='Staff wages')
        self.assertEqual(costs.count(), 1)
        self.assertEqual(costs.first().amount, Decimal('26000.00'))

    def test_a_repayment_may_not_exceed_the_award(self):
        application = self.approved(institution_type='college')
        line = Award.objects.current().filter(application=application).first()
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/reports/repayments/', {
            'award': line.id, 'amount': str(line.amount + Decimal('1')),
            'reason': 'Withdrew', 'repaid_on': '2026-11-02'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_a_repayment_must_say_why(self):
        application = self.approved(institution_type='college')
        line = Award.objects.current().filter(application=application).first()
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/reports/repayments/', {
            'award': line.id, 'amount': '10.00', 'reason': '   ',
            'repaid_on': '2026-11-02'}, format='json')
        self.assertEqual(response.status_code, 400)


class RegistrarQuestionTests(TestCase):
    """The two classifications the report is built on."""

    def test_the_registrar_is_asked_both(self):
        from funding.schemas import get_schema

        schema = get_schema('enrollment_verification')
        for key in ('institution_type', 'program_type'):
            with self.subTest(key=key):
                self.assertIn(key, {f.key for f in schema.fields})

    def test_neither_is_required(self):
        """The registrar's answer governs tuition. A confirmation that cannot
        be submitted because of a reporting question would hold up an award."""
        from funding.schemas import get_schema

        schema = get_schema('enrollment_verification')
        for key in ('institution_type', 'program_type'):
            with self.subTest(key=key):
                self.assertFalse(schema.field(key).required)

    def test_the_program_types_are_the_ones_the_office_asked_for(self):
        from funding.schemas import get_schema

        values = {c.value for c in
                  get_schema('enrollment_verification').field('program_type').choices}
        self.assertEqual(values, {'post_secondary', 'trades', 'upgrading'})


class HeadcountTests(ReportTestCase):
    """A row of the student table is not a student.

    The table is keyed by beneficiary number, which is right: it is what
    the head department reconciles against, and a name is not an
    identifier. But two people holding one number are then one row, and a
    report that calls its row count "students funded" understates the
    program to the funder paying for it.
    """

    def funded(self, number):
        student = self.person()
        student.beneficiary_number = number
        student.save(update_fields=['beneficiary_number'])
        return self.approved(student=student)

    def test_two_people_on_one_number_are_one_row_but_two_students(self):
        self.funded('B-1016')
        self.funded('B-1016')
        students = self.report()['students']
        self.assertEqual(len(students['rows']), 1)
        self.assertEqual(students['students'], 1)
        self.assertEqual(students['distinct_students'], 2)
        self.assertEqual(students['sharing_a_number'], 1)

    def test_the_merged_row_still_carries_both_their_money(self):
        """Merging must not lose funding, only combine it."""
        self.funded('B-1016')
        self.funded('B-1016')
        report = self.report()
        row = report['students']['rows'][0]
        self.assertEqual(Decimal(row['net']),
                         Decimal(report['financial']['total']['net']))
        self.assertEqual(row['applications'], 2)

    def test_distinct_numbers_are_distinct_rows(self):
        self.funded('B-1')
        self.funded('B-2')
        students = self.report()['students']
        self.assertEqual(students['distinct_students'], 2)
        self.assertEqual(students['sharing_a_number'], 0,
                         'nobody is sharing, so nothing is hidden')

    def test_students_with_no_number_are_not_merged_into_each_other(self):
        """The blank is an absence, not a shared identifier."""
        self.approved()
        self.approved()
        students = self.report()['students']
        self.assertEqual(len(students['rows']), 2)
        self.assertEqual(students['unidentified'], 2)
        self.assertEqual(students['sharing_a_number'], 0)

    def test_the_headcount_matches_the_programme_breakdown(self):
        """Two tables, one program, one number of people.

        The breakdown counts people per programme; a student funded from
        one programme only must not make these disagree.
        """
        self.funded('B-1016')
        self.funded('B-1016')
        report = self.report()
        psssp = next(r for r in report['programmes']['rows']
                     if r['stream'] == FundingStream.PSSSP)
        self.assertEqual(psssp['students'],
                         report['students']['distinct_students'])

    def test_the_document_says_a_number_can_be_shared(self):
        from funding.services import report_pdf

        self.funded('B-1016')
        self.funded('B-1016')
        text = self.extracted(report_pdf.render(self.report()))
        self.assertIn('share a number', text)

    def test_and_says_nothing_when_nobody_shares(self):
        from funding.services import report_pdf

        self.funded('B-1')
        text = self.extracted(report_pdf.render(self.report()))
        self.assertNotIn('share a number', text)


class NarrowedExportTests(ReportTestCase):
    """A report for one programme must not pass as the whole year.

    It leaves the office on the department letterhead and is read by a
    funder. Under the annual report's own title and filename, a DGGR-only
    export reads as the whole program with most of the money missing, and
    nothing in the document contradicts that reading.
    """

    def setUp(self):
        super().setUp()
        self.approved(stream=FundingStream.PSSSP)
        self.approved(stream=FundingStream.DGGR, tuition='4000')

    def narrowed(self):
        return reporting.annual_report(YEAR, stream=FundingStream.DGGR)

    def test_the_filename_names_the_programme(self):
        from funding.services import report_pdf

        self.assertNotEqual(
            report_pdf.filename_for(reporting.annual_report(YEAR)),
            report_pdf.filename_for(self.narrowed()))
        self.assertIn(FundingStream.DGGR,
                      report_pdf.filename_for(self.narrowed()))

    def test_the_whole_year_keeps_the_plain_name(self):
        """The common case must not grow a suffix."""
        from funding.services import report_pdf

        self.assertEqual(
            report_pdf.filename_for(reporting.annual_report(YEAR)),
            f'DGG-annual-report-{YEAR.year}.pdf')

    def test_the_document_says_it_covers_one_programme(self):
        from funding.services import report_pdf

        text = self.extracted(report_pdf.render(self.narrowed()))
        self.assertIn('DGGR', text)
        self.assertIn('not the whole program', text)

    def test_the_whole_year_makes_no_such_claim(self):
        from funding.services import report_pdf

        text = self.extracted(
            report_pdf.render(reporting.annual_report(YEAR)))
        self.assertNotIn('not the whole program', text)

    def test_a_narrowed_export_carries_the_narrowed_figures(self):
        """The filter has to reach the document, not only its title.

        A page that says DGGR at the top and reports the whole year
        underneath is worse than one that says nothing.
        """
        from funding.services import report_pdf

        whole = reporting.annual_report(YEAR)
        self.assertNotEqual(
            whole['financial']['grand_total'],
            self.narrowed()['financial']['grand_total'])
        self.assertNotEqual(
            report_pdf.render(whole),
            report_pdf.render(self.narrowed()))


class ReportPdfTests(ReportTestCase):
    """The document the office forwards to its head department."""

    def test_it_renders_a_pdf(self):
        from funding.services import report_pdf

        self.approved(institution_type='college')
        content = report_pdf.render(self.report())
        self.assertTrue(content.startswith(b'%PDF-'))

    def test_every_table_the_office_asked_for_is_in_it(self):
        from funding.services import report_pdf

        self.approved(institution_type='college')
        text = self.extracted(report_pdf.render(self.report()))
        for heading in ('Student enrolment by semester', 'Graduate awards',
                        'Institutions attended', 'Financial summary',
                        'Total program cost'):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_no_column_heading_is_cut_short(self):
        """Wrapping a header to its first line only turned "In trades" and
        "In upgrading" into two columns both headed "In", on a report going to
        a funder."""
        from funding.services import report_pdf

        self.approved(institution_type='college')
        text = self.extracted(report_pdf.render(self.report()))
        for heading in ('Not', 'classified', 'upgrading', 'Trades'):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_the_figures_in_the_pdf_are_the_reports_own(self):
        from funding.services import report_pdf

        self.approved(institution_type='college')
        report = self.report()
        text = self.extracted(report_pdf.render(report))
        self.assertIn(str(report['enrolment']['total']['total']), text)
        # The grand total, formatted as the document formats it.
        grand = f"{float(report['financial']['grand_total']):,.2f}"
        self.assertIn(grand, text)

    def test_the_office_s_own_language_survives(self):
        from funding.services import report_pdf

        self.approved(institution_type='college')
        self.assertIn('Délı̨nę',
                      self.extracted(report_pdf.render(self.report())))

    def test_only_the_roles_that_see_money_may_download_it(self):
        client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        expected = {Role.ADMIN: 200, Role.FINANCE: 200,
                    Role.SUPPORT_WORKER: 403, Role.STUDENT: 403}
        for role, code in expected.items():
            with self.subTest(role=role):
                client.force_authenticate(self.person(role))
                self.assertEqual(
                    client.get('/api/reports/annual/pdf/').status_code, code)
        client.force_authenticate(None)
        self.assertEqual(client.get('/api/reports/annual/pdf/').status_code, 401)

    def test_it_is_served_as_a_pdf_under_a_name_that_says_what_it_is(self):
        client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        client.force_authenticate(self.admin)
        response = client.get('/api/reports/annual/pdf/?year=2026')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('DGG-annual-report-2026.pdf', response['Content-Disposition'])


class ReconciliationEdgeTests(ReportTestCase):
    """Where the money figures could quietly stop reconciling."""

    def test_a_repayment_survives_the_application_being_re_priced(self):
        """`Award.objects.awarded()` scopes to the decision in force, which is
        right for what the office committed to and wrong for what came back:
        re-pricing supersedes the lines, and the repayment attached to one
        disappeared from the report — the year went back to reporting its gross
        as its net, silently. The same reason `Award.objects.paid()` is
        deliberately unscoped."""
        application = self.approved(institution_type='college')
        line = Award.objects.current().filter(application=application).first()
        AwardRepayment.objects.create(
            award=line, amount=Decimal('100.00'), reason='Withdrew',
            repaid_on=date(YEAR.year, 11, 1))
        self.assertEqual(Decimal(self.report()['financial']['total']['repaid']),
                         Decimal('100.00'))

        record_decision(application, actor=self.admin)
        self.assertEqual(
            Decimal(self.report()['financial']['total']['repaid']),
            Decimal('100.00'),
            'money that came back vanished when the application was re-priced')

    def test_a_cost_dated_inside_the_year_lands_on_that_year(self):
        """A date of 15 June was accepted, stored, and appeared on no report at
        all — a figure the office had entered simply vanished."""
        from funding.api.report_views import ReportedCostSerializer

        for raw, expected in (('2026-04-01', date(2026, 4, 1)),
                              ('2026-06-15', date(2026, 4, 1)),
                              ('2027-03-31', date(2026, 4, 1)),
                              ('2026-01-10', date(2025, 4, 1))):
            with self.subTest(raw=raw):
                serializer = ReportedCostSerializer(
                    data={'fiscal_year_start': raw, 'label': 'X', 'amount': '1'})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data['fiscal_year_start'],
                                 expected)

    def test_a_cost_entered_mid_year_reaches_the_report(self):
        client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        client.force_authenticate(self.admin)
        self.approved(institution_type='college')
        client.post('/api/reports/costs/',
                    {'fiscal_year_start': f'{YEAR.year}-06-15',
                     'label': 'Staff wages', 'amount': '5000.00'}, format='json')
        self.assertEqual(Decimal(self.report()['financial']['entered_total']),
                         Decimal('5000.00'))

    def test_an_empty_year_claims_nothing_about_a_busiest_season(self):
        """It named one as having "the highest level of financial assistance
        ($0.00)", which is a claim about nothing."""
        report = reporting.annual_report(date(2030, 4, 1))
        self.assertEqual(report['highlights']['busiest_season'], '')
        self.assertEqual(report['enrolment']['total']['total'], 0)

    def test_an_empty_year_still_renders(self):
        from funding.services import report_pdf

        self.assertTrue(
            report_pdf.render(reporting.annual_report(date(2030, 4, 1)))
            .startswith(b'%PDF-'))

    def test_the_fiscal_year_boundary_is_exact(self):
        """31 March belongs to the year ending; 1 April to the year starting."""
        self.approved(institution_type='college',
                      submitted=timezone.make_aware(
                          timezone.datetime(YEAR.year, 3, 31, 23, 59)))
        self.approved(institution_type='college',
                      submitted=timezone.make_aware(
                          timezone.datetime(YEAR.year, 4, 1, 0, 1)))
        self.approved(institution_type='college',
                      submitted=timezone.make_aware(
                          timezone.datetime(YEAR.year + 1, 3, 31, 23, 59)))
        self.approved(institution_type='college',
                      submitted=timezone.make_aware(
                          timezone.datetime(YEAR.year + 1, 4, 1, 0, 1)))

        counts = {year: reporting.annual_report(
                      date(year, 4, 1))['enrolment']['total']['total']
                  for year in (YEAR.year - 1, YEAR.year, YEAR.year + 1)}
        self.assertEqual(counts, {YEAR.year - 1: 1, YEAR.year: 2, YEAR.year + 1: 1})


class StudentBreakdownTests(ReportTestCase):
    """"Funding breakdown by student no." — the office's own words.

    Identified by beneficiary number rather than name: this is a document that
    leaves the building, the number is what the head department reconciles
    against, and a name is not an identifier.
    """

    def test_funding_is_broken_down_by_student_number(self):
        person = self.person(beneficiary_number='B-7001')
        self.approved(student=person, institution_type='college')
        table = self.report()['students']
        row = next(r for r in table['rows'] if r['student_number'] == 'B-7001')
        self.assertEqual(row['applications'], 1)
        self.assertGreater(Decimal(row['net']), 0)

    def test_a_students_applications_are_added_together(self):
        person = self.person(beneficiary_number='B-7002')
        self.approved(student=person, semester='fall', institution_type='college')
        self.approved(student=person, semester='winter', institution_type='college')
        row = next(r for r in self.report()['students']['rows']
                   if r['student_number'] == 'B-7002')
        self.assertEqual(row['applications'], 2)

    def test_the_rows_add_up_to_the_year(self):
        """A breakdown that does not reconcile with the total above it is a
        breakdown nobody can use."""
        self.approved(institution_type='college')
        self.approved(institution_type='university')
        report = self.report()
        self.assertEqual(
            sum(Decimal(r['net']) for r in report['students']['rows']),
            Decimal(report['financial']['total']['net']))

    def test_a_repayment_shows_against_the_student_it_came_from(self):
        person = self.person(beneficiary_number='B-7003')
        application = self.approved(student=person, institution_type='college')
        line = Award.objects.current().filter(application=application).first()
        AwardRepayment.objects.create(
            award=line, amount=Decimal('50.00'), reason='Withdrew',
            repaid_on=date(YEAR.year, 11, 1))
        row = next(r for r in self.report()['students']['rows']
                   if r['student_number'] == 'B-7003')
        self.assertEqual(Decimal(row['repaid']), Decimal('50.00'))
        self.assertEqual(Decimal(row['net']),
                         Decimal(row['gross']) - Decimal('50.00'))

    def test_a_student_with_no_number_is_listed_rather_than_dropped(self):
        """Dropping them would leave the breakdown short of the year's total."""
        self.approved(student=self.person(), institution_type='college')
        table = self.report()['students']
        self.assertEqual(table['unidentified'], 1)
        self.assertTrue(any(not r['student_number'] for r in table['rows']))

    def test_it_reaches_the_exported_report(self):
        from funding.services import report_pdf

        person = self.person(beneficiary_number='B-7004')
        self.approved(student=person, institution_type='college')
        content = report_pdf.render(self.report())
        import io as _io

        from pypdf import PdfReader
        text = '\n'.join(p.extract_text() or ''
                         for p in PdfReader(_io.BytesIO(content)).pages)
        self.assertIn('Funding by student number', text)
        self.assertIn('B-7004', text)
