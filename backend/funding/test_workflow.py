"""Application status derived from its event history."""

import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, ApplicationType, FundingStream,
)
from funding.services.workflow import (
    ALLOWED_ACTIONS, InvalidTransition, can, derive_status, record,
    status_is_consistent,
)

Action = ApplicationEvent.Action
User = get_user_model()
_counter = itertools.count(1)


def make_application(**kwargs):
    student = User.objects.create_user(
        email=f'w{next(_counter)}@test.com', password='pw123456',
        first_name='Test', last_name='Student', role='student',
    )
    defaults = dict(
        type=ApplicationType.ADMISSION, stream=FundingStream.PSSSP,
        schema_slug='admission', answers={},
        status=ApplicationStatus.SUBMITTED,
    )
    defaults.update(kwargs)
    return Application.objects.create(student=student, **defaults)


def make_staff(role='support_worker'):
    return User.objects.create_user(
        email=f'staff{next(_counter)}@test.com', password='pw123456',
        first_name='Test', last_name='Staff', role=role,
    )


class TransitionTests(TestCase):

    def setUp(self):
        self.staff = make_staff()

    def test_recording_an_event_moves_the_status(self):
        app = make_application()
        record(app, Action.REVIEWED, self.staff)
        app.refresh_from_db()
        self.assertEqual(app.status, ApplicationStatus.UNDER_REVIEW)

    def test_the_full_happy_path(self):
        app = make_application()
        for action, expected in [
            (Action.REVIEWED, ApplicationStatus.UNDER_REVIEW),
            (Action.FORWARDED, ApplicationStatus.AWAITING_DECISION),
            (Action.APPROVED, ApplicationStatus.APPROVED),
            (Action.SENT_TO_FINANCE, ApplicationStatus.SENT_TO_FINANCE),
        ]:
            record(app, action, self.staff)
            app.refresh_from_db()
            self.assertEqual(app.status, expected, action)

    def test_an_invalid_transition_is_refused(self):
        """Approving straight from submitted skips review entirely."""
        app = make_application()
        with self.assertRaises(InvalidTransition):
            record(app, Action.APPROVED, self.staff)

    def test_a_refused_transition_writes_nothing(self):
        app = make_application()
        with self.assertRaises(InvalidTransition):
            record(app, Action.APPROVED, self.staff)
        app.refresh_from_db()
        self.assertEqual(app.status, ApplicationStatus.SUBMITTED)
        self.assertFalse(app.events.exists())

    def test_final_states_accept_nothing_further(self):
        app = make_application()
        record(app, Action.REVIEWED, self.staff)
        record(app, Action.DECLINED, self.staff)
        for action in Action:
            with self.assertRaises(InvalidTransition, msg=action):
                record(app, action, self.staff)

    def test_the_error_says_what_is_allowed_instead(self):
        app = make_application()
        with self.assertRaises(InvalidTransition) as ctx:
            record(app, Action.APPROVED, self.staff)
        message = str(ctx.exception)
        self.assertIn('submitted', message.lower())
        self.assertIn('reviewed', message)

    def test_information_can_be_requested_and_supplied(self):
        app = make_application()
        record(app, Action.REVIEWED, self.staff)
        record(app, Action.INFO_REQUESTED, self.staff)
        app.refresh_from_db()
        self.assertEqual(app.status, ApplicationStatus.INFO_REQUESTED)

        record(app, Action.INFO_PROVIDED, self.staff)
        app.refresh_from_db()
        self.assertEqual(app.status, ApplicationStatus.UNDER_REVIEW)

    def test_a_director_can_send_it_back_for_more_information(self):
        app = make_application()
        record(app, Action.REVIEWED, self.staff)
        record(app, Action.FORWARDED, self.staff)
        record(app, Action.INFO_REQUESTED, self.staff)
        app.refresh_from_db()
        self.assertEqual(app.status, ApplicationStatus.INFO_REQUESTED)

    def test_can_reports_what_record_will_accept(self):
        app = make_application()
        self.assertTrue(can(app, Action.REVIEWED))
        self.assertFalse(can(app, Action.APPROVED))


class HistoryTests(TestCase):

    def setUp(self):
        self.staff = make_staff()

    def test_every_transition_leaves_an_event(self):
        app = make_application()
        record(app, Action.REVIEWED, self.staff, note='Checked documents')
        record(app, Action.FORWARDED, self.staff)

        events = list(app.events.all())
        self.assertEqual([e.action for e in events], ['reviewed', 'forwarded'])
        self.assertEqual(events[0].note, 'Checked documents')
        self.assertEqual(events[0].actor, self.staff)

    def test_status_always_matches_the_history(self):
        app = make_application()
        record(app, Action.REVIEWED, self.staff)
        record(app, Action.FORWARDED, self.staff)
        record(app, Action.APPROVED, self.staff)
        app.refresh_from_db()
        self.assertTrue(status_is_consistent(app))

    def test_drift_is_detectable_when_something_bypasses_the_workflow(self):
        """The failure mode the old model had permanently."""
        app = make_application()
        record(app, Action.REVIEWED, self.staff)

        Application.objects.filter(pk=app.pk).update(status=ApplicationStatus.APPROVED)
        app.refresh_from_db()
        self.assertFalse(status_is_consistent(app))

    def test_deriving_replays_a_history_to_the_same_status(self):
        app = make_application()
        for action in (Action.REVIEWED, Action.FORWARDED, Action.APPROVED):
            record(app, action, self.staff)
        app.refresh_from_db()
        self.assertEqual(derive_status(app.events.all()), app.status)

    def test_an_empty_history_derives_to_draft(self):
        self.assertEqual(derive_status([]), ApplicationStatus.DRAFT)


class TransitionTableTests(TestCase):
    """The table itself has to be coherent."""

    def test_every_status_declares_its_allowed_actions(self):
        for status in ApplicationStatus:
            self.assertIn(status, ALLOWED_ACTIONS, status)

    def test_every_reachable_status_can_be_reached(self):
        reachable = {ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED}
        from funding.services.workflow import RESULTING_STATUS
        for actions in ALLOWED_ACTIONS.values():
            for action in actions:
                reachable.add(RESULTING_STATUS[action])
        for status in ApplicationStatus:
            self.assertIn(status, reachable, f'{status} is unreachable')

    def test_no_action_leads_out_of_a_final_state(self):
        for final in (ApplicationStatus.DECLINED, ApplicationStatus.SENT_TO_FINANCE):
            self.assertEqual(ALLOWED_ACTIONS[final], set(), final)


class DeterministicOrderTests(TestCase):
    """A history must fold to one status, whatever the storage returns.

    auto_now_add timestamps can tie, and an ambiguous order would let the same
    events derive different statuses on different reads.
    """

    def test_events_sharing_a_timestamp_keep_a_stable_order(self):
        from django.utils import timezone

        app = make_application()
        moment = timezone.now()
        for action in (Action.REVIEWED, Action.FORWARDED, Action.APPROVED):
            event = ApplicationEvent.objects.create(application=app, action=action)
            ApplicationEvent.objects.filter(pk=event.pk).update(occurred_at=moment)

        derived = {derive_status(app.events.all()) for _ in range(5)}
        self.assertEqual(derived, {ApplicationStatus.APPROVED})

    def test_the_last_event_wins_regardless_of_insertion_time(self):
        app = make_application()
        record(app, Action.REVIEWED, make_staff())
        record(app, Action.INFO_REQUESTED, make_staff())
        self.assertEqual(
            derive_status(app.events.all()), ApplicationStatus.INFO_REQUESTED,
        )
