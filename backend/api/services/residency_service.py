"""
Residency consistency checks.

Students declare NWT residency at sign-up (eligibility Q4 → province_of_residence).
The address they later give on their profile or on a form is independent data, so
the two can contradict each other — e.g. "No, I do not live in the NWT" together
with a Deline mailing address and an X0E postal code. Those cases must be surfaced
to staff instead of silently passing review.
"""

import logging

logger = logging.getLogger(__name__)

# Declared answers that mean "I am not an NWT resident".
NON_NWT_DECLARATIONS = ('outside', 'other')

# Territory / province text that means NWT.
_NWT_PROVINCE_TOKENS = {
    'nt', 'nwt', 'n.w.t', 'n.w.t.', 'northwest territories',
    'north west territories', 'northwest territory', 'territoires du nord-ouest',
}

# Province / territory text that is definitely not the NWT. Nunavut and Yukon are
# included: they are northern, but they are not the NWT.
_OTHER_PROVINCE_NAMES = {
    'ab': 'Alberta', 'alberta': 'Alberta',
    'bc': 'British Columbia', 'b.c': 'British Columbia',
    'british columbia': 'British Columbia',
    'mb': 'Manitoba', 'manitoba': 'Manitoba',
    'nb': 'New Brunswick', 'new brunswick': 'New Brunswick',
    'nl': 'Newfoundland and Labrador', 'nfld': 'Newfoundland and Labrador',
    'newfoundland': 'Newfoundland and Labrador',
    'newfoundland and labrador': 'Newfoundland and Labrador',
    'ns': 'Nova Scotia', 'nova scotia': 'Nova Scotia',
    'on': 'Ontario', 'ont': 'Ontario', 'ontario': 'Ontario',
    'pe': 'Prince Edward Island', 'pei': 'Prince Edward Island',
    'prince edward island': 'Prince Edward Island',
    'qc': 'Quebec', 'que': 'Quebec', 'quebec': 'Quebec', 'québec': 'Quebec',
    'sk': 'Saskatchewan', 'sask': 'Saskatchewan', 'saskatchewan': 'Saskatchewan',
    'nu': 'Nunavut', 'nunavut': 'Nunavut',
    'yt': 'Yukon', 'yk': 'Yukon', 'yukon': 'Yukon',
}

# Canada Post forward sortation areas assigned to the NWT.
# X0A/X0B/X0C are Nunavut and X0Y is Yukon — deliberately excluded.
_NWT_POSTAL_PREFIXES = ('X0E', 'X0G', 'X1A')

# NWT communities. Used only when province/postal code give no signal, so a
# same-named town elsewhere is possible — the result is a flag for review, not
# an automatic rejection.
_NWT_COMMUNITIES = {
    'deline', 'délı̨nę', 'delįne', 'fort franklin',
    'yellowknife', 'hay river', 'inuvik', 'fort smith', 'behchoko', 'behchokò',
    'norman wells', 'fort simpson', 'tulita', 'fort good hope', 'colville lake',
    'aklavik', 'tuktoyaktuk', 'fort mcpherson', 'tsiigehtchic', 'ulukhaktok',
    'paulatuk', 'sachs harbour', 'fort providence', 'fort resolution',
    'fort liard', 'gameti', 'gamètì', 'wekweeti', 'wekweètì', 'whati', 'whatì',
    'lutselk\'e', 'lutsel k\'e', 'enterprise', 'kakisa', 'jean marie river',
    'nahanni butte', 'sambaa k\'e', 'trout lake', 'wrigley', 'dettah', 'ndilo',
}


def _norm(value):
    return (value or '').strip().lower()


def _postal_prefix(postal_code):
    """First three characters of a postal code, uppercased, spaces stripped."""
    cleaned = (postal_code or '').replace(' ', '').replace('-', '').upper()
    return cleaned[:3]


def nwt_address_signals(province=None, town_city=None, postal_code=None, mailing_address=None):
    """
    Return the list of reasons the supplied address looks like an NWT address.
    Empty list means nothing in the address points at the NWT.
    """
    signals = []

    province_norm = _norm(province).rstrip('.')
    if province_norm in _NWT_PROVINCE_TOKENS:
        signals.append(f"territory/province entered as '{province.strip()}'")

    prefix = _postal_prefix(postal_code)
    if prefix in _NWT_POSTAL_PREFIXES:
        signals.append(f"postal code '{postal_code.strip()}' is in the NWT ({prefix})")

    town_norm = _norm(town_city)
    if town_norm in _NWT_COMMUNITIES:
        signals.append(f"town/city '{town_city.strip()}' is an NWT community")

    # Only fall back to scanning the free-text address when the structured
    # fields said nothing — it is the least reliable source.
    if not signals:
        address_norm = _norm(mailing_address)
        if address_norm:
            for community in _NWT_COMMUNITIES:
                if community in address_norm:
                    signals.append(f"mailing address mentions the NWT community '{community}'")
                    break
            else:
                for token in ('northwest territories', ' nwt', 'nwt,', ' n.w.t'):
                    if token in address_norm:
                        signals.append("mailing address mentions the Northwest Territories")
                        break

    return signals


def non_nwt_address_signals(province=None, postal_code=None):
    """
    Reasons the supplied address is clearly outside the NWT.

    Only the two unambiguous fields are used. Town names and free text are not:
    a student can write a school address, a parent's address, or a community name
    that exists in more than one province, and those guesses are not worth a flag.
    """
    signals = []

    province_norm = _norm(province).rstrip('.')
    named = _OTHER_PROVINCE_NAMES.get(province_norm)
    if named:
        signals.append(f"territory/province entered as '{province.strip()}' ({named})")

    prefix = _postal_prefix(postal_code)
    if prefix and len(prefix) == 3 and prefix[0].isalpha() and prefix[1].isdigit():
        if prefix not in _NWT_POSTAL_PREFIXES and prefix[0] != 'X':
            signals.append(f"postal code '{postal_code.strip()}' is not an NWT postal code")

    return signals


def check_residency_mismatch(declared_province, province=None, town_city=None,
                             postal_code=None, mailing_address=None,
                             institution_location=None):
    """
    Compare a student's declared residency against the address they supplied.

    Two contradictions are reported:
      'declared_non_resident' — said they do not live in the NWT, gave an NWT address.
      'declared_resident'     — said they are an NWT resident, gave an address that is
                                clearly outside the NWT. Suppressed when the address
                                matches where they study, since students away at school
                                keep their NWT residency.

    Args:
        declared_province: user.province_of_residence ('nwt' / 'outside' / 'other')
        province, town_city, postal_code, mailing_address: address as entered
        institution_location: where the student attends school, when known

    Returns:
        dict with 'kind', 'declared', 'signals' and 'message', or None when the
        declaration and the address agree.
    """
    declared = _norm(declared_province)

    if declared in NON_NWT_DECLARATIONS:
        signals = nwt_address_signals(
            province=province,
            town_city=town_city,
            postal_code=postal_code,
            mailing_address=mailing_address,
        )
        if not signals:
            return None
        return {
            'kind': 'declared_non_resident',
            'declared': declared_province,
            'signals': signals,
            'message': (
                "Residency mismatch: student declared they are NOT an NWT resident, "
                "but the address on file looks like an NWT address (" + '; '.join(signals) + "). "
                "Confirm residency before approving — SFA/PSSSP routing depends on it."
            ),
        }

    if declared == 'nwt':
        signals = non_nwt_address_signals(province=province, postal_code=postal_code)
        if not signals:
            return None
        # Studying away from home does not end NWT residency — if the address is
        # where the institution is, it explains itself and no flag is raised.
        location_norm = _norm(institution_location)
        province_norm = _norm(province).rstrip('.')
        if location_norm:
            named = _OTHER_PROVINCE_NAMES.get(province_norm, '')
            town_norm = _norm(town_city)
            if ((named and named.lower() in location_norm)
                    or (province_norm and province_norm in location_norm)
                    or (town_norm and town_norm in location_norm)):
                return None
        return {
            'kind': 'declared_resident',
            'declared': declared_province,
            'signals': signals,
            'message': (
                "Residency review: student declared they ARE an NWT resident, but the "
                "address on file is outside the NWT (" + '; '.join(signals) + "). "
                "This is expected for a student living at school — confirm the home "
                "address before treating them as NWT-resident for SFA purposes."
            ),
        }

    return None


def evaluate_submission(submission):
    """
    Run the residency comparison for one submission, reading the address from the
    submission's own answers and falling back to the student's profile.
    """
    student = submission.student
    if not student:
        return None

    answers = {
        (a.field.label or '').strip().lower(): (a.answer_text or '')
        for a in submission.answers.select_related('field').all() if a.field
    }

    def answer(*labels):
        for label in labels:
            value = answers.get(label)
            if value:
                return value
        return None

    profile = getattr(student, 'profile', None)

    return check_residency_mismatch(
        student.province_of_residence,
        province=answer('province', 'territory / province', 'territory/province', 'province/territory'),
        town_city=answer('city', 'town / city', 'town/city', 'town') or getattr(profile, 'town_city', None),
        postal_code=answer('postal code', 'postalcode') or getattr(profile, 'postal_code', None),
        mailing_address=answer('address', 'current address', 'mailing address') or student.mailing_address,
        institution_location=answer('institution location', 'school location') or student.institution_location,
    )


def apply_to_submission(submission, notify=True):
    """
    Store the residency verdict on the submission and, for a newly raised flag,
    tell staff. Returns the mismatch dict (or None) so callers can report on it.
    """
    mismatch = evaluate_submission(submission)
    new_flag = mismatch['message'] if mismatch else None

    if new_flag != submission.residency_flag:
        submission.residency_flag = new_flag
        submission.save(update_fields=['residency_flag'])
        if mismatch and notify:
            notify_staff_of_mismatch(
                submission.student, mismatch, link=f"/staff/applications/{submission.id}"
            )

    return mismatch


NOTIFICATION_TITLE = "Residency Declaration Mismatch"


def notify_staff_of_mismatch(student, mismatch, link=None):
    """
    Send the mismatch to every admin/SSW/director reviewer. Never raises.

    Profile edits can re-trigger the same mismatch on every save, so an identical
    message that is still unread is not sent again.
    """
    if not mismatch:
        return
    try:
        from django.contrib.auth import get_user_model
        from notifications.models import Notification
        from notifications.utils import create_notification

        User = get_user_model()
        who = getattr(student, 'full_name', None) or getattr(student, 'email', 'A student')
        message = f"{who} ({getattr(student, 'email', '—')}): {mismatch['message']}"

        for staff in User.objects.filter(role__in=('admin', 'ssw', 'director')):
            already_pending = Notification.objects.filter(
                user=staff, title=NOTIFICATION_TITLE, message=message, is_read=False,
            ).exists()
            if already_pending:
                continue
            create_notification(staff, NOTIFICATION_TITLE, message, link=link)
    except Exception:
        logger.exception("Failed to notify staff of residency mismatch")
