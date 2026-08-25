"""The approval letters the office sends.

Three templates, one per programme. The properties that matter are that a
letter belongs to a programme rather than to an application — one approval
routinely draws on two — that its figures are the award's own and cannot drift
from it, and that nothing in it is a number typed twice.
"""

import itertools
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationStatus, ApplicationType, Award, FundingStream,
    PolicySetting,
)
from funding.services import approval_letter as letters
from funding.services import workflow
from funding.services.decisions import record_decision
from funding.test_fixtures import confirm_enrolment
from funding.test_rules import seed_rates

_counter = itertools.count(1)


def make_user(role=Role.STUDENT, **kwargs):
    return User.objects.create_user(
        f'l{next(_counter)}@test.com', 'pw12345678',
        first_name='Sara', last_name='Student', role=role,
        is_deline_beneficiary=True, is_indian_act_registered=True, **kwargs)


def approved_application(student=None, stream=FundingStream.PSSSP, **kwargs):
    student = student or make_user(beneficiary_number='B-1001', treaty_number='T-9001')
    defaults = dict(
        student=student, type=ApplicationType.ADMISSION, stream=stream,
        schema_slug='admission', status=ApplicationStatus.SUBMITTED,
        semester='fall', academic_year='2026-2027',
        answers={
            'course_load': 'full_time', 'confirmed_tuition': '9000',
            'semester_start': '2026-09-01', 'semester_end': '2026-12-31',
            'first_name': 'Sara', 'last_name': 'Student',
        },
    )
    defaults.update(kwargs)
    application = Application.objects.create(**defaults)
    confirm_enrolment(application)
    return application


def price_and_approve(application, actor):
    record_decision(application, actor=actor)
    Application.objects.filter(pk=application.pk).update(
        status=ApplicationStatus.APPROVED)
    application.refresh_from_db()
    return application


class LetterTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)

    def letters_for(self, application):
        return {letter['programme_code']: letter
                for letter in letters.letters_for(application)}

    # ── Which letters exist ────────────────────────────────────────────────

    def test_one_approval_can_owe_two_letters(self):
        """DGGR tops up rather than replaces.

        A student funded under PSSSP with a DGGR top-up is owed the CDFN letter
        and the DGGR one. Keying the letter on `Application.stream` would send
        a single letter naming a total two programmes paid.
        """
        application = price_and_approve(approved_application(), self.admin)
        produced = self.letters_for(application)
        self.assertEqual(set(produced), {'DGG-CDFN', 'DGGR-SFSP'})

    def test_each_letter_carries_only_its_own_programme_s_money(self):
        application = price_and_approve(approved_application(), self.admin)
        produced = self.letters_for(application)

        psssp = sum(line.amount for line in Award.objects.current().filter(
            application=application, rule_code__startswith='psssp'))
        self.assertEqual(Decimal(produced['DGG-CDFN']['total'].replace('$', '').replace(',', '')),
                         psssp)

    def test_the_letters_together_account_for_the_whole_award(self):
        """A letter that omitted money would be the office telling a student
        they were awarded less than they were."""
        application = price_and_approve(approved_application(), self.admin)
        total = sum(Decimal(letter['total'].replace('$', '').replace(',', ''))
                    for letter in letters.letters_for(application))
        self.assertEqual(total, application.awarded_total)

    def test_nothing_is_sent_before_anybody_approves(self):
        application = approved_application()
        record_decision(application, actor=self.admin)
        with self.assertRaises(letters.LetterUnavailable):
            letters.letters_for(application)

    def test_nothing_is_sent_for_an_approval_nobody_priced(self):
        application = approved_application()
        Application.objects.filter(pk=application.pk).update(
            status=ApplicationStatus.APPROVED)
        application.refresh_from_db()
        with self.assertRaises(letters.LetterUnavailable):
            letters.letters_for(application)

    def test_a_one_off_award_gets_no_letter(self):
        """All three templates describe a semester: program costs and a monthly
        allowance, "for the [term]". A graduation cheque has neither, and the
        office has supplied no letter for it — so producing one would send
        somebody a "Semester Stipend" table listing their graduation bursary."""
        application = approved_application(
            type=ApplicationType.GRADUATION_BURSARY, stream=FundingStream.DGGR,
            schema_slug='graduation_bursary',
            answers={'credential': 'bachelors_degree'})
        application = price_and_approve(application, self.admin)
        self.assertTrue(Award.objects.current().filter(application=application).exists())
        with self.assertRaises(letters.LetterUnavailable):
            letters.letters_for(application)

    # ── What a letter says ─────────────────────────────────────────────────

    def test_the_monthly_allowance_says_the_rate_and_the_months(self):
        """The office chose to see "$1,200.00/month × 4 months".

        Read from `Award.detail`, which the rule wrote as figures. Reading it
        back out of the rule's explanation sentence would put a display string
        in charge of what a letter says somebody is paid.
        """
        application = price_and_approve(approved_application(), self.admin)
        row = next(r for r in self.letters_for(application)['DGG-CDFN']['rows']
                   if r['label'] == 'Monthly Allowance')
        self.assertIn('/month', row['note'])
        self.assertIn('month', row['note'])
        rate = PolicySetting.objects.get(section='psssp_living',
                                         key='fulltime_no_dependents').value
        self.assertIn(f'${rate:,.2f}', row['note'])

    def test_an_allowance_priced_before_the_detail_existed_shows_the_amount_alone(self):
        """Rather than inventing a rate. Every award priced before the column
        was added carries nothing, and so does a hand-set one."""
        application = price_and_approve(approved_application(), self.admin)
        Award.objects.filter(application=application, category='living').update(detail={})
        row = next(r for r in self.letters_for(application)['DGG-CDFN']['rows']
                   if r['label'] == 'Monthly Allowance')
        self.assertEqual(row['note'], '')
        self.assertTrue(row['amount'].startswith('$'))

    def test_the_cap_in_the_footnote_is_the_policy_rate(self):
        """It is a figure the office edits on the policy screen. Typed into the
        letter as well, it is a second copy that can disagree — which is how a
        "$500 limit" on a screen came to sit beside a $3,000 seeded rate."""
        application = price_and_approve(approved_application(), self.admin)
        PolicySetting.objects.filter(section='psssp_tuition',
                                     key='max_per_semester').update(value=Decimal('5500'))
        footnote = self.letters_for(application)['DGG-CDFN']['footnote']
        self.assertIn('$5,500.00', footnote)

    def test_a_missing_cap_drops_the_sentence_rather_than_printing_nothing(self):
        """A missing rate must never read as $0.00 — that is a letter telling a
        student the cap on their funding is nought."""
        application = price_and_approve(approved_application(), self.admin)
        PolicySetting.objects.filter(section='psssp_tuition',
                                     key='max_per_semester').delete()
        self.assertEqual(self.letters_for(application)['DGG-CDFN']['footnote'], '')

    def test_each_programme_asks_for_the_identifier_its_template_asks_for(self):
        application = price_and_approve(approved_application(), self.admin)
        produced = self.letters_for(application)
        self.assertEqual(produced['DGG-CDFN']['identifier']['label'], 'Treaty #:')
        self.assertEqual(produced['DGG-CDFN']['identifier']['value'], 'T-9001')
        self.assertEqual(produced['DGGR-SFSP']['identifier']['label'], 'Beneficiary #:')
        self.assertEqual(produced['DGGR-SFSP']['identifier']['value'], 'B-1001')

    def test_the_term_is_written_the_way_the_form_offered_it(self):
        """"Fall", not "fall" — taken from the schema's own choice label rather
        than title-cased into shape."""
        application = price_and_approve(approved_application(), self.admin)
        self.assertEqual(self.letters_for(application)['DGG-CDFN']['term'],
                         'Fall 2026-2027')

    def test_only_the_dggr_letter_has_no_total_on_ucepp(self):
        """The office's UCEPP template carries no total row. Inventing one would
        be this system deciding what the office's letter says."""
        self.assertEqual(letters.PROGRAMMES[FundingStream.UCEPP]['total_label'], '')
        self.assertEqual(letters.PROGRAMMES[FundingStream.PSSSP]['total_label'],
                         'Total Allotted')
        self.assertEqual(letters.PROGRAMMES[FundingStream.DGGR]['total_label'], 'Total')

    def test_the_signatory_is_a_setting_not_a_name_in_the_code(self):
        """A Director who leaves the post should not need a release to stop
        signing the office's letters."""
        with self.settings(DIRECTOR_NAME='A Nother', DIRECTOR_EMAIL='a@gov.deline.ca'):
            signed = letters.signatory()
        self.assertEqual(signed['name'], 'A Nother')
        self.assertEqual(signed['email'], 'a@gov.deline.ca')

    def test_a_hand_set_award_lands_on_the_programme_it_was_filed_under(self):
        """`manual_N` belongs to no rule, so nothing can attribute it. Dropping
        it would produce letters adding up to less than the award."""
        application = price_and_approve(approved_application(), self.admin)
        Award.objects.filter(application=application).update(rule_code='manual_1')
        produced = letters.letters_for(application)
        self.assertEqual([letter['programme_code'] for letter in produced], ['DGG-CDFN'])
        self.assertEqual(
            Decimal(produced[0]['total'].replace('$', '').replace(',', '')),
            application.awarded_total)


class LetterEmailTests(TestCase):
    """The letter has to actually arrive.

    Asserting that a letter can be *built* is the same as asserting a link has
    an href. What matters is that the message queued for the student contains
    it, so these read the queued row rather than the function's return value.
    """

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)

    def approve_and_queue(self, application, approved=True, reason=''):
        # Queued on commit, so a student is never told about a decision that
        # rolled back. Nothing is queued inside a TestCase's transaction until
        # the callbacks are run.
        from funding.services import messages
        with self.captureOnCommitCallbacks(execute=True):
            messages.send_decision(application, approved=approved, reason=reason)

    def queued_body(self):
        from notifications.models import OutboundEmail
        return OutboundEmail.objects.latest('id').body_html

    def test_the_approval_email_carries_the_letter_itself(self):
        application = price_and_approve(approved_application(), self.admin)
        self.approve_and_queue(application)
        body = self.queued_body()

        self.assertIn('Program Costs', body)
        self.assertIn('Total Allotted', body)
        self.assertIn('Dear Sara Student', body)
        # The office's sign-off, not just a summary of the award.
        self.assertIn('Director of Education', body)
        self.assertIn('www.deline.ca', body)

    def test_both_programmes_letters_are_sent_where_both_funded_the_semester(self):
        application = price_and_approve(approved_application(), self.admin)
        self.approve_and_queue(application)
        body = self.queued_body()
        self.assertIn('DGG-CDFN', body)
        self.assertIn('DGGR-SFSP', body)
        self.assertIn('Semester Stipend', body)

    def test_the_amounts_in_the_email_are_the_amounts_awarded(self):
        application = price_and_approve(approved_application(), self.admin)
        self.approve_and_queue(application)
        body = self.queued_body()
        for letter in letters.letters_for(application):
            self.assertIn(letter['total'], body)

    def test_a_decision_is_still_announced_when_there_is_no_letter(self):
        """A one-off award has no letter the office supplied. The student must
        still be told they were approved — a missing letter is not a reason to
        swallow the decision."""
        application = approved_application(
            type=ApplicationType.GRADUATION_BURSARY, stream=FundingStream.DGGR,
            schema_slug='graduation_bursary', answers={'credential': 'diploma'})
        application = price_and_approve(application, self.admin)
        self.approve_and_queue(application)
        body = self.queued_body()
        self.assertIn('approved', body.lower())
        self.assertNotIn('Semester Stipend', body)

    def test_a_declined_application_is_sent_no_letter(self):
        application = price_and_approve(approved_application(), self.admin)
        self.approve_and_queue(application, approved=False, reason='Not eligible')
        body = self.queued_body()
        self.assertNotIn('Total Allotted', body)
        self.assertIn('Not eligible', body)


class TemplateFidelityTests(TestCase):
    """Where the three templates differ from each other.

    Each of these was wrong in the first build and found by rendering a real
    letter in a browser and reading it beside the office's PDF. They are the
    details a test built from the same assumption as the code cannot catch.
    """

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)
        self.application = price_and_approve(approved_application(), self.admin)
        self.produced = {letter['programme_code']: letter
                         for letter in letters.letters_for(self.application)}

    def test_the_term_completes_a_title_that_ends_for_the(self):
        """CDFN and UCEPP read "…Student Bursary for the Fall 2026-2027"."""
        self.assertEqual(self.produced['DGG-CDFN']['term'], 'Fall 2026-2027')
        self.assertTrue(letters.PROGRAMMES[FundingStream.PSSSP]['title']
                        .rstrip().endswith('for the'))

    def test_a_title_that_is_already_a_sentence_takes_no_term(self):
        """The DGGR title ends "…Top-Up Funds". Appending the term to it read
        as "Top-Up Funds Fall 2026-2027". The semester is in the breakdown's own
        column, which is where that template puts it."""
        self.assertEqual(self.produced['DGGR-SFSP']['term'], '')
        self.assertEqual(self.produced['DGGR-SFSP']['semester'], 'Fall')

    def test_only_the_dggr_letter_carries_a_date(self):
        """Two of the three templates have no line for one, and inventing a
        place for it is this system deciding what the office's letter says."""
        self.assertTrue(self.produced['DGGR-SFSP']['date'])
        self.assertEqual(self.produced['DGG-CDFN']['date'], '')

    def test_the_identifier_is_punctuated_as_the_template_punctuates_it(self):
        self.assertEqual(self.produced['DGG-CDFN']['identifier']['label'], 'Treaty #:')
        self.assertEqual(self.produced['DGGR-SFSP']['identifier']['label'],
                         'Beneficiary #:')

    def test_an_identifier_the_account_lacks_leaves_the_line_blank(self):
        """Rather than dropping it. The office writes the number on by hand, so
        a letter with no line for it cannot be completed."""
        student = make_user()  # no treaty or beneficiary number
        application = price_and_approve(approved_application(student=student), self.admin)
        letter = next(l for l in letters.letters_for(application)
                      if l['programme_code'] == 'DGG-CDFN')
        self.assertEqual(letter['identifier']['label'], 'Treaty #:')
        self.assertEqual(letter['identifier']['value'], '')

    def test_the_emailed_copy_carries_the_date_only_where_the_letter_has_one(self):
        self.assertIn('Date:', letters.render_email(self.produced['DGGR-SFSP']))
        self.assertNotIn('Date:', letters.render_email(self.produced['DGG-CDFN']))


class LetterReachesTheStudentTests(TestCase):
    """The letter has to arrive whichever order the office works in.

    Every other test here prices first and approves second, because that is the
    order the audits walk. Nothing in `workflow.ALLOWED_ACTIONS` requires it:
    an application can be approved and priced afterwards, and on that path the
    approval email had no award to describe and nothing ever sent one. The
    student got no letter at all, in silence, and the whole suite passed.
    """

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)

    def letter_bodies(self):
        from notifications.models import OutboundEmail
        return [row.body_html for row in OutboundEmail.objects.all()]

    def sent_a_letter(self):
        return any('Total Allotted' in body for body in self.letter_bodies())

    def test_priced_then_approved_carries_the_letter_in_the_approval_email(self):
        application = approved_application()
        record_decision(application, actor=self.admin)
        workflow.record(application, 'reviewed', actor=self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, 'approved', actor=self.admin)

        from notifications.models import OutboundEmail
        self.assertIn('Total Allotted', OutboundEmail.objects.latest('id').body_html)

    def test_approved_then_priced_still_reaches_the_student(self):
        application = approved_application()
        workflow.record(application, 'reviewed', actor=self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, 'approved', actor=self.admin)
        # Nothing to describe yet — and that is not a fault, it is the reason
        # the letter cannot ride along with this email.
        self.assertFalse(self.sent_a_letter())

        with self.captureOnCommitCallbacks(execute=True):
            record_decision(application, actor=self.admin)
        self.assertTrue(self.sent_a_letter(),
                        'the student was approved and never sent a letter')

    def test_pricing_an_application_nobody_approved_sends_nothing(self):
        """A pricing is not a promise. Sending a letter of congratulation for a
        decision nobody has made is worse than sending none."""
        application = approved_application()
        with self.captureOnCommitCallbacks(execute=True):
            record_decision(application, actor=self.admin)
        self.assertFalse(self.sent_a_letter())

    def test_re_pricing_an_approved_application_corrects_the_letter(self):
        """A superseded letter nobody corrects names figures the office is no
        longer paying, in a document the student is holding."""
        application = approved_application()
        record_decision(application, actor=self.admin)
        workflow.record(application, 'reviewed', actor=self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, 'approved', actor=self.admin)

        from notifications.models import OutboundEmail
        before = OutboundEmail.objects.count()
        PolicySetting.objects.filter(section='psssp_living',
                                     key='fulltime_no_dependents').update(
            value=Decimal('1500'))
        with self.captureOnCommitCallbacks(execute=True):
            record_decision(application, actor=self.admin)

        self.assertGreater(OutboundEmail.objects.count(), before,
                           'the figures changed and nobody told the student')
        latest = OutboundEmail.objects.latest('id').body_html
        self.assertIn('$1,500.00/month', latest)
        self.assertIn('replaces it', latest)

    def test_a_hand_set_award_on_an_approved_application_corrects_it_too(self):
        """Same class: an administrator setting the breakdown by hand changes
        what the student was told they are getting."""
        from funding.services.decisions import record_manual_decision

        application = approved_application()
        record_decision(application, actor=self.admin)
        workflow.record(application, 'reviewed', actor=self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            workflow.record(application, 'approved', actor=self.admin)

        from notifications.models import OutboundEmail
        before = OutboundEmail.objects.count()
        with self.captureOnCommitCallbacks(execute=True):
            record_manual_decision(
                application,
                [{'category': 'tuition', 'amount': Decimal('1234.00'),
                  'description': 'Agreed at the counter'}],
                actor=self.admin, note='Fee no rate covers')

        self.assertGreater(OutboundEmail.objects.count(), before)
        self.assertIn('$1,234.00', OutboundEmail.objects.latest('id').body_html)


class EmailEncodingTests(TestCase):
    """The office's own language has to survive the trip.

    Encoding has already cost this project 143 unsent messages, and the letter
    carries far more of the language than any earlier message did — the
    programme names, the place name, the office's wording.
    """

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)

    def test_the_message_declares_its_encoding_in_the_html_as_well(self):
        """The MIME part already says utf-8 and a conforming client honours it.
        This is for the ones that do not: webmail that lifts the body into its
        own document, and anybody who saves or forwards the HTML."""
        from funding.services import messages
        self.assertIn('<meta charset="utf-8">', messages._wrap('Hi', '<p>x</p>'))

    def test_the_letter_survives_the_mail_pipeline_intact(self):
        """Asserted through what Django actually sends, not what was composed:
        the message is encoded quoted-printable on the way out."""
        import quopri
        from django.core.mail import EmailMultiAlternatives
        from funding.services import messages

        application = price_and_approve(approved_application(), self.admin)
        body = messages._wrap('Approved', messages._approval_letters(application))

        message = EmailMultiAlternatives('s', 'text', 'a@b.test', ['c@d.test'])
        message.attach_alternative(body, 'text/html')
        html_part = [part for part in message.message().walk()
                     if part.get_content_type() == 'text/html'][0]

        self.assertEqual(html_part.get_content_charset(), 'utf-8')
        decoded = quopri.decodestring(
            html_part.get_payload().encode('ascii')).decode('utf-8')
        # The place name, and the programme name with the characters most
        # likely to be mangled.
        self.assertIn('Délı̨nę', decoded)
        self.assertIn('Dèlı̨nę', decoded)
        self.assertIn('Total Allotted', decoded)
