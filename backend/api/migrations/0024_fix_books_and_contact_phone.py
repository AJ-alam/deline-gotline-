from django.db import migrations


def fix_policy_values(apps, schema_editor):
    """Apply client feedback to existing live policy data:
    - Books & Supplies allowance must NOT auto-apply ($500 phantom line);
      staff add it manually per student when applicable. Set to 0.
    - Public contact phone: drop the unused extension.
    """
    PolicySetting = apps.get_model('api', 'PolicySetting')

    PolicySetting.objects.filter(
        section='system_config', field_key='book_allowance'
    ).update(value=0)

    PolicySetting.objects.filter(
        section='system_config', field_key='contact_phone'
    ).update(unit='(867) 589-3515')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0023_fix_registrar_email_default'),
    ]

    operations = [
        migrations.RunPython(fix_policy_values, noop),
    ]
