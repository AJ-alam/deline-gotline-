"""Replace the rebuild's invented rates with the ones the policy prints.

The rates seeded during the rebuild were placeholders. Every one of them is
now set to the figure in the DGG Bursary & Awards Program Procedure, and the
ones the policy has no programme for are removed.

Each change is written as a `PolicyChange` as well, dated today, because that is
how every other rate edit is recorded and an award has to be explainable against
the rate that was in force when it was priced. `PolicyBook` reads history by
date, so applications already submitted keep the figures they were priced with:
this changes what happens next, not what happened.

Rates removed, with the reason:

  system_config.book_allowance   §7(A) and §8(A) fund mandatory books and
                                 supplies out of the same per-semester tuition
                                 cap as the tuition. A flat $500 on top was an
                                 amount the policy does not describe.
  travel.max_compassionate       There is no compassionate travel programme.
  travel.max_start_of_study      Superseded by the two dependants-aware keys;
  travel.max_end_of_study        §7(C) caps a trip at $2,000 without dependants
  travel.max_graduation          and $3,500 with them.
"""

from decimal import Decimal

from django.db import migrations
from django.utils import timezone

# (section, key, value, label). Mirrors seed_demo.RATES; kept as a literal here
# because a migration must not import code that will change under it.
POLICY_RATES = [
    ('psssp_tuition', 'max_per_semester', '5000.00',
     'PSSSP tuition, books and fees, per semester'),
    ('psssp_living', 'fulltime_no_dependents', '1200.00', 'PSSSP living, full-time, no dependants'),
    ('psssp_living', 'fulltime_with_dependents', '1700.00', 'PSSSP living, full-time, with dependants'),
    ('psssp_living', 'parttime_no_dependents', '720.00', 'PSSSP living, part-time, no dependants'),
    ('psssp_living', 'parttime_with_dependents', '1020.00', 'PSSSP living, part-time, with dependants'),

    ('ucepp_tuition', 'max_per_semester', '2000.00',
     'UCEPP tuition, books and fees, per semester'),
    ('ucepp_living', 'fulltime_no_dependents', '700.00', 'UCEPP living, full-time, no dependants'),
    ('ucepp_living', 'fulltime_with_dependents', '1000.00', 'UCEPP living, full-time, with dependants'),
    ('ucepp_living', 'parttime_no_dependents', '420.00', 'UCEPP living, part-time, no dependants'),
    ('ucepp_living', 'parttime_with_dependents', '600.00', 'UCEPP living, part-time, with dependants'),

    ('dggr_tuition', 'fulltime_per_semester', '1500.00', 'DGGR tuition top-up, full-time'),
    ('dggr_tuition', 'parttime_per_semester', '900.00', 'DGGR tuition top-up, part-time'),
    ('dggr_living', 'fulltime_no_dependents', '700.00', 'DGGR living, full-time, no dependants'),
    ('dggr_living', 'fulltime_with_dependents', '950.00', 'DGGR living, full-time, with dependants'),
    ('dggr_living', 'parttime_no_dependents', '420.00', 'DGGR living, part-time, no dependants'),
    ('dggr_living', 'parttime_with_dependents', '570.00', 'DGGR living, part-time, with dependants'),

    ('dggr_extra_tuition', 'threshold_per_semester', '5000.00',
     'Extra tuition bursary applies above this tuition'),
    ('dggr_extra_tuition', 'max_percent_covered', '25.00',
     'Share of tuition covered by the extra tuition bursary'),
    ('dggr_extra_tuition', 'max_per_semester', '4000.00',
     'Extra tuition bursary cap per semester, inclusive of the tuition top-up'),

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

    ('academic_scholarship', 'high_threshold_percent', '80.00', 'High achievement threshold'),
    ('academic_scholarship', 'mid_threshold_percent', '70.00', 'Mid achievement threshold'),
    ('academic_scholarship', 'high_achievement_award', '1000.00',
     'Achievement scholarship, 80% and above'),
    ('academic_scholarship', 'mid_achievement_award', '500.00',
     'Achievement scholarship, 70% to 79.99%'),

    ('practicum', 'allowance', '500.00', 'Summer student / practicum award'),
    ('hardship_bursary', 'max_per_student', '500.00', 'Hardship bursary cap'),

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
]

RETIRED = [
    ('system_config', 'book_allowance'),
    ('travel', 'max_compassionate'),
    ('travel', 'max_start_of_study'),
    ('travel', 'max_end_of_study'),
    ('travel', 'max_graduation'),
]


def apply_policy_rates(apps, schema_editor):
    PolicySetting = apps.get_model('funding', 'PolicySetting')
    PolicyChange = apps.get_model('funding', 'PolicyChange')

    # A database with no rates at all has never been seeded — a fresh install,
    # or the test database. Seeding one is `seed_demo`'s job, not a migration's,
    # and doing it here would silently change the baseline every test starts
    # from: rates would exist before a test had asked for any, so a test proving
    # what happens when a rate is *missing* would find one and pass for the
    # wrong reason. This migration corrects rates; it does not install them.
    if not PolicySetting.objects.exists():
        return

    today = timezone.now().date()

    for section, key, raw, label in POLICY_RATES:
        value = Decimal(raw)
        unit = '%' if 'percent' in key else '$'
        setting, created = PolicySetting.objects.get_or_create(
            section=section, key=key,
            defaults=dict(label=label, value=value, unit=unit),
        )
        if created:
            continue

        previous = setting.value
        setting.label, setting.unit = label, unit
        setting.value = value
        setting.save(update_fields=['label', 'unit', 'value', 'updated_at'])

        # A no-op edit is not history. `policy_admin.change_rate` refuses one
        # for the same reason.
        if previous != value:
            PolicyChange.objects.create(
                setting=setting, previous_value=previous, new_value=value,
                effective_date=today, changed_by=None,
            )

    # Retired rates go with their PolicyChange rows: the rule that read them is
    # gone too, so there is no decision left that either could explain.
    for section, key in RETIRED:
        PolicySetting.objects.filter(section=section, key=key).delete()


def unapply(apps, schema_editor):
    """Not reversible.

    Restoring the placeholder figures would mean pricing new applications with
    numbers the office never published. The rates screen is how a rate goes
    back, and it records who did it.
    """
    raise NotImplementedError(
        'Rates are changed through the policy screen, which records the change. '
        'This migration cannot restore the pre-policy placeholder figures.'
    )


class Migration(migrations.Migration):

    dependencies = [('funding', '0012_tidy_award_and_notice_leftovers')]

    operations = [migrations.RunPython(apply_policy_rates, unapply)]
