"""The residency contradiction the office asked to be flagged.

Reported by the office: *a student said they do not live in the Northwest
Territories and then gave an address in the Northwest Territories, and nothing
said so.* `residency_flag` had existed since the first migration with two
readers and no writer at all, so the dashboard count could only ever be zero.

These pin the rule as stated and — at least as importantly — the cases that
must **not** flag. A flag that fires on ordinary circumstances is a queue
nobody can clear, which is how this one came to be ignored.
"""

import itertools

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType,
    FundingStream,
)
from funding.services import residency, workflow
from funding.test_rules import seed_rates

_ids = itertools.count(1)

SCREENING = {
    'indian_act_registered': 'yes', 'deline_beneficiary': 'yes',
    'receives_sfa': 'no', 'lives_in_nwt': 'yes',
    'accredited_institution': 'yes', 'programme_twelve_weeks': 'yes',
}

NWT = {'street_address': '12 Bear Rock Road', 'city': 'Délı̨nę',
       'province': 'NT', 'postal_code': 'X0E 0G0'}
ELSEWHERE = {'street_address': '400 Jasper Avenue', 'city': 'Edmonton',
             'province': 'AB', 'postal_code': 'T5J 0N3'}


class AddressRecognitionTests(TestCase):
    """What counts as an address in the Northwest Territories."""

    def test_the_territory_however_it_is_written(self):
        for province in ('NT', 'nt', 'N.T.', 'NWT', 'N.W.T.',
                         'Northwest Territories', 'northwest territories'):
            with self.subTest(province=province):
                self.assertTrue(residency.looks_like_nwt(province, ''))

    def test_a_postal_code_where_the_province_was_left_blank(self):
        """An address is not "not in the NWT" because somebody skipped a box."""
        for code in ('X0E 0G0', 'x0e0g0', 'X1A 2P4', 'X0G 1A0'):
            with self.subTest(code=code):
                self.assertTrue(residency.looks_like_nwt('', code))

    def test_nunavut_is_not_the_northwest_territories(self):
        """X0A–X0C are Nunavut. Reading them as NWT would tell a reviewer
        something untrue about somebody's address."""
        for code in ('X0A 0H0', 'X0B 1C0', 'X0C 0G0'):
            with self.subTest(code=code):
                self.assertFalse(residency.looks_like_nwt('', code))
        self.assertFalse(residency.looks_like_nwt('Nunavut', 'X0C 0G0'))

    def test_other_provinces_are_not_matched(self):
        for province, code in (('AB', 'T5J 0N3'), ('Ontario', 'M5H 2N2'),
                               ('BC', 'V6B 1A1'), ('', '')):
            with self.subTest(province=province):
                self.assertFalse(residency.looks_like_nwt(province, code))

    def test_nt_inside_a_word_is_not_the_territory(self):
        """Matched whole rather than as a substring — 'Ontario' and 'Kent'
        both contain it."""
        for province in ('Ontario', 'Kent', 'Nunavut', 'Vermont'):
            with self.subTest(province=province):
                self.assertFalse(residency.looks_like_nwt(province, ''))


class FlaggingTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)

    def student(self, lives_in_nwt='yes', **account):
        n = next(_ids)
        person = User.objects.create_user(
            f'res{n}@test.com', 'pw12345678', first_name='Res', last_name=f'T{n}',
            role=Role.STUDENT, is_deline_beneficiary=True,
            is_indian_act_registered=True, **account)
        person.eligibility_answers = {**SCREENING, 'lives_in_nwt': lives_in_nwt}
        person.save(update_fields=['eligibility_answers'])
        return person

    def filed(self, student, address=None, **extra):
        application = Application.objects.create(
            student=student, type=ApplicationType.ADMISSION,
            stream=FundingStream.PSSSP, schema_slug='admission',
            status=ApplicationStatus.DRAFT, semester='fall',
            academic_year='2026-2027',
            answers={'course_load': 'full_time', **(address or {}), **extra})
        workflow.record(application, ApplicationEvent.Action.SUBMITTED)
        application.refresh_from_db()
        return application

    # ── The reported fault ─────────────────────────────────────────────────

    def test_not_a_resident_but_an_nwt_address_is_flagged(self):
        """The office's report, exactly."""
        application = self.filed(self.student(lives_in_nwt='no'), NWT)
        self.assertTrue(application.residency_flag)
        self.assertIn('Northwest Territories', application.residency_flag)

    def test_the_flag_reaches_the_dashboard_count(self):
        """It had two readers and no writer, so the count could only be zero."""
        from funding.services import dashboard

        staff = User.objects.create_user('resstaff@test.com', 'pw12345678',
                                         role=Role.SUPPORT_WORKER)
        self.filed(self.student(lives_in_nwt='no'), NWT)
        self.assertEqual(
            dashboard.summary(staff)['attention']['residency_mismatch'], 1)

    # ── What must not be flagged ───────────────────────────────────────────

    def test_a_resident_with_an_nwt_address_is_not_flagged(self):
        self.assertFalse(self.filed(self.student('yes'), NWT).residency_flag)

    def test_a_non_resident_with_an_address_elsewhere_is_not_flagged(self):
        """Consistent answers. This is the ordinary case for a student living
        outside the territory."""
        self.assertFalse(self.filed(self.student('no'), ELSEWHERE).residency_flag)

    def test_somebody_moving_to_the_nwt_is_not_flagged(self):
        """The screening offers "Not yet — I am moving there". Someone moving
        to the NWT who gives an NWT address is describing the move, not
        contradicting themselves. Checking against 'yes' alone would have read
        this as a denial."""
        self.assertFalse(self.filed(self.student('moving'), NWT).residency_flag)

    def test_an_unanswered_screening_is_not_a_denial(self):
        for answer in ('', None):
            with self.subTest(answer=answer):
                self.assertFalse(
                    self.filed(self.student(answer), NWT).residency_flag)

    def test_an_application_with_no_address_anywhere_is_not_flagged(self):
        self.assertFalse(self.filed(self.student('no')).residency_flag)

    # ── Where the address is read from ─────────────────────────────────────

    def test_the_profile_address_is_used_where_the_form_asks_for_none(self):
        """Only two of the ten forms ask for an address. Without the fallback
        the check would silently do nothing on the other eight."""
        person = self.student('no', province='NT', postal_code='X0E 0G0')
        application = Application.objects.create(
            student=person, type=ApplicationType.CONTINUING_FUNDING,
            stream=FundingStream.PSSSP, schema_slug='continuing_funding',
            status=ApplicationStatus.DRAFT, semester='fall',
            academic_year='2026-2027', answers={'course_load': 'full_time'})
        workflow.record(application, ApplicationEvent.Action.SUBMITTED)
        application.refresh_from_db()
        self.assertTrue(application.residency_flag)

    def test_the_application_address_wins_over_the_profile(self):
        """The address on this form is the one the office is comparing."""
        person = self.student('no', province='AB', postal_code='T5J 0N3')
        self.assertTrue(self.filed(person, NWT).residency_flag)

    # ── It follows the answers ─────────────────────────────────────────────

    def test_correcting_the_address_clears_the_flag(self):
        """Unlike lateness, this is a statement about the answers the
        application currently holds, so it is re-decided rather than stamped
        once and left."""
        application = self.filed(self.student('no'), NWT)
        self.assertTrue(application.residency_flag)

        application.answers = {**application.answers, **ELSEWHERE}
        application.save(update_fields=['answers'])
        residency.stamp(application)
        application.refresh_from_db()
        self.assertEqual(application.residency_flag, '')

    def test_correcting_an_address_into_the_nwt_raises_one(self):
        application = self.filed(self.student('no'), ELSEWHERE)
        self.assertEqual(application.residency_flag, '')

        application.answers = {**application.answers, **NWT}
        application.save(update_fields=['answers'])
        residency.stamp(application)
        application.refresh_from_db()
        self.assertTrue(application.residency_flag)

    def test_stamping_writes_nothing_when_nothing_changed(self):
        """It is called on every submission and every amendment; a save that
        writes the same value is a write nobody asked for."""
        application = self.filed(self.student('yes'), NWT)
        before = application.updated_at
        residency.stamp(application)
        application.refresh_from_db()
        self.assertEqual(application.updated_at, before)

    def test_a_guest_application_is_not_flagged(self):
        """No account behind it, so no screening answer to contradict."""
        application = Application.objects.create(
            student=None, type=ApplicationType.GRADUATION_BURSARY,
            stream=FundingStream.DGGR, schema_slug='graduation_bursary',
            status=ApplicationStatus.DRAFT, answers={**NWT})
        self.assertEqual(residency.assess(application), '')
