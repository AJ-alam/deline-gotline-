import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_policysetting_is_active_effective_date'),
        ('forms', '0015_submissionanswer_original_filename'),
    ]

    operations = [
        migrations.CreateModel(
            name='DirectorActionToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=64, unique=True)),
                ('action', models.CharField(choices=[('approve', 'Approve'), ('deny', 'Deny')], max_length=10)),
                ('reason', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('director', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('submission', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='director_tokens',
                    to='forms.formsubmission',
                )),
            ],
            options={'db_table': 'director_action_tokens'},
        ),
        migrations.CreateModel(
            name='FinanceConfirmToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('confirmed_by_name', models.CharField(blank=True, default='', max_length=255)),
                ('submission', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='finance_tokens',
                    to='forms.formsubmission',
                )),
            ],
            options={'db_table': 'finance_confirm_tokens'},
        ),
    ]
