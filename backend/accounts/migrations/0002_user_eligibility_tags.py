"""Save what the sign-up screening decided, instead of re-deriving it.

The streams a person qualifies for were recomputed on every application from
`is_indian_act_registered` and `is_deline_beneficiary`. Two of the answers the
decision actually rests on have no column — whether the programme is an
upgrading programme, and whether the person is already funded elsewhere — so the
recomputation could never produce UCEPP and could not honour either exclusion.

Existing accounts are backfilled from the two booleans, which is exactly what
they were already being given. Nobody's funding changes; they simply stop being
guessed at afresh each time.
"""

from django.db import migrations, models


def backfill(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.filter(eligible_streams=[]).iterator():
        streams = []
        if user.is_indian_act_registered:
            streams.append('psssp')
        if user.is_deline_beneficiary:
            streams.append('dggr')
        if streams:
            user.eligible_streams = streams
            user.save(update_fields=['eligible_streams'])


def unbackfill(apps, schema_editor):
    """Nothing to undo: the columns go with the tags."""


class Migration(migrations.Migration):

    dependencies = [('accounts', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='eligible_streams',
            field=models.JSONField(
                blank=True, default=list,
                help_text='FundingStream values this person qualified for at sign-up.'),
        ),
        migrations.AddField(
            model_name='user',
            name='eligibility_answers',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='The screening answers the streams above were decided from.'),
        ),
        migrations.AddField(
            model_name='user',
            name='eligibility_assessed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill, unbackfill),
    ]
