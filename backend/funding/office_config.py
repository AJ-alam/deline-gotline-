"""The office's own configuration: what it pays, and by when.

Rates, published deadlines and the rule set that prices an application. This is
the part of a database that is *not* case data — `core.purge` keeps every row of
it when the applications are cleared out, and a fresh deployment needs it before
it can price anything at all.

It lives here rather than in `seed_demo` because the two are not the same job.
Demo data is accounts and applications for local work; this is the office's
published figures, and a production cut-over needs exactly one of those. Both
`seed_policies` and `seed_demo` read this module, so there is one copy of the
rate list: a second one is how a "$500 limit" came to sit beside a $3,000
seeded rate.

Migration 0013 carries the same figures as a literal, deliberately — a migration
must not import code that will change under it.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.utils import timezone

from funding.models import (
    ApplicationDeadline, FundingStream, PolicySetting, RuleSet,
)
from funding.services.policy_admin import unit_for


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

def install(stdout=None, style=None) -> dict:
    """Write the rates, the deadlines and a published rule set.

    Idempotent: every write is an update_or_create, and a rule set is published
    only when none is. Running it twice changes nothing, which is what lets a
    deploy hook call it unconditionally.

    It deliberately does **not** touch a rate that has been edited since —
    `update_or_create` resets it to the seeded figure. That is correct for a
    fresh database and wrong for a running one, so this is a cut-over tool:
    afterwards the policy screen is how a rate changes, because that records who
    changed it and when it takes effect.
    """
    def say(text):
        if stdout is not None:
            stdout.write(text)

    for section, key, value, label in RATES:
        PolicySetting.objects.update_or_create(
            section=section, key=key,
            defaults=dict(label=label, value=Decimal(value), unit=unit_for(key)),
        )
    say(f'  {len(RATES)} rates set')

    deadlines = _deadlines()
    for stream, semester, closes in deadlines:
        ApplicationDeadline.objects.update_or_create(
            stream=stream, academic_year=_academic_year(closes),
            semester=semester,
            defaults=dict(closes_at=closes, late_allowed=True),
        )
    say(f'  {len(deadlines)} deadlines set')

    published = RuleSet.objects.filter(status=RuleSet.Status.PUBLISHED).exists()
    if not published:
        # Backdated a year so an application filed today is priced by a rule set
        # that was already in force when it was submitted.
        call_command('seed_rules', '--publish', '--effective-from',
                     (date.today() - timedelta(days=365)).isoformat(), verbosity=0)
        say('  rule set published')
    else:
        say('  rule set already published')

    return {
        'rates': len(RATES),
        'deadlines': len(deadlines),
        'rule_set_published': not published,
    }
