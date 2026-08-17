"""Report anything that would make an award total read wrongly.

    python manage.py check_awards

Read-only. Written after a student approved once for $2,000 was shown $4,000:
a decision supersedes rather than overwrites, its award lines are kept, and the
sums did not say which decision they meant. The sums are scoped now — see
`Award.objects.current()` — so this exists to say whether a given database was
affected and by how much, not to repair anything. Nothing needs repairing: the
superseded lines are history and are simply no longer counted.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from funding.models import Application, Award, AwardDecision

ZERO = Decimal('0.00')


class Command(BaseCommand):
    help = 'Report applications priced more than once, and any orphaned awards.'

    def handle(self, *args, **options):
        repriced = (Application.objects
                    # Not named `decisions`: that is the related name, and annotating
                    # over it collides.
                    .annotate(times_priced=Count('decisions'))
                    .filter(times_priced__gt=1)
                    .order_by('pk'))

        self.stdout.write(self.style.MIGRATE_HEADING('Applications priced more than once'))
        if not repriced.exists():
            self.stdout.write('  none')
        for application in repriced:
            current = (Award.objects.current()
                       .filter(application=application)
                       .aggregate(total=Sum('amount'))['total']) or ZERO
            everything = (Award.objects
                          .filter(application=application)
                          .aggregate(total=Sum('amount'))['total']) or ZERO
            who = application.student.full_name if application.student else 'guest'
            self.stdout.write(
                f'  #{application.pk}  {who}  {application.get_type_display()}\n'
                f'      priced {application.times_priced} times; '
                f'awarded {current}, and would have read {everything} before the fix'
            )

        self.stdout.write(self.style.MIGRATE_HEADING('\nAwards with no decision behind them'))
        orphans = Award.objects.filter(decision__isnull=True)
        if not orphans.exists():
            self.stdout.write('  none')
        for award in orphans:
            self.stdout.write(
                f'  award {award.pk} on application {award.application_id}: '
                f'{award.amount} ({award.status})')

        self.stdout.write(self.style.MIGRATE_HEADING('\nTotals'))
        live = Award.objects.current().aggregate(total=Sum('amount'))['total'] or ZERO
        every = Award.objects.aggregate(total=Sum('amount'))['total'] or ZERO
        paid = Award.objects.paid().aggregate(total=Sum('amount'))['total'] or ZERO
        self.stdout.write(f'  awarded, current decisions   {live}')
        self.stdout.write(f'  every award row ever written {every}')
        self.stdout.write(f'  paid                         {paid}')
        self.stdout.write(
            f'  decisions: {AwardDecision.objects.count()} '
            f'({AwardDecision.objects.filter(is_current=True).count()} current)')

        if every != live:
            self.stdout.write(self.style.WARNING(
                f'\n  Before the fix these screens read {every} instead of {live}. '
                'Nothing needs repairing — the superseded lines are kept as '
                'history and are no longer counted.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n  Nothing here was ever double-counted.'))
