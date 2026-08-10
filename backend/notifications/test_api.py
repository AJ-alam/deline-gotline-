"""Reading notices in the portal.

The property that matters most: a person sees their own and no one else's.
Everything else is presentation.
"""

import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import Notification

_counter = itertools.count(1)


def make_user(role=Role.STUDENT):
    return User.objects.create_user(
        f'n{next(_counter)}@test.com', 'pw12345678',
        first_name='Test', last_name=f'P{next(_counter)}', role=role,
    )


def notice(user, title='Application received', is_read=False, **kwargs):
    return Notification.objects.create(
        user=user, title=title, message='Something happened.',
        is_read=is_read, link='/applications/1', **kwargs,
    )


class IsolationTests(TestCase):

    def setUp(self):
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.person = make_user()
        self.other = make_user()

    def test_a_person_sees_only_their_own(self):
        notice(self.person, 'Mine')
        notice(self.other, 'Theirs')

        self.client.force_authenticate(self.person)
        response = self.client.get('/api/notifications/')

        titles = [row['title'] for row in response.data['results']]
        self.assertEqual(titles, ['Mine'])

    def test_someone_elses_notice_cannot_be_marked_read(self):
        theirs = notice(self.other)
        self.client.force_authenticate(self.person)

        response = self.client.post('/api/notifications/', {'ids': [theirs.id]},
                                    format='json')

        self.assertEqual(response.data['marked'], 0)
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_marking_everything_read_does_not_reach_anyone_else(self):
        notice(self.person)
        theirs = notice(self.other)

        self.client.force_authenticate(self.person)
        self.client.post('/api/notifications/', {}, format='json')

        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_anonymous_requests_are_rejected(self):
        self.assertEqual(self.client.get('/api/notifications/').status_code, 401)


class ReadingTests(TestCase):

    def setUp(self):
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.person = make_user()
        self.client.force_authenticate(self.person)

    def test_the_unread_count_is_returned_alongside_the_list(self):
        notice(self.person)
        notice(self.person)
        notice(self.person, is_read=True)

        response = self.client.get('/api/notifications/')
        self.assertEqual(response.data['unread'], 2)
        self.assertEqual(len(response.data['results']), 3)

    def test_the_unread_count_is_of_everything_not_just_this_page(self):
        """Filtering the list must not change the number shown on the bell."""
        for _ in range(3):
            notice(self.person)
        notice(self.person, is_read=True)

        response = self.client.get('/api/notifications/?unread=true')
        self.assertEqual(response.data['unread'], 3)
        self.assertEqual(len(response.data['results']), 3)

    def test_newest_appear_first(self):
        notice(self.person, 'Older')
        notice(self.person, 'Newer')

        titles = [row['title'] for row in self.client.get('/api/notifications/').data['results']]
        self.assertEqual(titles[0], 'Newer')

    def test_a_long_history_is_not_all_sent_to_the_browser(self):
        for _ in range(60):
            notice(self.person)
        response = self.client.get('/api/notifications/')
        self.assertEqual(len(response.data['results']), 50)
        self.assertEqual(response.data['unread'], 60)

    def test_a_notice_carries_where_it_points(self):
        notice(self.person)
        row = self.client.get('/api/notifications/').data['results'][0]
        self.assertEqual(row['link'], '/applications/1')
        self.assertIn('title', row)
        self.assertIn('created_at', row)

    def test_nothing_to_show_reads_as_empty_not_as_an_error(self):
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['unread'], 0)


class MarkingTests(TestCase):

    def setUp(self):
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')
        self.person = make_user()
        self.client.force_authenticate(self.person)

    def test_specific_notices_can_be_marked_read(self):
        first, second = notice(self.person), notice(self.person)

        response = self.client.post('/api/notifications/', {'ids': [first.id]},
                                    format='json')

        self.assertEqual(response.data['marked'], 1)
        self.assertEqual(response.data['unread'], 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertFalse(second.is_read)

    def test_everything_can_be_marked_read_at_once(self):
        for _ in range(3):
            notice(self.person)

        response = self.client.post('/api/notifications/', {}, format='json')

        self.assertEqual(response.data['marked'], 3)
        self.assertEqual(response.data['unread'], 0)

    def test_marking_something_already_read_changes_nothing(self):
        read = notice(self.person, is_read=True)
        response = self.client.post('/api/notifications/', {'ids': [read.id]},
                                    format='json')
        self.assertEqual(response.data['marked'], 0)

    def test_a_malformed_request_says_what_was_expected(self):
        response = self.client.post('/api/notifications/', {'ids': 'not-a-list'},
                                    format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('ids', response.data)
