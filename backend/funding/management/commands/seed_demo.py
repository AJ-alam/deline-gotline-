"""Populate a database with enough to exercise the portal end to end.

    python manage.py seed_demo

Creates one account per role, the funding rates every award is computed from,
and a published rule set. Intended for local work and manual testing; it refuses
to run against a database that already holds applications, so it cannot be
pointed at production by accident.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import BankAccount, Role, User
from funding.models import (
    Application, ApplicationDeadline, FundingStream, PolicySetting, RuleSet,
)
from funding.services.policy_admin import unit_for

PASSWORD = 'DemoPass123!'

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

# Every figure below is the one printed in the DGG Bursary & Awards Program
# Procedure, section by section. Nothing here is a placeholder: the earlier set
# was invented for the rebuild, and where the two disagreed the policy wins.
# Amend a rate through the policy screen, which records who changed it and when
# it takes effect — editing this list only changes what a *new* database is
# seeded with.
RATES = [
    # ── §7 C-DFN PSSSP ──
    # One cap covering tuition, mandatory books and supplies, and additional
    # fees. The policy funds all three from the same $5,000, which is why there
    # is no separate book allowance any more.
    ('psssp_tuition', 'max_per_semester', '5000.00',
     'PSSSP tuition, books and fees, per semester'),
    ('psssp_living', 'fulltime_no_dependents', '1200.00', 'PSSSP living, full-time, no dependants'),
    ('psssp_living', 'fulltime_with_dependents', '1700.00', 'PSSSP living, full-time, with dependants'),
    ('psssp_living', 'parttime_no_dependents', '720.00', 'PSSSP living, part-time, no dependants'),
    ('psssp_living', 'parttime_with_dependents', '1020.00', 'PSSSP living, part-time, with dependants'),

    # ── §8 C-DFN UCEPP (upgrading programmes) ──
    ('ucepp_tuition', 'max_per_semester', '2000.00',
     'UCEPP tuition, books and fees, per semester'),
    ('ucepp_living', 'fulltime_no_dependents', '700.00', 'UCEPP living, full-time, no dependants'),
    ('ucepp_living', 'fulltime_with_dependents', '1000.00', 'UCEPP living, full-time, with dependants'),
    ('ucepp_living', 'parttime_no_dependents', '420.00', 'UCEPP living, part-time, no dependants'),
    ('ucepp_living', 'parttime_with_dependents', '600.00', 'UCEPP living, part-time, with dependants'),

    # ── §9(A) DGGR Tuition Bursary — a top-up, per semester, by course load ──
    ('dggr_tuition', 'fulltime_per_semester', '1500.00', 'DGGR tuition top-up, full-time'),
    ('dggr_tuition', 'parttime_per_semester', '900.00', 'DGGR tuition top-up, part-time'),

    # ── §9(C) DGGR Monthly Living Bursary ──
    ('dggr_living', 'fulltime_no_dependents', '700.00', 'DGGR living, full-time, no dependants'),
    ('dggr_living', 'fulltime_with_dependents', '950.00', 'DGGR living, full-time, with dependants'),
    ('dggr_living', 'parttime_no_dependents', '420.00', 'DGGR living, part-time, no dependants'),
    ('dggr_living', 'parttime_with_dependents', '570.00', 'DGGR living, part-time, with dependants'),

    # ── §9(B) DGGR Extra Tuition Bursary for expensive programmes ──
    # "over $5,000 per semester", "up to 25% of tuition", "maximum $4,000 per
    # semester". The cap is stated to be inclusive of the regular tuition
    # bursary, which is what `inclusive_of` on the rule expresses.
    ('dggr_extra_tuition', 'threshold_per_semester', '5000.00',
     'Extra tuition bursary applies above this tuition'),
    ('dggr_extra_tuition', 'max_percent_covered', '25.00',
     'Share of tuition covered by the extra tuition bursary'),
    ('dggr_extra_tuition', 'max_per_semester', '4000.00',
     'Extra tuition bursary cap per semester, inclusive of the tuition top-up'),

    # ── §9(E) DGGR Grad Bursary, by credential ──
    ('graduation_bursary', 'high_school_diploma', '500.00', 'Grad bursary, high school diploma'),
    ('graduation_bursary', 'certificate', '1000.00', 'Grad bursary, certificate'),
    ('graduation_bursary', 'trades_certificate', '2000.00',
     'Grad bursary, trades certificate of qualification'),
    ('graduation_bursary', 'trades_journeyperson', '3000.00',
     'Grad bursary, trades journeyperson licence'),
    ('graduation_bursary', 'diploma', '2000.00', 'Grad bursary, diploma'),
    ('graduation_bursary', 'pilot_licence', '3000.00', 'Grad bursary, professional pilot licence'),
    ('graduation_bursary', 'red_seal', '3000.00', 'Grad bursary, Red Seal'),
    ('graduation_bursary', 'bachelors_degree', '3000.00',
     'Grad bursary, bachelors degree (including B.Ed.)'),
    ('graduation_bursary', 'masters_degree', '5000.00', 'Grad bursary, masters degree'),
    ('graduation_bursary', 'doctorate', '5000.00', 'Grad bursary, doctorate (PhD)'),
    ('graduation_bursary', 'juris_doctor', '5000.00',
     'Grad bursary, Juris Doctor or Bachelor of Laws'),
    ('graduation_bursary', 'md_dds', '5000.00',
     'Grad bursary, Doctor of Medicine or Doctor of Dental Surgery'),

    # ── §9(F) DGGR Academic Achievement Scholarships ──
    ('academic_scholarship', 'high_threshold_percent', '80.00', 'High achievement threshold'),
    ('academic_scholarship', 'mid_threshold_percent', '70.00', 'Mid achievement threshold'),
    ('academic_scholarship', 'high_achievement_award', '1000.00',
     'Achievement scholarship, 80% and above'),
    ('academic_scholarship', 'mid_achievement_award', '500.00',
     'Achievement scholarship, 70% to 79.99%'),

    # ── §9(D) DGGR Summer Student Employment or Practicum Award ──
    ('practicum', 'allowance', '500.00', 'Summer student / practicum award'),

    # ── §9(G) DGGR Hardship Bursary ──
    # "up to $500". The seeded figure used to be $3,000 and §8 of the handover
    # recorded the disagreement as an open question for the office; the policy
    # answers it.
    ('hardship_bursary', 'max_per_student', '500.00', 'Hardship bursary cap'),

    # ── §7(C) and §7(D) Travel ──
    # Travel assistance is capped by whether the student has dependants, not by
    # which end of the year the trip is at. The graduation travel bursary is a
    # separate, larger cap and does not vary.
    ('travel', 'max_start_of_study_no_dependents', '2000.00',
     'Travel assistance per trip, no dependants'),
    ('travel', 'max_start_of_study_with_dependents', '3500.00',
     'Travel assistance per trip, with dependants'),
    ('travel', 'max_end_of_study_no_dependents', '2000.00',
     'Return travel per trip, no dependants'),
    ('travel', 'max_end_of_study_with_dependents', '3500.00',
     'Return travel per trip, with dependants'),
    ('travel', 'max_graduation_no_dependents', '5000.00', 'Graduation travel bursary'),
    ('travel', 'max_graduation_with_dependents', '5000.00',
     'Graduation travel bursary, with dependants'),

    # ── Not in the policy ──
    # Emergency relief is a form this portal carries and the Bursary & Awards
    # Program Procedure does not describe. The hardship bursary is the only
    # discretionary help the policy defines. Kept at its existing rate rather
    # than invented afresh or silently deleted; the office has to say whether
    # the form should stay. See docs/PROJECT_STATE.md §8.
    ('emergency_relief', 'max_per_student', '1500.00', 'Emergency relief cap'),
]


# The office's published cut-offs. Seeded for the academic year that is running
# now and the one after, so the portal always has an upcoming date to show
# rather than a list of dates that have all passed.
# §10: August 1 for Fall, December 1 for Winter, April 1 for Spring, June 1 for
# Summer. Summer was missing, so a summer application had no deadline to be
# measured against and could never be flagged late.
SEMESTER_CLOSES = (
    ('fall', 8, 1),
    ('winter', 12, 1),
    ('spring', 4, 1),
    ('summer', 6, 1),
)


def _academic_year(closes) -> str:
    start = closes.year if closes.month >= 8 else closes.year - 1
    return f'{start}-{start + 1}'


def _deadlines():
    """(stream, semester, closes_at) for every stream and term."""
    today = date.today()
    first = today.year if today.month < 8 else today.year + 1
    rows = []
    for year in (first - 1, first):
        for semester, month, day in SEMESTER_CLOSES:
            closes = timezone.make_aware(
                timezone.datetime(year, month, day, 23, 59))
            for stream in FundingStream.values:
                rows.append((stream, semester, closes))
    return rows


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
            user.set_password(PASSWORD)
            user.save()

            if role == Role.STUDENT and not user.bank_accounts.exists():
                BankAccount.objects.create(
                    user=user, account_holder=user.full_name,
                    transit_number='12345', institution_number='001',
                    account_number='9876543210',
                )
            self.stdout.write(f'  {"created" if created else "updated"}  {email}  ({role})')

        self.stdout.write(self.style.MIGRATE_HEADING('\nFunding rates'))
        for section, key, value, label in RATES:
            PolicySetting.objects.update_or_create(
                section=section, key=key,
                defaults=dict(label=label, value=Decimal(value), unit=unit_for(key)),
            )
        self.stdout.write(f'  {len(RATES)} rates set')

        self.stdout.write(self.style.MIGRATE_HEADING('\nDeadlines'))
        for stream, semester, closes in _deadlines():
            ApplicationDeadline.objects.update_or_create(
                stream=stream, academic_year=_academic_year(closes),
                semester=semester,
                defaults=dict(closes_at=closes, late_allowed=True),
            )
        self.stdout.write(f'  {len(_deadlines())} deadlines set')

        self.stdout.write(self.style.MIGRATE_HEADING('\nRule set'))
        if not RuleSet.objects.filter(status=RuleSet.Status.PUBLISHED).exists():
            call_command('seed_rules', '--publish', '--effective-from',
                         (date.today() - timedelta(days=365)).isoformat(), verbosity=0)
            self.stdout.write('  published')
        else:
            self.stdout.write('  already published')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Every account uses the password: {PASSWORD}\n'
        ))
        for email, _, _, role in PEOPLE:
            self.stdout.write(f'  {role:<16} {email}')
