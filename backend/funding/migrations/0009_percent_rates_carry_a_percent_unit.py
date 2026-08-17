"""Rates measured in percent said they were measured in dollars.

Every PolicySetting was seeded with unit '$', so the policy screen published an
80% achievement threshold as '$80.00' — on the one screen where an
administrator changes what students are paid. The value was right and its unit
was not, which is the same class of fault as a label deciding an amount.

Applies to any database already filled. New rows get their unit from
`policy_admin.unit_for`.
"""

from django.db import migrations


def set_percent_units(apps, schema_editor):
    PolicySetting = apps.get_model('funding', 'PolicySetting')
    PolicySetting.objects.filter(key__contains='percent').update(unit='%')


def back_to_dollars(apps, schema_editor):
    PolicySetting = apps.get_model('funding', 'PolicySetting')
    PolicySetting.objects.filter(key__contains='percent').update(unit='$')


class Migration(migrations.Migration):

    dependencies = [
        ('funding', '0008_alter_application_type'),
    ]

    operations = [
        migrations.RunPython(set_percent_units, back_to_dollars),
    ]
