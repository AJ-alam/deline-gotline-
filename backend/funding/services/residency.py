"""Whether an application contradicts itself about where the applicant lives.

`residency_flag` existed from the first migration with two readers — the
application detail screen and the staff dashboard's "needs a look" count — and
**no writer at all**, so the count could only ever be zero and the screen could
only ever say nothing. It was recorded as an open item because implementing it
needs a residency policy, and nobody had stated one.

The office has now stated it: *a student who says they do not live in the
Northwest Territories, and then gives an address in the Northwest Territories,
should be flagged.* That is the rule implemented here and nothing more.

**Only that direction.** The screening also offers "Not yet — I am moving
there", and someone moving to the NWT who gives an NWT address is not
contradicting themselves, they are describing the move. The reverse case —
saying yes and giving an address elsewhere — is deliberately not flagged: a
student may be studying away, or give a parent's address, and a flag that fires
on ordinary circumstances is a queue nobody can clear, which is how
`residency_flag` came to be ignored in the first place.

The flag is a sentence for a reviewer to act on, not a code. Nothing prices on
it, nothing blocks on it: it says "these two answers disagree, look at it".
"""

from __future__ import annotations

import re

# How the Northwest Territories is written on a form by somebody who lives
# there. Matched on the whole field rather than as a substring, because "NT"
# inside a word — Ontario, Nunavut, Kent — is not a territory.
NWT_PROVINCE = {
    'nt', 'n.t.', 'nwt', 'n.w.t.', 'nw t',
    'northwest territories', 'north west territories',
    'northwest territory', 'territoires du nord-ouest',
}

# The postal districts the Northwest Territories actually uses. X0A–X0C are
# Nunavut and are deliberately absent: a flag that fires on a Nunavut address
# is a flag telling a reviewer something untrue.
NWT_POSTAL_PREFIXES = ('x0e', 'x0g', 'x1a')

MESSAGE = (
    'The screening says this applicant does not live in the Northwest '
    'Territories, but the address on this application is in the Northwest '
    'Territories.'
)


def _normalise(value) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip().lower()


def looks_like_nwt(province='', postal_code='') -> bool:
    """Whether an address is in the Northwest Territories.

    The province decides it. The postal code is a second chance for a form
    where the province was left blank or written as something this does not
    recognise — an address is not "not in the NWT" merely because somebody
    spelled the territory a way nobody anticipated.
    """
    if _normalise(province) in NWT_PROVINCE:
        return True
    code = _normalise(postal_code).replace(' ', '')
    return bool(code) and code.startswith(NWT_POSTAL_PREFIXES)


def _address_of(application) -> tuple[str, str]:
    """The address this application gives, or the one on the account.

    The application's own answers first: that is the address the applicant put
    on this form, which is what the office is comparing against. Only two forms
    ask for one, so everything else falls back to the profile — otherwise the
    check would silently do nothing on eight of the ten types.
    """
    answers = application.answers or {}
    province = (answers.get('province') or '').strip()
    postal = (answers.get('postal_code') or '').strip()
    if province or postal:
        return province, postal

    student = application.student
    if student is None:
        return '', ''
    return (getattr(student, 'province', '') or '',
            getattr(student, 'postal_code', '') or '')


def _declared_not_resident(application) -> bool:
    """Whether the applicant said they do not live in the NWT.

    Read from the screening answers saved on the account. Strictly 'no': a
    blank answer is not a denial, and 'moving' is the opposite of one.
    """
    student = application.student
    if student is None:
        return False
    answers = getattr(student, 'eligibility_answers', None) or {}
    return _normalise(answers.get('lives_in_nwt')) == 'no'


def assess(application) -> str:
    """The flag this application should carry. Empty when there is no conflict."""
    if not _declared_not_resident(application):
        return ''
    province, postal = _address_of(application)
    if not looks_like_nwt(province, postal):
        return ''
    return MESSAGE


def stamp(application) -> str:
    """Work out the flag and store it, returning what was stored.

    Saved rather than derived on read because it is shown on a list of many
    applications and counted on the dashboard, and because the office may
    correct an address later — re-stamped on an amendment and on a revision, so
    the flag always describes the answers the application currently holds.
    Deriving it on read would make the staff queue a query per row.
    """
    flag = assess(application)
    if application.residency_flag != flag:
        application.residency_flag = flag
        application.save(update_fields=['residency_flag', 'updated_at'])
    return flag
