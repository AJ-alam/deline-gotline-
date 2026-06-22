from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_policyhistory_setting_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='policysetting',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='policysetting',
            name='effective_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
