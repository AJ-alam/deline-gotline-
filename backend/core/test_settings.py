"""What the settings file itself resolves to.

The transport tests in funding.test_smoke use override_settings to switch
production hardening back on, because the suite otherwise runs with it off. That
makes them useless for catching the hardening being disabled in the file: they
assert against a copy they supplied themselves.

These load core.settings as a module, under the conditions a real process would
see, and assert what it actually produces. Someone silencing a redirect by
setting SECURE_SSL_REDIRECT = False in the file fails here.
"""

import importlib
import os
import sys
from unittest import mock

from django.test import SimpleTestCase


def resolve(argv, **environ):
    """Load core.settings as a fresh module under the given conditions."""
    import core.settings as module

    with mock.patch.object(sys, 'argv', argv), \
            mock.patch.dict(os.environ, environ, clear=False):
        return importlib.reload(module)


PRODUCTION_ENV = {
    'SECRET_KEY': 'x' * 50,
    'DEBUG': 'False',
    'INSECURE_LOCAL': '',
}


class ProductionTransportTests(SimpleTestCase):
    """A deployed process must harden, whatever anyone edited to get local
    working."""

    def test_a_deployed_process_redirects_to_https(self):
        settings = resolve(['gunicorn'], **PRODUCTION_ENV)
        self.assertTrue(settings.SECURE_SSL_REDIRECT)

    def test_a_deployed_process_marks_cookies_secure(self):
        settings = resolve(['gunicorn'], **PRODUCTION_ENV)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)

    def test_a_deployed_process_sets_hsts(self):
        settings = resolve(['gunicorn'], **PRODUCTION_ENV)
        self.assertGreaterEqual(settings.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)

    def test_a_deployed_process_trusts_the_proxy_header(self):
        """Without this, every request behind Vercel's TLS terminator loops."""
        settings = resolve(['gunicorn'], **PRODUCTION_ENV)
        self.assertEqual(
            settings.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'),
        )

    def test_debug_alone_does_not_disable_hardening(self):
        """A copied .env with DEBUG=True must not switch production off."""
        settings = resolve(['gunicorn'], **{**PRODUCTION_ENV, 'DEBUG': 'True'})
        self.assertTrue(settings.SECURE_SSL_REDIRECT)


class LocalTransportTests(SimpleTestCase):

    def test_runserver_serves_plain_http(self):
        """runserver cannot serve the scheme a redirect would send it to."""
        settings = resolve(['manage.py', 'runserver'], **PRODUCTION_ENV)
        self.assertFalse(settings.SECURE_SSL_REDIRECT)
        self.assertEqual(settings.SECURE_HSTS_SECONDS, 0)

    def test_an_explicit_local_opt_out_serves_plain_http(self):
        settings = resolve(['gunicorn'], **{**PRODUCTION_ENV, 'INSECURE_LOCAL': '1'})
        self.assertFalse(settings.SECURE_SSL_REDIRECT)

    def test_the_test_runner_serves_plain_http(self):
        settings = resolve(['manage.py', 'test'], **PRODUCTION_ENV)
        self.assertFalse(settings.SECURE_SSL_REDIRECT)


class AlwaysOnTests(SimpleTestCase):
    """Protections that cost nothing on plain HTTP and apply everywhere."""

    def test_headers_that_do_not_depend_on_transport_are_always_set(self):
        for argv in (['gunicorn'], ['manage.py', 'runserver']):
            settings = resolve(argv, **PRODUCTION_ENV)
            self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF, argv)
            self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY', argv)
            self.assertTrue(settings.CSRF_COOKIE_HTTPONLY, argv)


class SecretKeyTests(SimpleTestCase):

    def test_a_deployed_process_refuses_the_built_in_key(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            resolve(['gunicorn'], **{**PRODUCTION_ENV, 'SECRET_KEY': ''})

    def test_a_short_key_is_refused(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            resolve(['gunicorn'], **{**PRODUCTION_ENV, 'SECRET_KEY': 'short'})


def tearDownModule():
    """Leave the settings module as the suite expects to find it."""
    resolve(['manage.py', 'test'])
