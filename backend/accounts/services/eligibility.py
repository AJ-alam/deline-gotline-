"""Whether someone may apply for funding at all, and which streams they qualify for.

This used to live inside the sign-up React component: the questions, the routing
rules and the wording shown to someone turned away, all in the browser. That is
the same pattern as award rules living in the dashboard — policy the office owns,
written where nobody can test it and anybody can bypass it by calling the API
directly.

The rules are the office's, transcribed unchanged:

  PSSSP  registered under the Indian Act with Délı̨nę First Nation affiliation,
         and not currently receiving GNWT Student Financial Assistance.
  DGGR   an enrolled Délı̨nę Beneficiary. SFA does not block this one.

Two conditions stop intake regardless of the above: an unaccredited institution,
and a programme shorter than twelve weeks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The questions, in the order they are asked. Kept here rather than in the
# client so the wording, the order and the rules cannot drift apart.
QUESTIONS = (
    {
        'key': 'indian_act_registered',
        'text': 'Are you registered under the Indian Act with Délı̨nę First Nation affiliation?',
    },
    {
        'key': 'deline_beneficiary',
        'text': 'Are you an enrolled Délı̨nę Beneficiary?',
    },
    {
        'key': 'receives_sfa',
        'text': 'Are you currently receiving GNWT Student Financial Assistance (SFA)?',
        'help': 'SFA affects C-DFN funding, but not the DGGR bursary.',
    },
    {
        'key': 'lives_in_nwt',
        'text': 'Do you live in the Northwest Territories?',
        'choices': (
            ('yes', 'Yes'),
            ('moving', 'Not yet — I am moving there'),
            ('no', 'No'),
        ),
    },
    {
        'key': 'accredited_institution',
        'text': 'Will you be attending an accredited institution?',
    },
    {
        'key': 'programme_twelve_weeks',
        'text': 'Is your programme at least twelve weeks long?',
    },
)

CONTACT_DEPARTMENT = (
    'Please contact the DGG Education Department if you have questions or '
    'believe you should still qualify.'
)


@dataclass
class Outcome:
    """The decision, and what to tell the person."""

    eligible: bool
    streams: list[str] = field(default_factory=list)
    title: str = ''
    message: str = ''

    def as_dict(self) -> dict:
        return {
            'eligible': self.eligible,
            'streams': self.streams,
            'title': self.title,
            'message': self.message,
        }


def _yes(answers: dict, key: str) -> bool:
    return str(answers.get(key, '')).strip().lower() in ('yes', 'true', '1')


def missing_answers(answers: dict) -> list[str]:
    return [q['key'] for q in QUESTIONS if not str(answers.get(q['key'], '')).strip()]


def assess(answers: dict) -> Outcome:
    """Decide eligibility from the six answers."""
    missing = missing_answers(answers)
    if missing:
        return Outcome(
            eligible=False,
            title='Not yet answered',
            message='Please answer all six questions to check your eligibility.',
        )

    # ── Conditions that stop intake regardless of who is asking ──
    if not _yes(answers, 'accredited_institution'):
        return Outcome(
            eligible=False,
            title='Institution not accredited',
            message=(
                'DGG funding requires enrolment at an accredited institution. '
                + CONTACT_DEPARTMENT
            ),
        )

    if not _yes(answers, 'programme_twelve_weeks'):
        affiliated = _yes(answers, 'indian_act_registered') or _yes(answers, 'deline_beneficiary')
        return Outcome(
            eligible=False,
            title='Programme requirements not met',
            message=(
                'You are not eligible for any funding administered by the DGG '
                'Education Department. You may wish to contact the Sahtu Dene '
                'Council about other funding programmes.'
                if affiliated else
                'You do not qualify for DGG funding support at this time. '
                + CONTACT_DEPARTMENT
            ),
        )

    # ── Which streams apply ──
    registered = _yes(answers, 'indian_act_registered')
    beneficiary = _yes(answers, 'deline_beneficiary')
    on_sfa = _yes(answers, 'receives_sfa')

    streams = []
    if registered and not on_sfa:
        streams.append('psssp')
    if beneficiary:
        streams.append('dggr')

    if streams:
        return Outcome(
            eligible=True,
            streams=streams,
            title='You can apply',
            message=(
                'Based on your answers you may apply for: '
                + ', '.join(s.upper() for s in streams) + '.'
            ),
        )

    # ── Nothing applies: say precisely why ──
    if not registered and not beneficiary:
        return Outcome(
            eligible=False,
            title='Not eligible',
            message=(
                'Only persons registered under the Indian Act with Délı̨nę First '
                'Nation affiliation, or enrolled Délı̨nę Beneficiaries, are '
                'eligible. ' + CONTACT_DEPARTMENT
            ),
        )

    if registered and on_sfa and not beneficiary:
        return Outcome(
            eligible=False,
            title='Student Financial Assistance is active',
            message=(
                'Because you are currently receiving GNWT Student Financial '
                'Assistance, you do not qualify for C-DFN PSSSP or UCEPP. '
                'Because you are not a Délı̨nę Beneficiary, you are not eligible '
                'for the DGGR bursary either. ' + CONTACT_DEPARTMENT
            ),
        )

    return Outcome(
        eligible=False,
        title='Not eligible',
        message='You do not qualify for DGG funding support at this time. '
                + CONTACT_DEPARTMENT,
    )


def questions_payload() -> list[dict]:
    """The questions, described well enough for a client to render them."""
    return [
        {
            'key': q['key'],
            'text': q['text'],
            'help': q.get('help', ''),
            'choices': [
                {'value': value, 'label': label}
                for value, label in q.get('choices', (('yes', 'Yes'), ('no', 'No')))
            ],
        }
        for q in QUESTIONS
    ]
