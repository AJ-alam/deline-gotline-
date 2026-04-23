from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0007_midsemesterchange_applicationdeadline_formsubmission_deadline'),
    ]

    operations = [
        migrations.AlterField(
            model_name='formsubmission',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('reviewed', 'Reviewed'),
                    ('forwarded', 'Forwarded to Director'),
                    ('accepted', 'Accepted'),
                    ('rejected', 'Rejected'),
                    ('more_info_required', 'More Info Required'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
