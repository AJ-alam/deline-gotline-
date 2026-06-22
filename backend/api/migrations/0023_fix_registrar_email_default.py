from django.db import migrations


def fix_registrar_email(apps, schema_editor):
    PolicySetting = apps.get_model('api', 'PolicySetting')
    test_emails = {'ajalam149@gmail.com', 'registrar@institution.ca', 'test@test.com'}
    qs = PolicySetting.objects.filter(section='system_config', field_key='registrar_email')
    for setting in qs:
        if setting.unit in test_emails:
            setting.unit = 'education.support@gov.deline.ca'
            setting.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0022_user_document_storage_scheme'),
    ]

    operations = [
        migrations.RunPython(fix_registrar_email, migrations.RunPython.noop),
    ]
