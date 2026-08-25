"""What a student keeps on file about themselves.

Three things live behind the profile screen, and they are three different kinds
of fact, which is why they are saved by three different calls rather than one
big update:

  identity        who they are. Ordinary account columns, patched on `/api/me/`.
  screening       what they are entitled to. Answers to the office's six
                  questions, which decide the funding streams — so re-answering
                  them re-runs the office's rule rather than writing a stream.
  enrolment       where they study. Convenience only: it pre-fills forms and is
                  never read by anything that decides money.

The banking details are the fourth, and they are not stored here at all — they
go through `funding.services.banking` onto the same `BankAccount` record the
payment run reads, so the profile screen and the application forms cannot
disagree about where somebody is paid.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from accounts.models import EnrolmentProfile, User
from accounts.services import eligibility as eligibility_service
from funding.models import AuditEntry

logger = logging.getLogger(__name__)


def enrolment_profile(user: User) -> EnrolmentProfile:
    """This student's profile, created empty the first time it is asked for.

    Never raises and never returns None: an empty profile and a missing one mean
    the same thing to every caller, and a nullable one would put a `None` check
    in front of every read in `prefill`.
    """
    profile, _created = EnrolmentProfile.objects.get_or_create(user=user)
    return profile


def _changed_answers(before: dict, after: dict) -> list[str]:
    return sorted(key for key in set(before) | set(after)
                  if str(before.get(key, '')).strip().lower()
                  != str(after.get(key, '')).strip().lower())


@transaction.atomic
def save_screening(user: User, answers: dict) -> eligibility_service.Outcome:
    """Re-run the office's eligibility screening and record what it decided.

    The streams are *never* taken from the client. The answers are, the rule is
    the office's, and the outcome is what gets saved — the same arrangement as
    registration, and for the same reason: eligibility rules that a client can
    supply the conclusion to are not rules.

    An outcome that qualifies for nothing is saved like any other. It is
    tempting to refuse it — an account with no streams cannot file anything, and
    `streams.NoStreamAvailable` turns every submission into a 409 — but the
    circumstance it usually describes is real and recent: a student has started
    receiving GNWT Student Financial Assistance, which withdraws both C-DFN
    streams. Refusing to record that leaves the portal funding somebody under a
    stream they have told us they no longer qualify for, which is worse than
    telling them plainly that they now qualify for nothing and to contact the
    office. The message they are shown is the screening's own.

    Every change is audited. These six answers decide what a person is paid, and
    the person editing them is the person being paid — so who changed which
    answer, and when, has to survive.
    """
    locked = User.objects.select_for_update().get(pk=user.pk)
    previous_answers = dict(locked.eligibility_answers or {})
    previous_streams = list(locked.eligible_streams or [])

    outcome = eligibility_service.assess(answers)

    locked.eligibility_answers = dict(answers)
    locked.eligible_streams = list(outcome.streams)
    locked.eligibility_assessed_at = timezone.now()
    # Kept in step with the answers rather than left at what sign-up recorded.
    # `streams.saved_streams` falls back to these two on accounts opened before
    # the tags existed, so a stale pair is a stale funding decision waiting for
    # the tags to be empty.
    locked.is_indian_act_registered = eligibility_service._yes(
        answers, 'indian_act_registered')
    locked.is_deline_beneficiary = eligibility_service._yes(
        answers, 'deline_beneficiary')
    locked.save(update_fields=[
        'eligibility_answers', 'eligible_streams', 'eligibility_assessed_at',
        'is_indian_act_registered', 'is_deline_beneficiary',
    ])

    changed = _changed_answers(previous_answers, answers)
    AuditEntry.objects.create(
        actor=locked, actor_role=locked.role, action='account.screening_updated',
        detail=(
            f'{locked.email} re-answered the eligibility screening. '
            f'Changed: {", ".join(changed) if changed else "nothing"}. '
            f'Streams {previous_streams or ["none"]} → {outcome.streams or ["none"]}.'
        ),
    )
    logger.info('Screening re-run for %s: %s → %s',
                locked.email, previous_streams, outcome.streams)

    # Keep the caller's instance consistent with what was written, the way
    # `workflow.record` does.
    user.eligibility_answers = locked.eligibility_answers
    user.eligible_streams = locked.eligible_streams
    user.eligibility_assessed_at = locked.eligibility_assessed_at
    user.is_indian_act_registered = locked.is_indian_act_registered
    user.is_deline_beneficiary = locked.is_deline_beneficiary

    return outcome


def screening_state(user: User) -> dict:
    """The questions, this student's answers to them, and what they decided.

    One payload, because a screen showing the questions without the answers
    makes a person re-answer from memory, and answers without the outcome make
    them guess what changing one would do.
    """
    return {
        'questions': eligibility_service.questions_payload(),
        'answers': dict(user.eligibility_answers or {}),
        'streams': list(user.eligible_streams or []),
        'assessed_at': user.eligibility_assessed_at,
    }
