"""Reading the full SIN and the full bank account.

`identifiers.reveal` was written in the first build with a reason argument, an
audit entry and unit tests — and no endpoint. So from the portal the whole
number was unreadable by anyone: an administrator doing the federal PSSSP
return, which is why the SIN is collected at all, saw `•••••996` and had no way
to see more. The masked value is what made it survive; a screen showing a
plausible placeholder does not look like a missing feature.

The office asked for these to be visible to administrators. What is kept is the
audit entry, which costs the reader nothing and is the whole defence if anyone
ever asks who read whose. What is dropped is the demand for a typed
justification: a box required on every read is a box filled with a full stop.
"""

import itertools

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import BankAccount, Role, User
from funding.models import ApplicantIdentifier, Application, AuditEntry
from funding.test_fixtures import TEST_SIN, admission_answers

_counter = itertools.count(1)


def make_user(role=Role.STUDENT, **flags):
    defaults = dict(is_deline_beneficiary=True, is_indian_act_registered=True)
    defaults.update(flags)
    return User.objects.create_user(
        f'{role}{next(_counter)}@reveal.test', 'pw12345678',
        first_name='Test', last_name=str(role).title(), role=role, **defaults)


class RevealTests(APITestCase):
    def setUp(self):
        self.student = make_user()
        self.admin = make_user(Role.ADMIN)
        self.worker = make_user(Role.SUPPORT_WORKER)
        self.director = make_user(Role.DIRECTOR)
        self.finance = make_user(Role.FINANCE)

        self.client.force_authenticate(self.student)
        response = self.client.post('/api/applications/', {
            'type': 'admission',
            'answers': admission_answers(
                sin=TEST_SIN,
                account_holder='Majid Khan',
                transit_number='12345',
                institution_number='003',
                account_number='7654321',
            ),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

    def url(self, application=None):
        return f'/api/applications/{(application or self.application).pk}/identifiers/'

    # ── What the office can now read ────────────────────────────────────────

    def test_an_administrator_reads_the_whole_sin(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url(), {}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['identifiers']['sin'], TEST_SIN)

    def test_and_the_whole_bank_account(self):
        self.client.force_authenticate(self.admin)
        account = self.client.post(self.url(), {}, format='json').data['bank_account']

        self.assertEqual(account['account_number'], '7654321')
        self.assertEqual(account['transit_number'], '12345')
        self.assertEqual(account['institution_number'], '003')
        self.assertEqual(account['account_holder'], 'Majid Khan')

    def test_the_account_is_the_one_finance_will_actually_pay(self):
        """Read from `BankAccount`, not from `answers`.

        The banking answers are split off at validation and never stored on the
        application, so a screen that read them back from `answers` would show
        an empty account for every application filed since — while the payment
        run paid a number nothing on any screen had displayed.
        """
        from funding.services import finance

        self.client.force_authenticate(self.admin)
        shown = self.client.post(self.url(), {}, format='json').data['bank_account']

        record = BankAccount.objects.get(user=self.student, is_current=True)
        self.assertEqual(shown['account_number'], record.account_number)
        self.assertEqual(shown['source'], 'account')
        # And it is the same record the payment path reads.
        self.assertEqual(finance._bank_account(self.student).pk, record.pk)

    def test_no_reason_has_to_be_typed(self):
        """The office asked for these to be visible. A mandatory justification
        on every read is a box that fills with a full stop."""
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url(), {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_a_reason_is_recorded_when_one_is_given(self):
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), {'reason': 'Federal PSSSP return'}, format='json')

        entry = AuditEntry.objects.get(action='identifier.revealed')
        self.assertIn('Federal PSSSP return', entry.detail)

    # ── The record of who looked ────────────────────────────────────────────

    def test_reading_the_sin_is_written_down(self):
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), {}, format='json')

        entry = AuditEntry.objects.get(action='identifier.revealed')
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.actor_role, Role.ADMIN)
        self.assertEqual(entry.application_id, self.application.pk)

    def test_reading_the_bank_account_is_written_down_separately(self):
        """Two different disclosures. One entry covering both would make the
        log unable to answer 'who has seen this person's SIN'."""
        self.client.force_authenticate(self.admin)
        self.client.post(self.url(), {}, format='json')

        self.assertTrue(AuditEntry.objects.filter(action='banking.revealed',
                                                  actor=self.admin).exists())

    def test_the_audit_entry_is_written_before_the_value_comes_back(self):
        """A read that could return the number without recording it is an
        unlogged read. Asserted by counting entries against reads."""
        self.client.force_authenticate(self.admin)
        for _ in range(3):
            self.client.post(self.url(), {}, format='json')

        self.assertEqual(
            AuditEntry.objects.filter(action='identifier.revealed').count(), 3)

    # ── Who may not ─────────────────────────────────────────────────────────

    def test_a_support_worker_may_not(self):
        """`reviews_applications` includes the people who assess these. The
        office's rule is that reading a regulated identifier is an
        administrator's act."""
        self.client.force_authenticate(self.worker)
        response = self.client.post(self.url(), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(AuditEntry.objects.filter(action='identifier.revealed').exists())

    def test_nor_the_director(self):
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(self.url(), {}, format='json').status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_nor_finance(self):
        """The payment file already carries the account finance needs, and it
        is built for them rather than read off a screen."""
        self.client.force_authenticate(self.finance)
        self.assertEqual(self.client.post(self.url(), {}, format='json').status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_nor_the_student_it_belongs_to(self):
        """Their own number, but this endpoint is the office's audited read.
        A student who could call it would generate audit entries naming
        themselves as the reader of their own file."""
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(self.url(), {}, format='json').status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_nor_another_student(self):
        other = make_user()
        self.client.force_authenticate(other)
        response = self.client.post(self.url(), {}, format='json')
        self.assertIn(response.status_code,
                      (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_nor_a_stranger(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url(), {}, format='json').status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_it_is_not_a_get(self):
        """Reading writes an audit entry, and a GET that changes the record is
        one a browser or a proxy may repeat by itself."""
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.url()).status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    # ── The detail endpoint is unchanged ────────────────────────────────────

    def test_the_detail_screen_still_masks_everything(self):
        """Visible on request, not on every page load. A detail endpoint that
        returned the number would put it in every staff response, every browser
        cache and every log — and would need an audit entry per page view,
        which makes the log useless."""
        self.client.force_authenticate(self.admin)
        body = self.client.get(f'/api/applications/{self.application.pk}/').data

        self.assertEqual(body['identifiers']['sin'], f'•••••{TEST_SIN[-3:]}')
        self.assertNotIn(TEST_SIN, str(body))
        self.assertNotIn('7654321', str(body))

    def test_opening_the_detail_screen_records_no_disclosure(self):
        self.client.force_authenticate(self.admin)
        self.client.get(f'/api/applications/{self.application.pk}/')
        self.assertFalse(AuditEntry.objects.filter(action='identifier.revealed').exists())


class GuestApplicationRevealTests(APITestCase):
    """A claim with no account behind it.

    Its banking is encrypted against the application rather than written to a
    `BankAccount`, because there is no account to attach it to. The office still
    has to be able to read it — that is how a guest claim gets paid at all.
    """

    def setUp(self):
        self.admin = make_user(Role.ADMIN)
        from funding.test_fixtures import answers_for

        response = self.client.post('/api/guest-applications/', {
            'type': 'graduation_bursary',
            'answers': answers_for(
                'graduation_bursary',
                credential='masters_degree',
                # Optional on this form — a guest claim can be made without one
                # — so it has to be passed deliberately rather than left to the
                # fixture, which fills required fields only.
                sin=TEST_SIN,
                account_holder='Guest Claimant',
                transit_number='54321',
                institution_number='004',
                account_number='1234567',
            ),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        # A guest submission answers with a reference number and nothing else —
        # deliberately, since there is no account to show a record to.
        self.application = Application.objects.get(
            pk=int(response.data['reference'].rsplit('-', 1)[1]))

    def test_the_held_bank_details_are_readable_by_the_office(self):
        self.client.force_authenticate(self.admin)
        body = self.client.post(
            f'/api/applications/{self.application.pk}/identifiers/', {},
            format='json').data

        self.assertEqual(body['bank_account']['account_number'], '1234567')
        self.assertEqual(body['bank_account']['source'], 'held',
                         'a guest claim has no BankAccount; saying so is how the '
                         'office knows the money cannot go out automatically')

    def test_and_so_is_the_sin(self):
        self.client.force_authenticate(self.admin)
        body = self.client.post(
            f'/api/applications/{self.application.pk}/identifiers/', {},
            format='json').data
        self.assertEqual(body['identifiers'].get('sin'), TEST_SIN)

    def test_the_bank_blob_is_never_returned_as_an_identifier(self):
        """It is structured JSON, not a number. Leaving it in `identifiers`
        would put a serialised account blob on a screen built to show a SIN."""
        self.client.force_authenticate(self.admin)
        body = self.client.post(
            f'/api/applications/{self.application.pk}/identifiers/', {},
            format='json').data
        self.assertNotIn(ApplicantIdentifier.Kind.BANK_ACCOUNT, body['identifiers'])


class NothingOnFileTests(APITestCase):
    """An application that never asked for either."""

    def setUp(self):
        self.student = make_user()
        self.admin = make_user(Role.ADMIN)
        from funding.test_fixtures import answers_for

        self.client.force_authenticate(self.student)
        response = self.client.post('/api/applications/', {
            'type': 'appeal', 'answers': answers_for('appeal'),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.application = Application.objects.get(pk=response.data['id'])

    def test_it_answers_rather_than_erroring(self):
        """Nothing on file is a normal answer for an appeal, which asks for no
        SIN and no banking. A 404 here would read as a broken screen."""
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/applications/{self.application.pk}/identifiers/', {}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['identifiers'], {})
        self.assertIsNone(response.data['bank_account'])

    def test_and_records_no_disclosure_because_nothing_was_disclosed(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/applications/{self.application.pk}/identifiers/', {},
                         format='json')
        self.assertFalse(AuditEntry.objects.filter(
            action__in=('identifier.revealed', 'banking.revealed')).exists())
