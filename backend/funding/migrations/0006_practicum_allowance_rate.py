"""Rename the practicum rate: `max_allowance` → `allowance`.

The summer student / practicum award stopped asking the claimant for an amount,
so there is nothing left to cap. The rule that prices it became a `flat_rate`
reading `practicum:allowance`, and a setting nothing reads under a name nothing
looks for is how an award silently prices at zero — `PolicySetting` deliberately
refuses to answer a missing rate rather than returning one.

Carries the office's figure across rather than seeding a new default, so a
database where the cap was edited keeps the edited number.
"""

from django.db import migrations


def rename_forwards(apps, schema_editor):
    _rename(apps, 'max_allowance', 'allowance',
            'Summer student / practicum award')


def rename_backwards(apps, schema_editor):
    _rename(apps, 'allowance', 'max_allowance',
            'Practicum placement allowance cap')


def _rename(apps, old_key, new_key, label):
    PolicySetting = apps.get_model('funding', 'PolicySetting')
    rows = PolicySetting.objects.filter(section='practicum', key=old_key)
    # A database that already carries the destination is left alone: the unique
    # constraint on (section, key) would refuse the rename, and the row that is
    # already there is the one being read.
    if not rows.exists() or PolicySetting.objects.filter(
            section='practicum', key=new_key).exists():
        return
    rows.update(key=new_key, label=label)


class Migration(migrations.Migration):

    dependencies = [('funding', '0005_alter_application_type')]

    operations = [migrations.RunPython(rename_forwards, rename_backwards)]
