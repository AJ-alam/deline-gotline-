"""The routing file the deployment is actually served by.

`vercel.json` is not imported by anything, not type-checked, and not exercised
by a single one of the 1200 tests — so it is the one file where being wrong
costs nothing until a person clicks a link. It was wrong from the commit that
introduced it.

`cleanUrls: true` redirects any `.html` path to its extensionless form, so the
SPA fallback rewrite `/(.*) -> /index.html` resolved to a 308 to `/` rather
than to the document. Vercel answered `NOT_FOUND` for **every** deep link:
/login, /dashboard, and the one that mattered — the registrar's
/enrolment/<token>.

It survived because of who hits a deep link. Staff and students load `/` and
navigate inside the router, where no request reaches Vercel at all. The
registrar arrives from an email, cold, on a path — and is the one user with no
account, no other route in, and no way to report the failure back. Tuition is
funded against their figure, so the whole tuition path ran through the single
URL nobody could see was broken.

These tests read the file rather than describe it. A comment saying "do not
enable cleanUrls" is a comment somebody deletes.
"""

import json
from pathlib import Path

from django.test import SimpleTestCase

VERCEL_JSON = Path(__file__).resolve().parent.parent.parent / 'vercel.json'

# What the browser must receive for a path the router owns: the app's document,
# so React can read the path and render the route.
SPA_FALLBACK = '/(.*)'


def config() -> dict:
    return json.loads(VERCEL_JSON.read_text(encoding='utf-8'))


class SpaFallbackTests(SimpleTestCase):
    """A deep link must reach the application."""

    def test_the_file_is_where_the_deployment_expects_it(self):
        """A path assertion, so the rest of this file cannot pass vacuously by
        reading a file that has moved."""
        self.assertTrue(VERCEL_JSON.is_file(), f'{VERCEL_JSON} is missing.')

    def test_there_is_a_catch_all_rewrite_to_the_document(self):
        rewrites = config().get('rewrites', [])
        fallback = [r for r in rewrites if r.get('source') == SPA_FALLBACK]

        self.assertEqual(len(fallback), 1,
                         'Exactly one catch-all rewrite serves the SPA.')
        self.assertTrue(fallback[0]['destination'].endswith('index.html'))

    def test_the_catch_all_is_last(self):
        """It matches everything, so anything after it is unreachable — the
        /api, /admin and /static rewrites included, which would hand the
        registrar's form the Django application instead."""
        sources = [r.get('source') for r in config().get('rewrites', [])]

        self.assertEqual(sources[-1], SPA_FALLBACK)

    def test_clean_urls_is_not_enabled_beside_an_html_destination(self):
        """The fault itself.

        `cleanUrls` 308-redirects `/index.html` to `/`, so the fallback resolves
        to a redirect rather than the document and Vercel answers NOT_FOUND for
        every path the router owns. Asserted as the *combination* rather than
        banning `cleanUrls` outright: it is a legitimate option, and it is only
        this pairing that breaks — a flat ban is a rule whose reason is lost the
        first time somebody wants the feature.
        """
        settings = config()
        rewrites = settings.get('rewrites', [])
        html_destinations = [r for r in rewrites
                             if str(r.get('destination', '')).endswith('.html')]

        if settings.get('cleanUrls') and html_destinations:
            self.fail(
                'cleanUrls redirects .html paths away, so a rewrite to '
                f'{html_destinations[0]["destination"]} resolves to a 308 and '
                'every deep link 404s — including the registrar enrolment link.'
            )

    def test_the_api_is_not_swallowed_by_the_catch_all(self):
        """/api must reach Django. Ordering does this today; asserting it means
        a reordering that breaks it fails here rather than in production."""
        rewrites = config().get('rewrites', [])
        sources = [r.get('source') for r in rewrites]

        self.assertLess(sources.index('/api/(.*)'), sources.index(SPA_FALLBACK))
