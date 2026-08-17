"""Create the baseline rule set from the funding policy currently in force.

    python manage.py seed_rules
    python manage.py seed_rules --publish

Each rule below replaces a branch of the old 847-line calculator. The point is
that they are now data: an administrator can read them, and changing a rate is
an edit with an audit trail rather than a deploy.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from funding.models import ApplicationType, Award, FundingStream, Rule, RuleSet

BASELINE = 'DGG Student Funding Policy'

RULES = [
    # ── Tuition, allocated against the real bill in stream order ──
    dict(
        code='psssp_tuition',
        description='PSSSP tuition, up to the per-semester cap',
        category=Award.Category.TUITION,
        order=10,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.PSSSP],
        condition={'all': [
            {'field': 'receives_sfa', 'op': 'ne', 'value': True},
            {'field': 'confirmed_tuition', 'op': 'is_set'},
        ]},
        effect={'kind': 'capped_tuition', 'section': 'psssp_tuition', 'key': 'max_per_semester'},
    ),
    dict(
        code='ucepp_tuition',
        description='UCEPP tuition, up to the per-semester cap',
        category=Award.Category.TUITION,
        order=20,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.UCEPP],
        condition={'all': [
            {'field': 'receives_sfa', 'op': 'ne', 'value': True},
            {'field': 'confirmed_tuition', 'op': 'is_set'},
        ]},
        effect={'kind': 'capped_tuition', 'section': 'ucepp_tuition', 'key': 'max_per_semester'},
    ),
    dict(
        code='dggr_tuition_top_up',
        description='DGGR tops up tuition the C-DFN caps left unpaid',
        category=Award.Category.TUITION,
        order=30,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.DGGR],
        condition={'field': 'confirmed_tuition', 'op': 'is_set'},
        effect={'kind': 'capped_tuition', 'section': 'dggr_tuition', 'key': '{load}_per_semester'},
    ),
    dict(
        code='dggr_extra_tuition_relief',
        description='Relief on tuition above the threshold, inclusive of the DGGR top-up',
        category=Award.Category.TUITION,
        order=40,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.DGGR],
        condition={'field': 'confirmed_tuition', 'op': 'is_set'},
        effect={
            'kind': 'percentage_relief',
            'base_field': 'confirmed_tuition',
            'threshold_section': 'dggr_extra_tuition', 'threshold_key': 'threshold_per_semester',
            'percent_section': 'dggr_extra_tuition', 'percent_key': 'max_percent_covered',
            'cap_section': 'dggr_extra_tuition', 'cap_key': 'max_per_semester',
            'inclusive_of': ['dggr_tuition_top_up'],
        },
    ),

    # ── Living allowance: additive across streams ──
    dict(
        code='psssp_living',
        description='PSSSP living allowance for each month of study',
        category=Award.Category.LIVING,
        order=50,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.PSSSP],
        condition={'field': 'receives_sfa', 'op': 'ne', 'value': True},
        effect={'kind': 'rate_per_month', 'section': 'psssp_living', 'key': '{load}_{dependants}'},
    ),
    dict(
        code='ucepp_living',
        description='UCEPP living allowance for each month of study',
        category=Award.Category.LIVING,
        order=60,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.UCEPP],
        condition={'field': 'receives_sfa', 'op': 'ne', 'value': True},
        effect={'kind': 'rate_per_month', 'section': 'ucepp_living', 'key': '{load}_{dependants}'},
    ),
    dict(
        code='dggr_living',
        description='DGGR living allowance for each month of study',
        category=Award.Category.LIVING,
        order=70,
        applies_to_types=[ApplicationType.ADMISSION, ApplicationType.CONTINUING_FUNDING],
        applies_to_streams=[FundingStream.DGGR],
        effect={'kind': 'rate_per_month', 'section': 'dggr_living', 'key': '{load}_{dependants}'},
    ),

    # ── Books ──
    # There is no separate book allowance. §7(A) and §8(A) fund "mandatory books
    # and supplies ... including technology if it is required by the
    # institution" out of the same per-semester tuition cap as the tuition
    # itself. A flat $500 on top paid every student an amount the policy does
    # not describe, and paid it whether or not the tuition cap had already
    # covered the books.

    # ── One-time awards ──
    dict(
        code='graduation_bursary',
        description='Graduation bursary for the credential earned',
        category=Award.Category.BURSARY,
        order=100,
        applies_to_types=[ApplicationType.GRADUATION_BURSARY],
        condition={'field': 'credential', 'op': 'is_set'},
        effect={'kind': 'flat_rate', 'section': 'graduation_bursary', 'key': '{credential}'},
    ),
    dict(
        code='academic_scholarship',
        description='Academic scholarship by achievement band',
        category=Award.Category.SCHOLARSHIP,
        order=110,
        applies_to_types=[ApplicationType.ACADEMIC_SCHOLARSHIP],
        effect={
            'kind': 'tiered',
            'value_field': 'gpa_achieved',
            # Thresholds by rate key, not by literal. They were published as
            # editable rates *and* written in here, so the policy screen let an
            # administrator move a threshold that nothing read.
            'tiers': [
                {'at_least_key': 'high_threshold_percent',
                 'section': 'academic_scholarship', 'key': 'high_achievement_award'},
                {'at_least_key': 'mid_threshold_percent',
                 'section': 'academic_scholarship', 'key': 'mid_achievement_award'},
            ],
        },
    ),
    dict(
        code='travel_assistance',
        description='Travel assistance, capped by the purpose of travel and dependants',
        category=Award.Category.TRAVEL,
        order=130,
        applies_to_types=[ApplicationType.TRAVEL],
        effect={
            'kind': 'capped_request',
            'request_field': 'amount_requested',
            # §7(C) caps a trip at $2,000 without dependants and $3,500 with
            # them. Keyed on the purpose alone, a student with dependants was
            # capped at the same figure as one without — the policy's own
            # distinction had nowhere to live.
            'section': 'travel', 'key': 'max_{travel_purpose}_{dependants}',
        },
    ),
    # A flat rate, not a capped request: the form asks the employer what the
    # student did, never what the award should be. There is no figure to cap.
    dict(
        code='practicum_allowance',
        description='Summer student / practicum award, at the published rate',
        category=Award.Category.BURSARY,
        order=140,
        applies_to_types=[ApplicationType.PRACTICUM],
        effect={
            'kind': 'flat_rate',
            'section': 'practicum', 'key': 'allowance',
        },
    ),
    dict(
        code='emergency_relief',
        description='Emergency relief, up to the per-student cap',
        category=Award.Category.BURSARY,
        order=150,
        applies_to_types=[ApplicationType.EMERGENCY_RELIEF],
        effect={
            'kind': 'capped_request',
            'request_field': 'amount_requested',
            'section': 'emergency_relief', 'key': 'max_per_student',
        },
    ),
    dict(
        code='hardship_bursary',
        description='Hardship bursary, up to the per-student cap',
        category=Award.Category.BURSARY,
        order=120,
        applies_to_types=[ApplicationType.HARDSHIP_BURSARY],
        effect={
            'kind': 'capped_request',
            'request_field': 'amount_requested',
            'section': 'hardship_bursary', 'key': 'max_per_student',
        },
    ),
]


class Command(BaseCommand):
    help = 'Create the baseline funding rule set.'

    def add_arguments(self, parser):
        parser.add_argument('--publish', action='store_true',
                            help='Publish it, so applications are priced against it.')
        parser.add_argument('--effective-from', default=None,
                            help='ISO date the rule set takes effect (default: today).')

    @transaction.atomic
    def handle(self, *args, **options):
        effective_from = (
            date.fromisoformat(options['effective_from'])
            if options['effective_from'] else date.today()
        )

        version = (RuleSet.objects.filter(name=BASELINE)
                   .order_by('-version').values_list('version', flat=True).first() or 0) + 1

        rule_set = RuleSet.objects.create(
            name=BASELINE,
            version=version,
            effective_from=effective_from,
            notes='Baseline policy, transcribed from the original calculation service.',
        )

        for spec in RULES:
            Rule.objects.create(rule_set=rule_set, **spec)

        if options['publish']:
            # Close the previous version so exactly one set is in force at a time.
            RuleSet.objects.filter(
                name=BASELINE, status=RuleSet.Status.PUBLISHED, effective_to__isnull=True,
            ).exclude(pk=rule_set.pk).update(
                status=RuleSet.Status.SUPERSEDED, effective_to=effective_from,
            )
            rule_set.status = RuleSet.Status.PUBLISHED
            rule_set.published_at = timezone.now()
            rule_set.save(update_fields=['status', 'published_at'])

        self.stdout.write(self.style.SUCCESS(
            f'{rule_set} created with {len(RULES)} rules '
            f'({"published" if options["publish"] else "draft"}), '
            f'effective {effective_from}.'
        ))
