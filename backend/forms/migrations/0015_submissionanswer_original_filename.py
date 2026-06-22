from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0014_form_b_response'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionanswer',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
