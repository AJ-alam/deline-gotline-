"""Put the registrar's address into the renewals that were filed without one.

`continuing_funding` did not ask for `registrar_email` until now — it was
carried at send time from the student's profile or from an earlier application,
and never written down. That leaves every renewal already in a database with an
answer set its own schema now reports as incomplete, and `amend` re-cleans the
whole set: an administrator opening one to fix a typo would be told the
registrar email is missing, on a question the student was never asked.

So the address that *would* have been used is written onto the application,
which is where it now belongs. Same order the send-time lookup uses: the
student's profile first, then the most recent earlier application that carries
one. A renewal for which neither answers is left alone — there is nothing to
write, and inventing an address is how a request reaches the wrong institution.

Deliberately not importing `workflow.registrar_email_for`: a migration that
calls into live service code changes meaning when that code changes, and this
one has to keep describing what was true on the day it ran.
"""

from django.db import migrations


def carry_the_address_across(apps, schema_editor):
    Application = apps.get_model('funding', 'Application')
    EnrolmentProfile = apps.get_model('accounts', 'EnrolmentProfile')

    renewals = list(
        Application.objects
        .filter(type='continuing_funding')
        .order_by('id')
    )
    if not renewals:
        return

    # One query for the profiles rather than one per renewal.
    student_ids = {r.student_id for r in renewals if r.student_id}
    profiles = {
        profile.user_id: (profile.registrar_email or '').strip()
        for profile in EnrolmentProfile.objects.filter(user_id__in=student_ids)
    }

    for renewal in renewals:
        answers = dict(renewal.answers or {})
        if str(answers.get('registrar_email') or '').strip():
            continue
        if not renewal.student_id:
            continue

        carried = profiles.get(renewal.student_id, '')
        if not carried:
            earlier = (
                Application.objects
                .filter(student_id=renewal.student_id, submitted_at__isnull=False)
                .exclude(pk=renewal.pk)
                .order_by('-submitted_at', '-id')
                .values_list('answers', flat=True)
            )
            for older in earlier:
                found = str((older or {}).get('registrar_email') or '').strip()
                if found:
                    carried = found
                    break

        if not carried:
            continue

        answers['registrar_email'] = carried
        renewal.answers = answers
        renewal.save(update_fields=['answers'])


def leave_them_as_they_are(apps, schema_editor):
    """Nothing to undo.

    Removing the answer again would not restore the previous state — before
    this migration some renewals had no address to carry, and stripping the
    field from all of them cannot tell those apart from the ones it filled in.
    An answer that is now correct is not worth deleting to make a reversal
    tidy.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('funding', '0015_awardrepayment_reportedcost'),
        ('accounts', '0003_enrolmentprofile'),
    ]

    operations = [
        migrations.RunPython(carry_the_address_across, leave_them_as_they_are),
    ]
