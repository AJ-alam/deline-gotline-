"""Which pot an application is funded from.

The stream used to be a dropdown on the application form, sent by the client
and stored as given. That is the same mistake as the eligibility rules living
in the sign-up component: it is the office's policy, decided by facts the
office already holds, and a client that chooses it can choose wrongly — either
by mistake, or by picking a stream the applicant does not qualify for.

It matters to the money. Tuition and living-allowance rules are gated on
`applies_to_streams`, so the stream decides which caps and rates are applied.

The rules are the sign-up screening's, and they are not restated here. The
streams a person qualified for are saved on the account at registration
(`User.eligible_streams`), because two of the answers behind them — whether the
programme is an upgrading programme, and whether the person is funded by another
organisation or another land claim agreement — have no column to reconstruct
them from. Re-deriving from `is_indian_act_registered` and
`is_deline_beneficiary` gave a different, quietly wrong answer: no applicant
could ever land in UCEPP, and neither exclusion was honoured.

What this module still decides per application is the one thing that genuinely
changes every term: SFA. It is asked again on each form whose award depends on
it, and a yes withdraws both C-DFN streams for that application without touching
the account.
"""

from __future__ import annotations

from funding.models import ApplicationType, FundingStream

# Awards that come from the government's own bursary funds whatever the
# applicant's C-DFN status. The guest path already forces these to DGGR; this
# keeps the signed-in path saying the same thing.
ALWAYS_DGGR = (
    ApplicationType.GRADUATION_BURSARY,
    ApplicationType.PRACTICUM,
    ApplicationType.HARDSHIP_BURSARY,
    ApplicationType.EMERGENCY_RELIEF,
    ApplicationType.ACADEMIC_SCHOLARSHIP,
)


class NoStreamAvailable(Exception):
    """This person cannot be funded from any stream.

    Registration is gated on eligibility, so an account should always qualify
    for something. Reaching this means the account predates the gate or its
    circumstances have since changed — either way the office has to look at it
    rather than the portal guessing.
    """


def receives_sfa(answers: dict | None = None) -> bool:
    """Whether GNWT Student Financial Assistance is in play.

    Read from the application, never from the person. SFA status changes every
    term, so it is not a fact about someone that can be recorded once at
    sign-up — and every application type whose award depends on the stream asks
    the question directly.
    """
    answers = answers or {}
    value = (answers or {}).get('receives_sfa')
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('true', 'yes', 'y', '1', 'on')


# The two C-DFN streams. Both are withdrawn by an SFA answer of yes, and DGGR
# is not — §7 of the policy is explicit that a student may hold a C-DFN bursary
# and a DGGR bursary at the same time.
SFA_EXCLUDES = (FundingStream.PSSSP, FundingStream.UCEPP)


def saved_streams(user) -> list[str]:
    """The tags the screening wrote on this account.

    Falls back to the two eligibility booleans for accounts opened before the
    tags existed. The fallback cannot produce UCEPP — nothing on an old account
    records whether the programme was an upgrading one — so those accounts keep
    behaving exactly as they did rather than being guessed into a stream.

    **An empty list is only a missing answer when nobody has ever answered.**
    The fallback used to fire on any account with no tags, which was safe while
    the only way to have none was to predate them. It is not safe now that a
    student can re-answer the screening on their profile: somebody who has
    started receiving SFA and is not a beneficiary qualifies for nothing, that
    is a decision rather than a gap, and falling through to
    `is_indian_act_registered` handed them PSSSP back — the exact fault
    `eligible_streams` was added to stop, arriving from the other direction. So
    the assessment date is what separates "screened, and the answer is nothing"
    from "never screened".
    """
    saved = [str(s).lower() for s in (getattr(user, 'eligible_streams', None) or [])]
    valid = [s for s in saved if s in FundingStream.values]
    if valid:
        return valid
    if getattr(user, 'eligibility_assessed_at', None) is not None:
        return []

    legacy = []
    if getattr(user, 'is_indian_act_registered', False):
        legacy.append(FundingStream.PSSSP)
    if getattr(user, 'is_deline_beneficiary', False):
        legacy.append(FundingStream.DGGR)
    return legacy


def eligible_streams(user, answers: dict | None = None) -> list[str]:
    """Every stream this person could be funded from, best first.

    The account's tags, minus anything this term's SFA answer withdraws.
    """
    streams = saved_streams(user)
    if receives_sfa(answers):
        streams = [s for s in streams if s not in SFA_EXCLUDES]
    return streams


def for_application(user, application_type: str, answers: dict | None = None) -> str:
    """The stream this application is funded from.

    The C-DFN stream first where it applies: it is the federal programme that
    funds tuition and a living allowance, and DGGR tops up rather than replaces
    it. A student who qualifies for both should not be funded from the smaller
    pot because a dropdown defaulted that way.

    This is the *primary* stream only — the one whose deadline the submission is
    measured against. Pricing draws on everything the applicant qualifies for;
    see `funding.rules.engine._streams_for`.
    """
    if application_type in ALWAYS_DGGR:
        return FundingStream.DGGR

    streams = eligible_streams(user, answers)
    if not streams:
        raise NoStreamAvailable(
            'This account does not currently qualify for any funding stream. '
            'Please contact the DGG Education Department.'
        )
    return streams[0]
