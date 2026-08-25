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

**These six questions are the sign-up page, and the owner has asked that they
stay exactly as they are.** Three more were added here on 17 Aug 2026 to carry
§6 of the Bursary & Awards Program Procedure — whether the programme is an
upgrading programme, and whether the applicant is already funded by another
organisation or another land claim agreement — and were removed again at his
request. Two consequences follow, and they are policy gaps rather than bugs:

  * **UCEPP cannot be assigned.** §8 makes it the upgrading-programme stream and
    that is the only thing separating it from PSSSP. Nothing here asks, so no
    applicant reaches it; the office assigns it by hand or not at all.
  * **§6(A)(e) and §6(C)(d) are not enforced.** Somebody already receiving PSSSP
    or UCEPP through another organisation, or student funding under another land
    claim agreement, is not excluded by this screening.

Do not re-add the questions to close those gaps without asking first.
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


def _choices_for(question: dict) -> set[str]:
    return {value for value, _label in question.get('choices', (('yes', 'Yes'), ('no', 'No')))}


def unrecognised_answers(answers: dict) -> dict[str, str]:
    """Answers that are not one of the choices the question offered.

    `_yes` reads anything it does not recognise as a no, silently. So
    `receives_sfa: 'maybe'` — or a client that posts a number, which a
    CharField will quietly stringify — decided a funding stream by falling
    through a comparison, and looked from the outside exactly like somebody
    answering no.

    That is identity-by-display-string again in miniature: a value nobody
    offered, meaning something nobody chose. Both doors that take these answers
    check this, because a rule enforced at one of two entrances is not enforced.
    """
    problems = {}
    for question in QUESTIONS:
        key = question['key']
        if key not in answers:
            continue
        given = str(answers[key]).strip().lower()
        allowed = _choices_for(question)
        if given and given not in allowed:
            problems[key] = (
                f'{answers[key]!r} is not one of the answers to this question. '
                f'Expected one of: {", ".join(sorted(allowed))}.')
    return problems


def streams_for(answers: dict) -> list[str]:
    """Every stream these answers qualify for, best first.

    Split out of `assess` because the sign-up path needs exactly this and
    nothing else: it saves the result on the account as the person's funding
    tags, which is what `funding.services.streams` reads back per application.

    PSSSP before DGGR. The order is what
    `funding.services.streams.for_application` reads to pick an application's
    primary stream, and the federal programme that funds tuition and a living
    allowance has to come before the one that only tops it up.

    UCEPP is never produced here — see the note at the top of this module.
    """
    registered = _yes(answers, 'indian_act_registered')
    beneficiary = _yes(answers, 'deline_beneficiary')
    on_sfa = _yes(answers, 'receives_sfa')

    streams = []
    if registered and not on_sfa:
        streams.append('psssp')
    if beneficiary:
        streams.append('dggr')
    return streams


def assess(answers: dict) -> Outcome:
    """Decide eligibility from the screening answers."""
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
    streams = streams_for(answers)

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
    registered = _yes(answers, 'indian_act_registered')
    beneficiary = _yes(answers, 'deline_beneficiary')
    on_sfa = _yes(answers, 'receives_sfa')

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
