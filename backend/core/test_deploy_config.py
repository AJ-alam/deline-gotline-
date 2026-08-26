"""Settings a deployment sets that the code must actually be able to read.

Every fault this file guards has the same shape: an environment variable set on
the host, believed to be configured, and invisible to Django because nothing in
`settings.py` declared it. That is not a configuration mistake anybody can see —
the dashboard shows the variable, the deploy succeeds, and the failure arrives
later as a refusal on a form somebody was filling in.

`FIELD_ENCRYPTION_KEY` was in exactly that state: `identifiers._key()` reads it
off the settings object, `settings.py` never assigned it, and a production
process would therefore have refused every application asking for a SIN however
carefully the key was set.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from funding.services import identifiers

# What Fernet wants: 32 bytes, urlsafe-base64. Not a real key.
A_KEY = 'ZHVtbXkta2V5LWZvci10ZXN0cy0wMTIzNDU2Nzg5YWI='


class FieldEncryptionKeyTests(SimpleTestCase):
    """The key that makes a stored SIN readable again."""

    def test_settings_declares_it_so_the_environment_can_reach_it(self):
        """The guard against the original fault.

        Deleting the assignment from `settings.py` leaves `getattr` falling back
        to its default forever, and every other test still passes because local
        and test runs derive a key on purpose.
        """
        self.assertTrue(hasattr(settings, 'FIELD_ENCRYPTION_KEY'))

    @override_settings(FIELD_ENCRYPTION_KEY=A_KEY)
    def test_a_configured_key_is_the_one_used(self):
        self.assertEqual(identifiers._key(), A_KEY.encode())

    @override_settings(FIELD_ENCRYPTION_KEY='', DEBUG=False, TESTING=False)
    def test_a_deployed_process_refuses_to_derive_one(self):
        """Deriving from SECRET_KEY means rotating SECRET_KEY silently makes
        every stored number unreadable."""
        with self.assertRaises(ImproperlyConfigured):
            identifiers._key()

    @override_settings(FIELD_ENCRYPTION_KEY='', DEBUG=True)
    def test_local_work_still_needs_no_configuration(self):
        self.assertTrue(identifiers._key())


class TaskTokenTests(SimpleTestCase):
    """The secret the outbox drainer is behind."""

    def test_settings_declares_it(self):
        self.assertTrue(hasattr(settings, 'TASK_TOKEN'))

    def test_it_defaults_to_empty_rather_than_to_something_guessable(self):
        """An endpoint that sends the office's mail must not ship with a
        default secret. Empty is refused by the view; a default would be a
        published password."""
        with override_settings():
            del settings.TASK_TOKEN
            self.assertEqual(getattr(settings, 'TASK_TOKEN', ''), '')
