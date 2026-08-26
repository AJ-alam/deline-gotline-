"""The two dependency lists, held to each other.

`backend/requirements.txt` is what a developer installs; `api/requirements.txt`
is what the Vercel function installs. They are two descriptions of one thing,
which is the drift this project keeps recording — a package added to one and not
the other produces a deployment that imports something the developer's machine
happens to have and the function does not, at runtime, with no build failure to
say so.

Exact equality would be the wrong rule: two packages belong on one side only,
and both are named here so that the exception is pinned rather than assumed.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

REPO = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO / 'backend' / 'requirements.txt'
FUNCTION = REPO / 'api' / 'requirements.txt'

# gunicorn: the function is served by Vercel, there is no WSGI server to run.
# pypdf:    reads a generated approval letter back in the tests, and nothing in
#           the running application parses a PDF.
BACKEND_ONLY = {'gunicorn', 'pypdf'}


def pins(path: Path) -> dict[str, str]:
    """Package name → pinned version, ignoring comments and blank lines."""
    found = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, _, version = re.split(r'(==)', line, maxsplit=1)[::2] + ['']
        found[name.strip().lower()] = version.strip()
    return found


class RequirementsAgreeTests(SimpleTestCase):

    def setUp(self):
        self.backend = pins(BACKEND)
        self.function = pins(FUNCTION)

    def test_both_files_were_found_and_are_not_empty(self):
        """A path that stopped resolving would make every assertion below
        vacuous — two empty dicts agree perfectly."""
        self.assertGreater(len(self.backend), 5)
        self.assertGreater(len(self.function), 5)

    def test_everything_the_application_needs_is_installed_by_the_function(self):
        missing = sorted(
            set(self.backend) - set(self.function) - BACKEND_ONLY)
        self.assertEqual(missing, [], (
            f'{missing} are installed for development and not by the Vercel '
            f'function. Add them to api/requirements.txt, or name them in '
            f'BACKEND_ONLY with the reason.'))

    def test_the_function_installs_nothing_the_application_does_not_declare(self):
        extra = sorted(set(self.function) - set(self.backend))
        self.assertEqual(extra, [], (
            f'{extra} are installed in production and absent from '
            f'backend/requirements.txt, so nothing in development is running '
            f'against them.'))

    def test_the_shared_packages_are_pinned_to_the_same_versions(self):
        """Two files pinning one package differently is a production running
        code no developer has."""
        disagreements = {
            name: (self.backend[name], self.function[name])
            for name in set(self.backend) & set(self.function)
            if self.backend[name] != self.function[name]
        }
        self.assertEqual(disagreements, {})

    def test_cryptography_is_pinned_rather_than_left_to_arrive_on_its_own(self):
        """`funding.services.identifiers` imports Fernet directly. It is present
        today only because `supabase` happens to depend on it."""
        self.assertIn('cryptography', self.function)
        self.assertIn('cryptography', self.backend)
