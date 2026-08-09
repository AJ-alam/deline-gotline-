"""
Merge duplicate form templates into one canonical form per award type.

Phase-2 testing found Academic Scholarship and Hardship Bursary listed twice,
plus separate Form A variants for PSSSP / C-DFN. This command:

  1. Groups forms by canonical title (each group lists all known aliases).
  2. Keeps the form with the most submissions (ties -> oldest id).
  3. Repoints submissions from duplicates onto the keeper.
  4. Deactivates duplicates (never deletes: their FormFields are still
     referenced by existing FormAnswers) and suffixes their titles so future
     seed runs don't re-match them.
  5. Renames the keeper to the canonical title.

Idempotent — safe to run repeatedly.

Usage:
    python manage.py dedupe_forms          # dry run
    python manage.py dedupe_forms --apply  # write changes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from forms.models import Form, FormSubmission

# canonical title -> aliases seen across seed_forms / reseed_forms / manual edits
CANONICAL_GROUPS = {
    'Form A — Admission Application': [
        'FormA — C-DFN PSSSP Application',
        'Form A - Admission (PSSSP) Application',
        'Form A — New Student Application',
        'FormA - New Student Application',
        'C-DFN PSSSP — New Student Application',
    ],
    'Form C — Continuing Funding Application': [
        'FormC — Continuing Funding Application',
        'FormC - Continuing Funding Application',
        'FormC - Travel Assistance',
        'Continuing Funding Application',
    ],
    'Form D — Appeal / Reconsideration': [
        'FormD — Appeal / Reconsideration',
        'Appeal & Reconsideration',
    ],
    'Form E — Travel Claim': [
        'FormE — Travel Claim',
        'Travel & Relocation Claim',
    ],
    'Form F — Practicum / Placement Allowance': [
        'FormF — Practicum / Placement Allowance',
        'Form F — Practicum / Placement Support',
        'FormF - Practicum / Placement',
        'Practicum & Placement Allowance',
    ],
    'Form G — Graduation Bursary': [
        'FormG — Graduation Bursary',
        'FormG - Graduation Bursary',
        'FormG - Graduation Award',
        'Graduation Bursary',
    ],
    'Form H — Emergency Relief': [
        'FormH — Emergency Relief',
        'Form H - Emergency Relief Fund',
        'Emergency Relief Fund',
        'FormE - Emergency Funding',
    ],
    'Academic Scholarship — Merit Award': [
        'AcademicScholarship — Merit Award',
        'AcademicScholarship - Merit Award',
        'Scholarship - Academic Excellence',
    ],
    'Hardship Bursary — Financial Hardship': [
        'HardshipBursary — Financial Hardship',
        'Hardship Bursary',
        'Hardship - Secondary Support',
        'Hardship Bursary — Secondary Support',
    ],
}


class Command(BaseCommand):
    help = 'Merge duplicate form templates into one canonical form per award type'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write changes (default: dry run)')

    def handle(self, *args, **options):
        apply = options['apply']
        if not apply:
            self.stdout.write(self.style.WARNING('DRY RUN — pass --apply to write changes\n'))

        with transaction.atomic():
            for canonical, aliases in CANONICAL_GROUPS.items():
                titles = [canonical] + aliases
                forms = list(Form.objects.filter(title__in=titles).order_by('id'))
                if not forms:
                    continue

                # Keeper: most submissions wins, then oldest id
                keeper = max(forms, key=lambda f: (f.submissions.count(), -f.id))
                self.stdout.write(f'{canonical}:')
                self.stdout.write(f'  KEEP  #{keeper.id} "{keeper.title}" ({keeper.submissions.count()} submissions)')

                for f in forms:
                    if f.id == keeper.id:
                        continue
                    moved = f.submissions.count()
                    self.stdout.write(f'  MERGE #{f.id} "{f.title}" ({moved} submissions -> keeper), deactivate')
                    if apply:
                        FormSubmission.objects.filter(form=f).update(form=keeper)
                        f.is_active = False
                        f.title = f'{f.title} [retired #{f.id}]'
                        f.save(update_fields=['is_active', 'title'])

                if keeper.title != canonical or not keeper.is_active:
                    self.stdout.write(f'  RENAME keeper -> "{canonical}"')
                    if apply:
                        keeper.title = canonical
                        keeper.is_active = True
                        keeper.save(update_fields=['title', 'is_active'])

            if not apply:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('\nDone.' if apply else '\nDry run complete.'))
