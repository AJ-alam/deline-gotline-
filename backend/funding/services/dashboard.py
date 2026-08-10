"""The numbers a person sees when they open the portal.

Everything here is computed by aggregation in the database. The screen this
replaces fetched seven endpoints every thirty seconds, pulled every application
with every answer, and counted them in the browser — which is why it grew slower
with every application the office received.

The cost of this does not change with the number of applications.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum

from funding.models import (
    Application, ApplicationStatus, Award, EnrollmentVerification,
)

ZERO = Decimal('0.00')


def _counts_by_status(queryset) -> dict[str, int]:
    """One query for every status count, rather than one query per status."""
    counted = {
        row['status']: row['n']
        for row in queryset.values('status').annotate(n=Count('id'))
    }
    return {status: counted.get(status, 0) for status in ApplicationStatus.values}


def for_student(user) -> dict:
    applications = Application.objects.filter(student=user)
    by_status = _counts_by_status(applications)

    awarded = (Award.objects
               .filter(application__student=user)
               .aggregate(total=Sum('amount'))['total']) or ZERO
    paid = (Award.objects
            .filter(application__student=user, status=Award.Status.PAID)
            .aggregate(total=Sum('amount'))['total']) or ZERO

    return {
        'scope': 'student',
        'applications': {
            'total': sum(by_status.values()),
            'open': sum(by_status[s] for s in ApplicationStatus.open_states()),
            'by_status': by_status,
        },
        'money': {'awarded': str(awarded), 'paid': str(paid)},
        # What the student is waiting on, phrased as something they can act on.
        'waiting_on_you': by_status[ApplicationStatus.INFO_REQUESTED],
    }


def for_staff(user) -> dict:
    applications = Application.objects.all()
    by_status = _counts_by_status(applications)

    money = Award.objects.aggregate(
        awarded=Sum('amount'),
        pending=Sum('amount', filter=Q(status=Award.Status.PENDING)),
        sent=Sum('amount', filter=Q(status=Award.Status.SENT_TO_FINANCE)),
    )

    flags = applications.aggregate(
        late=Count('id', filter=Q(submitted_after_deadline=True)),
        residency=Count('id', filter=~Q(residency_flag='')),
    )

    awaiting_enrolment = EnrollmentVerification.objects.filter(
        status=EnrollmentVerification.Status.REQUESTED,
    ).count()

    return {
        'scope': 'staff',
        'applications': {
            'total': sum(by_status.values()),
            'open': sum(by_status[s] for s in ApplicationStatus.open_states()),
            'by_status': by_status,
        },
        'money': {
            'awarded': str(money['awarded'] or ZERO),
            'awaiting_payment': str(money['pending'] or ZERO),
            'sent_to_finance': str(money['sent'] or ZERO),
        },
        # The three queues someone actually works from.
        'queues': {
            'to_review': by_status[ApplicationStatus.SUBMITTED],
            'awaiting_decision': by_status[ApplicationStatus.AWAITING_DECISION],
            'awaiting_enrolment_confirmation': awaiting_enrolment,
        },
        'attention': {
            'submitted_late': flags['late'],
            'residency_mismatch': flags['residency'],
        },
    }


def summary(user) -> dict:
    """One payload, scoped to what this person is allowed to see."""
    if user.is_student:
        return for_student(user)
    return for_staff(user)
