"""Email backends for local work.

Django's console backend writes the message to `sys.stdout`. On Windows that
stream encodes with the console code page — cp1252 here — and every message
this portal sends contains "Délı̨nę". The result is a UnicodeEncodeError per
message, recorded as a delivery failure, so the whole local email path fails
for a reason that has nothing to do with email.

SMTP is unaffected: it encodes its own payload as UTF-8. This is only about
printing to a terminal.
"""

import sys

from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend


def _make_stdout_utf8() -> None:
    """Ask stdout to encode UTF-8, replacing what the terminal cannot draw.

    Reconfiguring the existing stream rather than wrapping it in a new
    TextIOWrapper: a wrapper owns the buffer it is given and closes it when
    collected, so the second message to be sent found stdout already closed.
    Losing a diacritic to a question mark costs nothing; losing the message
    costs the whole point of printing it.
    """
    reconfigure = getattr(sys.stdout, 'reconfigure', None)
    if reconfigure is None:
        return
    encoding = (getattr(sys.stdout, 'encoding', '') or '').lower()
    if encoding.replace('-', '') != 'utf8':
        try:
            reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            # A stream that cannot be reconfigured — a pipe under test, say.
            # Nothing here is worth failing a send for.
            pass


class Utf8ConsoleEmailBackend(ConsoleEmailBackend):
    """The console backend, writing UTF-8 whatever the terminal prefers."""

    def __init__(self, *args, **kwargs):
        _make_stdout_utf8()
        super().__init__(*args, **kwargs)
