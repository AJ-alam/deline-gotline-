"""Report on the Application / FormSubmission split before migrating off it.

Read-only. Safe to run against production, and intended to be — the migration
path depends on whether any genuine pre-FormSubmission applications survive, or
whether every Application row is a shadow synthesized by the payment path.

    python manage.py audit_dual_model

An Application is classified as SYNTHESIZED when it carries no form_data of its
own and exists only to give Payment.application an FK target (see
calculation_service._resolve_or_create_application, which creates them already
marked approved). Anything with real form_data predates FormSubmission and holds
data that exists nowhere else.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from api.models import Application, Payment
from forms.models import FormSubmission


class Command(BaseCommand):
    help = "Report on Application vs FormSubmission overlap before consolidating them."

    def handle(self, *args, **options):
        out = self.stdout
        total_apps = Application.objects.count()
        total_subs = FormSubmission.objects.count()

        out.write(self.style.MIGRATE_HEADING("\n== Row counts =="))
        out.write(f"  FormSubmission          {total_subs}")
        out.write(f"  Application             {total_apps}")

        if total_apps == 0:
            out.write(self.style.SUCCESS(
                "\nNo Application rows. The model can be removed without a data migration."
            ))
            return

        # form_data is the discriminator: the synthesizer never populates it.
        with_data = Application.objects.exclude(
            Q(form_data__isnull=True) | Q(form_data__exact={})
        )
        genuine = with_data.count()
        synthesized = total_apps - genuine

        out.write(self.style.MIGRATE_HEADING("\n== Application provenance =="))
        out.write(f"  synthesized by payment path (no form_data)   {synthesized}")
        out.write(f"  carries its own form_data (pre-FormSubmission) {genuine}")

        out.write(self.style.MIGRATE_HEADING("\n== By form_type =="))
        for row in (Application.objects.values('form_type')
                    .annotate(n=Count('id')).order_by('-n')):
            out.write(f"  {row['form_type'] or '(blank)':<20} {row['n']}")

        out.write(self.style.MIGRATE_HEADING("\n== By status =="))
        for row in (Application.objects.values('status')
                    .annotate(n=Count('id')).order_by('-n')):
            out.write(f"  {row['status'] or '(blank)':<20} {row['n']}")

        # Payments are the reason the shadow table exists, so they decide how much
        # rewiring the migration has to do.
        out.write(self.style.MIGRATE_HEADING("\n== Payment linkage =="))
        out.write(f"  total payments                      {Payment.objects.count()}")
        out.write(f"  linked to a submission              "
                  f"{Payment.objects.filter(submission__isnull=False).count()}")
        out.write(f"  linked to an application            "
                  f"{Payment.objects.filter(application__isnull=False).count()}")
        orphaned = Payment.objects.filter(
            submission__isnull=True, application__isnull=False
        ).count()
        out.write(f"  application-only (needs remapping)  {orphaned}")
        out.write(f"  linked to neither                   "
                  f"{Payment.objects.filter(submission__isnull=True, application__isnull=True).count()}")

        # Students holding both shapes are where duplicate dashboard rows come from.
        dupes = 0
        for app in Application.objects.select_related('student').iterator():
            if not app.student_id:
                continue
            if FormSubmission.objects.filter(student_id=app.student_id).exists():
                dupes += 1
        out.write(self.style.MIGRATE_HEADING("\n== Duplicate exposure =="))
        out.write(f"  Applications whose student also has submissions  {dupes}")
        out.write("  (each of these renders as an extra staff dashboard row)")

        out.write(self.style.MIGRATE_HEADING("\n== Verdict =="))
        if genuine == 0:
            out.write(self.style.SUCCESS(
                "  Every Application is a synthesized shadow. They can be deleted\n"
                "  once payments are repointed at their submission — no data is lost."
            ))
        else:
            out.write(self.style.WARNING(
                f"  {genuine} Application row(s) hold form_data that exists nowhere\n"
                "  else. These must be converted into FormSubmission + SubmissionAnswer\n"
                "  rows before Application can be dropped."
            ))
        out.write("")
