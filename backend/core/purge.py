"""Empty the case data out of a database while leaving the office's setup standing.

Lives in `core` rather than under `funding/` for two reasons: it spans three
apps, and `accounts.test_profile.test_only_prefill_reads_the_profile` bars
anything under `funding/` from so much as naming `EnrolmentProfile` — the guard
against the old fallback where profile data leaked into what a student was paid.
Counting profile rows before deleting them is not that, but the guard is worth
more than the convenience of putting this file next to the models it deletes.

Written for the cut-over to production. The database this was developed against
carried 1,516 applications, 3,196 queued emails and 338 accounts on
`@example.com` that the live audit scripts in `backend/scripts/` created — none
of which should exist on the day the office starts taking real applications.

**What it removes:** applications and everything that hangs off one — events,
awards, decisions, repayments, encrypted identifiers, uploaded documents,
enrolment verifications — plus in-portal notifications and, unless told
otherwise, the outbound email queue.

**What it keeps:** every account, unless `drop_test_accounts` is asked for; the
profile, banking and eligibility rows belonging to a kept account; and the whole
of the office's configuration — policy settings and their change history,
deadlines, rule sets and rules, and the hand-entered report costs. Deleting a
`RuleSet` is refused by the database anyway (`AwardDecision.rule_set` is
PROTECT), which is deliberate: a rule set that priced something is part of the
record.

**Order matters twice.**

`AuditEntry.application` is SET_NULL, not CASCADE. Delete the applications first
and the audit rows survive as entries about nothing, so the application-scoped
ones go first, deliberately, while they can still be identified. Audit entries
that are not about an application — policy edits, staff administration — are
left alone: they are the office's own history, not case data.

`SupportingDocument.application` is nullable, because the graduation award is
claimable by someone with no account. Those rows are not reachable from any
application and would survive a cascade, so documents are cleared as a set.

**The files themselves are not deleted.** Django removes the row, never the
blob. On local disk that leaves orphans under MEDIA_ROOT; on Supabase Storage it
leaves objects in the bucket. Both are reported so the caller can decide.

**Cutting down to a named set of accounts** is a second, blunter thing, asked
for when a database that has been tested against is about to become the one the
office signs into: `keep_emails` names who survives and *everyone else goes*,
staff included. It is deliberately not a variant of `drop_test_accounts` —
that one reasons about which addresses are throwaway and protects staff on
principle, and the two answering the same question differently in one run is
how a safeguard becomes a coin toss. Asking for both is refused.

Two things guard it, because the failure mode is losing an account nobody can
recreate from inside the portal:

*A name that matches nothing is refused.* A typo in a keep list does not fail
loudly on its own — the address simply matches no row, and the account it was
meant to protect is deleted with the rest. Every address must resolve.

*An administrator must survive.* Nothing in a portal with no `is_superuser` and
no `Role.ADMIN` can create the next account, so a keep list that leaves none is
refused rather than obeyed. §10 of the project notes records the shape of this
already: a correctly deployed portal with no accounts refuses every login and
reads as a broken deployment.

**Attribution is nulled, not carried.** Nine of the eleven foreign keys into
`User` are SET_NULL, and four of them are on rows a purge *keeps* —
`PolicyChange.changed_by`, `RuleSet.created_by`, `ReportedCost.recorded_by`, and
the audit entries that are not about an application. Deleting the account that
made those entries leaves the office's history standing with nobody's name on
it. That is the correct behaviour — the entry matters more than the attribution,
and PROTECT here would make the account undeletable — but it is a real loss and
the report counts it rather than letting it happen quietly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q


class PurgeRefused(Exception):
    """The purge was asked for something it will not do."""

# Domains the audit scripts and the seed command invent addresses on. An account
# here is never a person.
DEFAULT_TEST_DOMAINS: tuple[str, ...] = ('example.com', 'dgg.test', 'test.local')


@dataclass
class PurgeReport:
    """What went, or what would go. Ordered as the deletion runs."""

    counts: dict[str, int] = field(default_factory=dict)
    users_deleted: list[str] = field(default_factory=list)
    users_kept: list[str] = field(default_factory=list)
    documents_left_on_disk: int = 0
    # Rows the purge keeps whose 'who did this' becomes NULL because the account
    # that did it is being deleted. Counted per model, never silently.
    attributions_cleared: dict[str, int] = field(default_factory=dict)
    dry_run: bool = True

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def test_accounts(domains: tuple[str, ...] = DEFAULT_TEST_DOMAINS):
    """Student accounts on a throwaway domain.

    Staff are excluded by role and by `is_staff`/`is_superuser` regardless of
    their address — `admin@dgg.test` is on a test domain and is the account that
    administers the site. Locking the office out of its own portal while
    tidying up would be a poor trade.
    """
    from accounts.models import Role, User

    matches = Q()
    for domain in domains:
        matches |= Q(email__iendswith=f'@{domain}')

    return User.objects.filter(
        matches, role=Role.STUDENT, is_staff=False, is_superuser=False,
    )


def accounts_outside(keep_emails):
    """Every account that is *not* in the keep list. Staff included.

    Case-insensitive, because an address typed into a command line is not
    obliged to match the case it was registered with, and deleting the
    administrator over a capital letter is not a defensible outcome.
    """
    from accounts.models import User

    wanted = {e.strip().lower() for e in keep_emails if e.strip()}
    if not wanted:
        raise PurgeRefused(
            'An empty keep list would delete every account, including the one '
            'that administers the site. Name who survives.'
        )

    matches = Q()
    for email in wanted:
        matches |= Q(email__iexact=email)

    found = {e.lower() for e in
             User.objects.filter(matches).values_list('email', flat=True)}
    missing = sorted(wanted - found)
    if missing:
        raise PurgeRefused(
            'No account matches: ' + ', '.join(missing) + '. A keep list is '
            'checked before anything is deleted precisely because a mistyped '
            'address does not announce itself — it simply matches nothing, and '
            'the account it was meant to protect goes with the rest.'
        )

    return User.objects.exclude(matches)


def _refuse_if_no_administrator_survives(doomed) -> None:
    """A portal with no administrator cannot make the next account.

    The keep list decides who stays; this decides whether what stays is a
    working portal. Checked against the database rather than against the list,
    because what matters is the role on the surviving row and not the intent
    behind the address that named it.
    """
    from accounts.models import Role, User

    survivors = User.objects.exclude(pk__in=doomed.values_list('pk', flat=True))
    if not survivors.filter(
        Q(is_superuser=True) | Q(role=Role.ADMIN), is_active=True,
    ).exists():
        raise PurgeRefused(
            'That keep list leaves no active administrator, and nothing inside '
            'the portal can create one. Registration makes students; staff are '
            'made by an administrator. Keep an account with role=admin or '
            'is_superuser, or create one before purging.'
        )


def survey(*, drop_test_accounts: bool = False,
           test_domains: tuple[str, ...] = DEFAULT_TEST_DOMAINS,
           purge_outbox: bool = True,
           keep_emails: tuple[str, ...] = ()) -> PurgeReport:
    """Count what a purge would remove, without touching anything."""
    from accounts.models import BankAccount, EnrolmentProfile, User
    from funding.models import (
        ApplicantIdentifier, Application, ApplicationEvent, AuditEntry, Award,
        AwardDecision, AwardRepayment, EnrollmentVerification, PolicyChange,
        ReportedCost, RuleSet, SupportingDocument,
    )
    from notifications.models import Notification, OutboundEmail

    if keep_emails and drop_test_accounts:
        raise PurgeRefused(
            '--keep-only and --drop-test-accounts answer the same question in '
            'two different ways: one protects staff on principle, the other '
            'deletes everyone unnamed. Pick one.'
        )

    report = PurgeReport(dry_run=True)
    report.counts = {
        'AuditEntry (application-scoped)':
            AuditEntry.objects.filter(application__isnull=False).count(),
        'Notification': Notification.objects.count(),
        'SupportingDocument': SupportingDocument.objects.count(),
        'ApplicantIdentifier': ApplicantIdentifier.objects.count(),
        'EnrollmentVerification': EnrollmentVerification.objects.count(),
        'AwardRepayment': AwardRepayment.objects.count(),
        'Award': Award.objects.count(),
        'AwardDecision': AwardDecision.objects.count(),
        'ApplicationEvent': ApplicationEvent.objects.count(),
        'Application': Application.objects.count(),
    }
    if purge_outbox:
        report.counts['OutboundEmail'] = OutboundEmail.objects.count()

    report.documents_left_on_disk = report.counts['SupportingDocument']

    if drop_test_accounts or keep_emails:
        if keep_emails:
            doomed = accounts_outside(keep_emails)
            _refuse_if_no_administrator_survives(doomed)
            label = 'not in the keep list'
        else:
            doomed = test_accounts(test_domains)
            label = 'test accounts'

        ids = list(doomed.values_list('pk', flat=True))
        # Only the User row varies by mechanism. The rows hanging off it read
        # the same either way, and interpolating the mechanism into them
        # produced 'EnrolmentProfile (of not in the keep list)'.
        report.counts[f'User ({label})'] = len(ids)
        report.counts['EnrolmentProfile (of a deleted account)'] = (
            EnrolmentProfile.objects.filter(user_id__in=ids).count())
        report.counts['BankAccount (of a deleted account)'] = (
            BankAccount.objects.filter(user_id__in=ids).count())
        report.users_deleted = sorted(doomed.values_list('email', flat=True))
        report.users_kept = sorted(
            User.objects.exclude(pk__in=ids).values_list('email', flat=True))

        # Office history that survives the purge but loses whose name is on it.
        # Counted, not prevented: PROTECT here would make the account
        # undeletable, and the entry is worth more than the attribution.
        report.attributions_cleared = {
            'PolicyChange.changed_by':
                PolicyChange.objects.filter(changed_by_id__in=ids).count(),
            'RuleSet.created_by':
                RuleSet.objects.filter(created_by_id__in=ids).count(),
            'ReportedCost.recorded_by':
                ReportedCost.objects.filter(recorded_by_id__in=ids).count(),
            'AuditEntry.actor (not about an application)':
                AuditEntry.objects.filter(
                    actor_id__in=ids, application__isnull=True).count(),
        }
    else:
        report.users_kept = sorted(User.objects.values_list('email', flat=True))

    return report


@transaction.atomic
def purge(*, drop_test_accounts: bool = False,
          test_domains: tuple[str, ...] = DEFAULT_TEST_DOMAINS,
          purge_outbox: bool = True,
          keep_emails: tuple[str, ...] = ()) -> PurgeReport:
    """Delete the case data. One transaction: it all goes or none of it does."""
    from accounts.models import User
    from funding.models import (
        Application, AuditEntry, SupportingDocument,
    )
    from notifications.models import Notification, OutboundEmail

    # Surveying first is what runs the guards: an empty or mistyped keep list,
    # and a keep list with no administrator in it, both raise here — before the
    # first delete rather than partway through one.
    report = survey(
        drop_test_accounts=drop_test_accounts,
        test_domains=test_domains,
        purge_outbox=purge_outbox,
        keep_emails=keep_emails,
    )
    report.dry_run = False

    # Before the applications: SET_NULL would otherwise leave these unidentifiable.
    AuditEntry.objects.filter(application__isnull=False).delete()
    Notification.objects.all().delete()
    if purge_outbox:
        OutboundEmail.objects.all().delete()
    # Guest uploads carry no application and survive the cascade.
    SupportingDocument.objects.all().delete()
    Application.objects.all().delete()

    # Re-resolve rather than reuse the surveyed ids: the deletes above may
    # have changed nothing about who matches, but the query is cheap and a
    # stale id list deleting the wrong account is not a risk worth carrying.
    if keep_emails:
        User.objects.filter(pk__in=accounts_outside(keep_emails)).delete()
    elif drop_test_accounts:
        User.objects.filter(pk__in=test_accounts(test_domains)).delete()

    return report
