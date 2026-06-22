from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_application_finance_sent_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='policyhistory',
            name='setting',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='history',
                to='api.policysetting',
            ),
        ),
    ]
