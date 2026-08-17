"""Three leftovers a consistency sweep found in an existing database.

None of them can arise again — each has a writer now — but a database filled
before those writers existed still says the wrong thing, and the wrong thing is
what somebody reads.

  1. A superseded decision's unpaid lines stayed PENDING: "waiting to be paid",
     on money nothing will ever pay. `record_decision` cancels them now.
  2. Awards paid before the payment run assigned references carry none, so the
     file said `AWD-<primary key>` — the database's own counter, handed to a
     bank. Backfilled from the dispatch date, the same way the run builds one.
  3. Notices linking to an application that no longer exists send the person to
     a page that cannot load. The notice is kept — it still says what happened —
     and only the dead link is removed.
"""

from django.db import migrations


def tidy(apps, schema_editor):
    Award = apps.get_model('funding', 'Award')
    Application = apps.get_model('funding', 'Application')
    Notification = apps.get_model('notifications', 'Notification')

    Award.objects.filter(
        decision__is_current=False, status='pending',
    ).update(status='cancelled')

    for award in Award.objects.filter(status='paid').filter(reference__isnull=True):
        stamp = award.sent_to_finance_at
        award.reference = (f'DGG-{stamp:%Y%m%d}-{award.pk:06d}' if stamp
                           else f'DGG-{award.pk:06d}')
        award.save(update_fields=['reference'])

    live = set(Application.objects.values_list('pk', flat=True))
    for notice in Notification.objects.exclude(link='').exclude(link=None):
        tail = (notice.link or '').rsplit('/', 1)[-1]
        if notice.link.startswith('/applications/') and tail.isdigit():
            if int(tail) not in live:
                notice.link = ''
                notice.save(update_fields=['link'])


def backwards(apps, schema_editor):
    """Nothing to undo. Cancelling a line that nothing would pay, naming a
    payment that has already gone out, and removing a link to a page that does
    not exist are all corrections rather than changes of policy."""


class Migration(migrations.Migration):

    dependencies = [
        ('funding', '0011_alter_applicationevent_action'),
        ('notifications', '0003_alter_notification_kind'),
    ]

    operations = [
        migrations.RunPython(tidy, backwards),
    ]
