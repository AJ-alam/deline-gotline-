"""Awards already dispatched still said SENT_TO_FINANCE.

Dispatching the payment file now marks an award PAID. Rows dispatched before
that change kept the older status, so a student who was paid last term still
read $0.00 paid — the same wrong figure the change was made to fix, only for
history instead of for everything.

`sent_to_finance_at` is what identifies them: it is set by the payment run and
by nothing else, so a row carrying one has been through a dispatch. Rows without
one are left alone.
"""

from django.db import migrations


def dispatched_is_paid(apps, schema_editor):
    Award = apps.get_model('funding', 'Award')
    Award.objects.filter(
        status='sent_to_finance', sent_to_finance_at__isnull=False,
    ).update(status='paid')


def back_to_sent(apps, schema_editor):
    Award = apps.get_model('funding', 'Award')
    Award.objects.filter(
        status='paid', sent_to_finance_at__isnull=False,
    ).update(status='sent_to_finance')


class Migration(migrations.Migration):

    dependencies = [
        ('funding', '0009_percent_rates_carry_a_percent_unit'),
    ]

    operations = [
        migrations.RunPython(dispatched_is_paid, back_to_sent),
    ]
