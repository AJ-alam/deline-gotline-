# Generated migration for MidSemesterChange, ApplicationDeadline, and FormSubmission deadline fields

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('forms', '0006_formsubmission_office_use_data'),
    ]

    operations = [
        # Add deadline fields to FormSubmission
        migrations.AddField(
            model_name='formsubmission',
            name='deadline_met',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='formsubmission',
            name='submitted_after_deadline',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='formsubmission',
            name='late_application_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='formsubmission',
            name='late_application_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_late_submissions', to=settings.AUTH_USER_MODEL),
        ),
        
        # Create MidSemesterChange model
        migrations.CreateModel(
            name='MidSemesterChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(choices=[('enrollment_status', 'Enrollment Status Change'), ('dependents', 'Dependents Change'), ('institution', 'Institution Change'), ('program', 'Program Change'), ('other', 'Other Change')], max_length=50)),
                ('old_value', models.TextField()),
                ('new_value', models.TextField()),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('recalculated_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_changes', to=settings.AUTH_USER_MODEL)),
                ('submitted_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submitted_changes', to=settings.AUTH_USER_MODEL)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mid_semester_changes', to='forms.formsubmission')),
            ],
            options={
                'ordering': ['-submitted_at'],
            },
        ),
        
        # Create ApplicationDeadline model
        migrations.CreateModel(
            name='ApplicationDeadline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('funding_stream', models.CharField(choices=[('PSSSP', 'C-DFN PSSSP'), ('UCEPP', 'C-DFN UCEPP'), ('DGGR', 'DGGR Bursaries')], max_length=50)),
                ('semester', models.CharField(max_length=50)),
                ('deadline_date', models.DateTimeField()),
                ('late_application_allowed', models.BooleanField(default=False)),
                ('late_application_deadline', models.DateTimeField(blank=True, null=True)),
                ('requires_director_approval', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-deadline_date'],
            },
        ),
        
        # Add unique constraint to ApplicationDeadline
        migrations.AlterUniqueTogether(
            name='applicationdeadline',
            unique_together={('funding_stream', 'semester')},
        ),
    ]
