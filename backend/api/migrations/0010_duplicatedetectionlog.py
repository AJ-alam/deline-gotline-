# Generated migration for DuplicateDetectionLog model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0009_alter_policysetting_value'),
    ]

    operations = [
        migrations.CreateModel(
            name='DuplicateDetectionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_id', models.IntegerField(db_index=True)),
                ('identifier_hash', models.CharField(db_index=True, max_length=64)),
                ('is_flagged', models.BooleanField(default=False)),
                ('is_confirmed_duplicate', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='duplicatedetectionlog',
            index=models.Index(fields=['identifier_hash', 'is_flagged'], name='api_duplica_identif_idx'),
        ),
        migrations.AddIndex(
            model_name='duplicatedetectionlog',
            index=models.Index(fields=['submission_id'], name='api_duplica_submiss_idx'),
        ),
    ]
