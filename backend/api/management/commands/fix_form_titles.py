"""
Management command to fix form titles in the database.
Renames old 'FormX - ...' titles to proper 'Form X — ...' format.

Usage:
    python manage.py fix_form_titles
"""
from django.core.management.base import BaseCommand
from forms.models import Form


TITLE_MAP = {
    'FormA - New Student Application':       'Form A — New Student Application',
    'FormB - Student Profile Update':        'Form B — Student Profile Update',
    'FormC - Travel Assistance':             'Form C — Continuing Funding Application',
    'FormC - Continuing Funding Application':'Form C — Continuing Funding Application',
    'FormD - Specialized Training':          'Form D — Specialized Training',
    'FormE - Emergency Funding':             'Form E — Emergency Funding',
    'FormF - Laptop & Tech Support':         'Form F — Practicum / Placement Support',
    'FormF - Practicum / Placement':         'Form F — Practicum / Placement Support',
    'FormG - Graduation Award':              'Form G — Graduation Bursary',
    'FormG - Graduation Bursary':            'Form G — Graduation Bursary',
    'FormH - Summer Student Employment':     'Form H — Summer Student Employment',
    'Scholarship - Academic Excellence':     'Academic Scholarship — Merit Award',
    'AcademicScholarship - Merit Award':     'Academic Scholarship — Merit Award',
    'AcademicScholarship — Merit Award':     'Academic Scholarship — Merit Award',
    'Hardship - Secondary Support':          'Hardship Bursary — Secondary Support',
}


class Command(BaseCommand):
    help = 'Fix form titles to use proper readable names'

    def handle(self, *args, **options):
        updated = 0
        for form in Form.objects.all():
            new_title = TITLE_MAP.get(form.title)
            if new_title and new_title != form.title:
                self.stdout.write(f'  "{form.title}"  →  "{new_title}"')
                form.title = new_title
                form.save(update_fields=['title'])
                updated += 1

        if updated:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Updated {updated} form title(s).'))
        else:
            self.stdout.write(self.style.WARNING('No titles needed updating.'))
