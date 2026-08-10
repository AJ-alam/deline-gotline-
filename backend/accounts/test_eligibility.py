"""Who may apply for funding at all.

These are the office's rules, transcribed from the sign-up page they used to
live inside. They are tested here because the browser is not a place to enforce
policy: the previous version could be bypassed by calling the API directly.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from accounts.services import eligibility

ELIGIBLE_BOTH = {
    'indian_act_registered': 'yes',
    'deline_beneficiary': 'yes',
    'receives_sfa': 'no',
    'lives_in_nwt': 'yes',
    'accredited_institution': 'yes',
    'programme_twelve_weeks': 'yes',
}


class StreamRoutingTests(TestCase):

    def test_registered_and_not_on_sfa_qualifies_for_psssp(self):
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'deline_beneficiary': 'no'})
        self.assertTrue(outcome.eligible)
        self.assertEqual(outcome.streams, ['psssp'])

    def test_a_beneficiary_qualifies_for_dggr(self):
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'indian_act_registered': 'no'})
        self.assertEqual(outcome.streams, ['dggr'])

    def test_both_can_apply_together(self):
        self.assertEqual(eligibility.assess(ELIGIBLE_BOTH).streams, ['psssp', 'dggr'])

    def test_sfa_blocks_cdfn_but_not_the_dggr_bursary(self):
        """The distinction the office draws, and the one most easily lost."""
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'receives_sfa': 'yes'})
        self.assertTrue(outcome.eligible)
        self.assertEqual(outcome.streams, ['dggr'])

    def test_living_outside_the_nwt_does_not_by_itself_disqualify(self):
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'lives_in_nwt': 'no'})
        self.assertTrue(outcome.eligible)


class RefusalTests(TestCase):

    def test_an_unaccredited_institution_stops_intake(self):
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'accredited_institution': 'no'})
        self.assertFalse(outcome.eligible)
        self.assertIn('accredited', outcome.message.lower())

    def test_a_short_programme_stops_intake(self):
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'programme_twelve_weeks': 'no'})
        self.assertFalse(outcome.eligible)

    def test_an_affiliated_person_on_a_short_programme_is_pointed_elsewhere(self):
        """They are one of ours; they should be told where else to ask."""
        outcome = eligibility.assess({**ELIGIBLE_BOTH, 'programme_twelve_weeks': 'no'})
        self.assertIn('Sahtu Dene Council', outcome.message)

    def test_neither_registered_nor_a_beneficiary_is_refused_with_the_reason(self):
        outcome = eligibility.assess({
            **ELIGIBLE_BOTH, 'indian_act_registered': 'no', 'deline_beneficiary': 'no',
        })
        self.assertFalse(outcome.eligible)
        self.assertIn('Indian Act', outcome.message)

    def test_sfa_with_no_beneficiary_status_leaves_nothing_and_says_so(self):
        outcome = eligibility.assess({
            **ELIGIBLE_BOTH, 'deline_beneficiary': 'no', 'receives_sfa': 'yes',
        })
        self.assertFalse(outcome.eligible)
        self.assertIn('Student Financial Assistance', outcome.message)
        self.assertIn('DGGR', outcome.message)

    def test_unanswered_questions_are_not_treated_as_a_refusal(self):
        outcome = eligibility.assess({'indian_act_registered': 'yes'})
        self.assertFalse(outcome.eligible)
        self.assertIn('answer all six', outcome.message.lower())

    def test_every_question_must_be_answered(self):
        self.assertEqual(len(eligibility.missing_answers({})), 6)


class EndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')

    def _register(self, **overrides):
        payload = {
            'email': 'new@example.com', 'password': 'pw12345678',
            'confirm_password': 'pw12345678', 'first_name': 'New',
            'last_name': 'Person', 'eligibility': dict(ELIGIBLE_BOTH),
        }
        payload.update(overrides)
        return self.client.post('/api/auth/register/', payload, format='json')

    def test_the_questions_are_public(self):
        response = self.client.get('/api/auth/eligibility/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['questions']), 6)
        self.assertTrue(response.data['questions'][0]['choices'])

    def test_someone_can_check_before_they_have_an_account(self):
        response = self.client.post('/api/auth/eligibility/',
                                    {'answers': ELIGIBLE_BOTH}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['eligible'])

    def test_an_eligible_person_can_register(self):
        self.assertEqual(self._register().status_code, 201)

    def test_an_ineligible_person_is_refused_with_the_guidance(self):
        response = self._register(eligibility={
            **ELIGIBLE_BOTH, 'indian_act_registered': 'no', 'deline_beneficiary': 'no',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Indian Act', str(response.data['eligibility']))
        self.assertFalse(User.objects.filter(email='new@example.com').exists())

    def test_the_gate_cannot_be_skipped_by_omitting_the_answers(self):
        """The old rule lived in the browser; calling the API bypassed it."""
        response = self._register(eligibility={})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_mismatched_passwords_are_refused(self):
        response = self._register(confirm_password='something-else')
        self.assertEqual(response.status_code, 400)
        self.assertIn('confirm_password', response.data)

    def test_what_the_answers_say_about_the_person_is_kept(self):
        self._register()
        person = User.objects.get(email='new@example.com')
        self.assertTrue(person.is_indian_act_registered)
        self.assertTrue(person.is_deline_beneficiary)

    def test_answers_about_a_course_of_study_are_not_stored_on_the_person(self):
        """SFA and programme length belong to an application, not to someone
        permanently — they change every term."""
        self._register()
        person = User.objects.get(email='new@example.com')
        held = {f.name for f in person._meta.get_fields()}
        self.assertNotIn('receives_sfa', held)
        self.assertNotIn('financial_assistance_status', held)
