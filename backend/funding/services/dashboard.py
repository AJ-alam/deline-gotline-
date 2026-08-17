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
    Application, ApplicationStatus, ApplicationType, Award,
    EnrollmentVerification,
)
from funding.services import deadlines as deadline_service

ZERO = Decimal('0.00')


def _counts_by_status(queryset) -> dict[str, int]:
    """One query for every status count, rather than one query per status."""
    counted = {
        row['status']: row['n']
        for row in queryset.values('status').annotate(n=Count('id'))
    }
    return {status: counted.get(status, 0) for status in ApplicationStatus.values}


def _next_step(user, applications) -> dict:
    """The one thing this student should do next.

    A dashboard of three totals tells someone with no applications nothing at
    all: it reads as a report on an empty file rather than a way in. This names
    the next action, and the reason, so the opening screen is usable by someone
    who has never applied for anything.
    """
    if applications.filter(status=ApplicationStatus.INFO_REQUESTED).exists():
        return {
            'key': 'provide_information',
            'title': 'Answer the office',
            'detail': 'An application is waiting on more information from you.',
            'action': 'Open it',
            'href': '/applications',
        }

    # An admission that was declined is not an admission they have. Counting it
    # sent somebody who had just been refused to `apply_more` — "travel,
    # practicum placements and bursaries are applied for separately" — which
    # reads as "you are funded, here is what else there is" to a person with no
    # funding at all, and hides the one thing they might actually do.
    admission = applications.filter(type=ApplicationType.ADMISSION).exclude(
        status=ApplicationStatus.DECLINED)
    if not admission.exists():
        return {
            'key': 'apply_admission',
            'title': 'Start your admission application',
            'detail': (
                'This is the first application, and it establishes which '
                'funding you are eligible for. Everything else follows from it.'
            ),
            'action': 'Start application',
            'href': '/apply/admission',
        }

    # Only where the application is still live. A registrar who has not answered
    # by the time an application is decided never will, so the verification sits
    # at REQUESTED for good — and this told a student whose application had been
    # *declined* that the office was "waiting on your institution" and that
    # "nothing is needed from you", permanently. The question is not whether a
    # request is outstanding; it is whether anything is still waiting on it.
    awaiting = EnrollmentVerification.objects.filter(
        application__student=user,
        application__status__in=ApplicationStatus.open_states(),
        status=EnrollmentVerification.Status.REQUESTED,
    ).exists()
    if awaiting:
        return {
            'key': 'awaiting_enrolment',
            'title': 'Waiting on your institution',
            'detail': (
                'We have asked your registrar to confirm your enrolment and '
                'the tuition billed. Tuition cannot be awarded until it '
                'arrives. Nothing is needed from you.'
            ),
            'action': '',
            'href': '',
        }

    if applications.filter(status__in=ApplicationStatus.open_states()).exists():
        return {
            'key': 'in_review',
            'title': 'Your application is with the office',
            'detail': 'You will be told as soon as there is a decision.',
            'action': 'Track it',
            'href': '/applications',
        }

    return {
        'key': 'apply_more',
        'title': 'Apply for further funding',
        'detail': 'Travel, practicum placements and bursaries are applied for separately.',
        'action': 'See what you can apply for',
        'href': '/applications',
    }


def _recent(applications, limit: int = 5) -> list[dict]:
    """The last few applications, as a student would describe them."""
    return [
        {
            'id': application.id,
            'type': application.type,
            'type_label': application.get_type_display(),
            'status': application.status,
            'status_label': application.get_status_display(),
            'awarded_total': str(application.awarded_amount),
            'submitted_at': application.submitted_at,
        }
        for application in applications.order_by('-submitted_at')[:limit]
    ]


def for_student(user) -> dict:
    applications = Application.objects.filter(student=user)
    by_status = _counts_by_status(applications)

    # Scoped to the decision in force *and* to an application that has been
    # approved. Scoping by decision alone was the previous fix and only half of
    # the answer: it stopped a re-pricing being counted twice, and still counted
    # a pricing nobody had decided on. A student under review was shown money
    # for an application the institution had not confirmed, and a student whose
    # application was declined went on being shown it afterwards.
    awarded = (Award.objects.awarded()
               .filter(application__student=user)
               .aggregate(total=Sum('amount'))['total']) or ZERO
    # Not scoped: money that left the bank under a decision since superseded
    # still left the bank.
    paid = (Award.objects.paid()
            .filter(application__student=user)
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
        'student': {
            'name': user.first_name or user.full_name,
            'reference': user.beneficiary_number or '',
        },
        'next_step': _next_step(user, applications),
        'recent': _recent(applications),
        'deadlines': _deadlines(),
    }


def _deadlines() -> list[dict]:
    """The next cut-offs. Empty when the office has set none, and the client
    shows nothing rather than inventing dates."""
    # No stream: these are deduplicated by term, and naming one of the three
    # streams the date came from would be arbitrary and read as a restriction.
    return [
        {
            'semester': deadline.semester,
            'academic_year': deadline.academic_year,
            'closes_at': deadline.closes_at,
            'late_allowed': deadline.late_allowed,
        }
        for deadline in deadline_service.upcoming()
    ]


def for_staff(user) -> dict:
    applications = Application.objects.all()
    by_status = _counts_by_status(applications)

    # The same scoping as the student's, for the same reason: the office's
    # totals were inflated by every re-pricing anybody had ever done, and then
    # by every pricing of an application nobody had approved.
    money = Award.objects.awarded().aggregate(
        awarded=Sum('amount'),
        pending=Sum('amount', filter=Q(status=Award.Status.PENDING)),
        # Dispatching the payment file is what marks an award paid, so this is
        # the figure that has gone out. It counted SENT_TO_FINANCE while nothing
        # wrote PAID; both cannot be read, and the one the run writes is the one
        # that is true.
        paid=Sum('amount', filter=Q(status=Award.Status.PAID)),
    )

    # Scoped to applications still open, because these are things to act on. A
    # decided application submitted late is a fact about the past; counting it
    # here put a number beside "needs attention" that no amount of work could
    # bring down, which is how a queue stops being read at all.
    open_applications = applications.filter(status__in=ApplicationStatus.open_states())
    flags = open_applications.aggregate(
        late=Count('id', filter=Q(submitted_after_deadline=True)),
        residency=Count('id', filter=~Q(residency_flag='')),
    )

    # The same fault as the student's "waiting on your institution": a registrar
    # who has not answered by the time an application is decided never will, so
    # the request stays REQUESTED for good. Unscoped, this was a work queue with
    # a floor it could never go below.
    awaiting_enrolment = EnrollmentVerification.objects.filter(
        application__status__in=ApplicationStatus.open_states(),
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
            'paid': str(money['paid'] or ZERO),
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
