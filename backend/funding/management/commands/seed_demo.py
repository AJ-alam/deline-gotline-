"""Populate a database with enough to exercise the portal end to end.

    python manage.py seed_demo

Creates one account per role, the funding rates every award is computed from,
and a published rule set. Intended for local work and manual testing; it refuses
to run against a database that already holds applications, so it cannot be
pointed at production by accident.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import BankAccount, Role, User
from accounts.services import eligibility
from funding.models import Application
from funding.office_config import install as install_office_config
# Re-exported: `funding.test_rules` reads the seeded rates through this name, and
# migration 0013 documents itself as mirroring `seed_demo.RATES`. One list, in
# `funding.office_config`, reachable by the name that already refers to it.
from funding.office_config import RATES  # noqa: F401

PASSWORD = 'DemoPass123!'

# What a seeded student answered at sign-up. Both C-DFN and DGGR, which is the
# case worth having in demo data: §7 of the policy allows holding both, and a
# student funded from one stream would never exercise the top-up.
SCREENING_ANSWERS = {
    'indian_act_registered': 'yes',
    'deline_beneficiary': 'yes',
    'receives_sfa': 'no',
    'lives_in_nwt': 'yes',
    'accredited_institution': 'yes',
    'programme_twelve_weeks': 'yes',
}

PEOPLE = [
    ('admin@dgg.test', 'Alice', 'Administrator', Role.ADMIN),
    ('director@dgg.test', 'Daniel', 'Director', Role.DIRECTOR),
    ('worker@dgg.test', 'Wanda', 'Worker', Role.SUPPORT_WORKER),
    ('finance@dgg.test', 'Fred', 'Finance', Role.FINANCE),
    ('student@dgg.test', 'Sara', 'Student', Role.STUDENT),
    # A second student, so "one student cannot open another's application" is a
    # thing that can actually be tried. With one student in the data the check
    # in lifecycle_audit had nothing to point at and reported that it could not
    # run — which is the same shape of defect as a dashboard count that can only
    # ever be zero.
    ('student2@dgg.test', 'Sam', 'Secondstudent', Role.STUDENT),
]


class Command(BaseCommand):
    help = 'Create demo accounts, funding rates, deadlines and a published rule set.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Run even if applications already exist.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if Application.objects.exists() and not options['force']:
            raise CommandError(
                f'This database already holds {Application.objects.count()} '
                'application(s). Refusing to seed over real data — pass --force '
                'if you are certain.'
            )

        self.stdout.write(self.style.MIGRATE_HEADING('Accounts'))
        for email, first, last, role in PEOPLE:
            user, created = User.objects.get_or_create(
                email=email,
                defaults=dict(first_name=first, last_name=last, role=role),
            )
            user.role = role
            user.is_staff = role == Role.ADMIN
            user.is_superuser = role == Role.ADMIN
            if role == Role.STUDENT:
                # Distinct per student. Two people sharing a beneficiary number
                # is not a thing the office's records can express, and demo data
                # that says otherwise teaches the wrong shape.
                user.beneficiary_number = f'B-{1000 + len(user.email):04d}'
                user.is_deline_beneficiary = True
                user.is_indian_act_registered = True
                # Seeded through the same screening a real applicant answers,
                # rather than having the tags written in. A seeded student used
                # to have none at all: the fallback in
                # `funding.services.streams.saved_streams` still funded them
                # correctly from the two booleans, so nothing broke — but their
                # portal showed no streams, and demo data that behaves unlike a
                # registered account teaches the wrong shape.
                answers = dict(SCREENING_ANSWERS)
                user.eligibility_answers = answers
                user.eligible_streams = eligibility.streams_for(answers)
                user.eligibility_assessed_at = timezone.now()
            user.set_password(PASSWORD)
            user.save()

            if role == Role.STUDENT and not user.bank_accounts.exists():
                BankAccount.objects.create(
                    user=user, account_holder=user.full_name,
                    transit_number='12345', institution_number='001',
                    account_number='9876543210',
                )
            self.stdout.write(f'  {"created" if created else "updated"}  {email}  ({role})')

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nRates, deadlines and rule set'))
        install_office_config(stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Every account uses the password: {PASSWORD}\n'
        ))
        for email, _, _, role in PEOPLE:
            self.stdout.write(f'  {role:<16} {email}')
