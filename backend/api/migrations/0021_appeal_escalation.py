from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_director_action_token_finance_confirm_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='appeal',
            name='escalation_level',
            field=models.CharField(
                choices=[
                    ('director', 'Director of Education'),
                    ('dggr_official', 'Senior DGGR Official'),
                    ('ceo', 'CEO'),
                ],
                default='director',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='appeal',
            name='escalated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='appeal',
            name='escalation_notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='appeal',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('reviewing', 'Reviewing'),
                    ('decided', 'Decided'),
                    ('escalated', 'Escalated'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
