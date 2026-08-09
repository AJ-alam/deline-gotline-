"""
Management command to seed all DGG form templates into the database.
Run once after initial deployment:  python manage.py seed_forms

Forms are matched by title in API.submitApplication() on the frontend.
Titles must contain the form key (e.g. 'FormA', 'FormC') for fuzzy-match to work.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import Form, FormField

User = get_user_model()

FORMS = [
    {
        'key': 'FormA',
        'title': 'Form A — Admission Application',
        'description': 'Post-Secondary Student Support Program — initial funding application.',
        'program_title': 'C-DFN PSSSP',
        'fields': [
            'firstName', 'lastName', 'preferredName', 'phone', 'email', 'dob',
            'address', 'city', 'province', 'postalCode', 'sin', 'sex',
            'beneficiaryNo', 'studentId', 'institution', 'program',
            'semStart', 'semEnd', 'registrarEmail', 'registrarPhone',
            'tuition', 'accountHolder', 'transitNumber', 'instNumber',
            'accountNumber', 'signature', 'programStart', 'programEnd',
            'courseLoad', 'learningStyle', 'currentAddress', 'hasDependents',
            'dependentCount', 'semester', 'institutionLocation', 'bursaryStream',
            'Transcripts *', 'Letter of Intent *', 'Reference Letter',
            'Status Card *', 'Void Cheque *', 'Extra Docs',
        ],
    },
    {
        'key': 'FormC',
        'title': 'Form C — Continuing Funding Application',
        'description': 'Renewal / continuing student funding application.',
        'program_title': 'C-DFN PSSSP',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'dob', 'beneficiaryNo',
            'institution', 'program', 'semStart', 'semEnd', 'courseLoad',
            'semester', 'currentGPA', 'tuition', 'hasDependents', 'bursaryStream',
            'accountHolder', 'transitNumber', 'instNumber', 'accountNumber',
            'Transcripts *', 'Status Card *', 'signature',
        ],
    },
    {
        'key': 'FormD',
        'title': 'Form D — Appeal / Reconsideration',
        'description': 'Appeal or reconsideration of a funding decision.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'beneficiaryNo',
            'originalDecision', 'appealReason', 'additionalInfo', 'signature',
            'Supporting Documents',
        ],
    },
    {
        'key': 'FormE',
        'title': 'Form E — Travel Claim',
        'description': 'Travel reimbursement claim for academic travel.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'beneficiaryNo',
            'travelDate', 'travelFrom', 'travelTo', 'travelPurpose',
            'travelCost', 'accountHolder', 'transitNumber', 'instNumber',
            'accountNumber', 'signature', 'Receipts *',
        ],
    },
    {
        'key': 'FormF',
        'title': 'Form F — Practicum / Placement Allowance',
        'description': 'Allowance claim for practicum or work placement.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'institution', 'program',
            'practicumStart', 'practicumEnd', 'practicumLocation', 'supervisorName',
            'supervisorEmail', 'weeksCompleted', 'allowanceRequested',
            'accountHolder', 'transitNumber', 'instNumber', 'accountNumber',
            'signature', 'Placement Letter *',
        ],
    },
    {
        'key': 'FormG',
        'title': 'Form G — Graduation Bursary',
        'description': 'One-time bursary awarded upon program completion.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'beneficiaryNo',
            'institution', 'program', 'degreeType', 'graduationDate',
            'accountHolder', 'transitNumber', 'instNumber', 'accountNumber',
            'signature', 'Graduation Letter *', 'Transcript *',
        ],
    },
    {
        'key': 'FormH',
        'title': 'Form H — Emergency Relief',
        'description': 'Emergency financial relief for unexpected hardship.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'beneficiaryNo',
            'emergencyType', 'emergencyDescription', 'amountRequested',
            'accountHolder', 'transitNumber', 'instNumber', 'accountNumber',
            'signature', 'Supporting Documents',
        ],
    },
    {
        'key': 'AcademicScholarship',
        'title': 'Academic Scholarship — Merit Award',
        'description': 'Academic merit scholarship based on GPA.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'beneficiaryNo',
            'institution', 'program', 'gpa', 'currentSemester',
            'accountHolder', 'transitNumber', 'instNumber', 'accountNumber',
            'signature', 'Transcript *',
        ],
    },
    {
        'key': 'HardshipBursary',
        'title': 'Hardship Bursary — Financial Hardship',
        'description': 'Bursary for students experiencing financial hardship.',
        'program_title': 'DGGR Bursaries',
        'fields': [
            'firstName', 'lastName', 'email', 'phone', 'beneficiaryNo',
            'hardshipReason', 'amountRequested', 'supportingDetails',
            'accountHolder', 'transitNumber', 'instNumber', 'accountNumber',
            'signature', 'Supporting Documents',
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed all DGG form templates into the database.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Re-create forms even if they already exist')

    def handle(self, *args, **options):
        force = options['force']

        # Get or create a system admin user to set as form creator
        admin_user = User.objects.filter(role='admin').first()
        if not admin_user:
            admin_user = User.objects.filter(is_superuser=True).first()

        created_count = 0
        skipped_count = 0

        for form_def in FORMS:
            # Ensure program exists
            program, _ = Program.objects.get_or_create(
                title=form_def['program_title'],
                defaults={'description': form_def['program_title'], 'is_active': True}
            )

            # Check if form already exists
            existing = Form.objects.filter(title=form_def['title']).first()
            if existing and not force:
                self.stdout.write(f"  SKIP (exists): {form_def['title']}")
                skipped_count += 1
                continue

            if existing and force:
                existing.delete()

            form = Form.objects.create(
                title=form_def['title'],
                description=form_def['description'],
                program=program,
                purpose='application',
                is_active=True,
                created_by=admin_user,
            )

            for i, field_label in enumerate(form_def['fields']):
                field_type = 'file' if field_label.endswith('*') or field_label in (
                    'Supporting Documents', 'Receipts *', 'Placement Letter *',
                    'Graduation Letter *', 'Transcript *', 'Transcripts *',
                    'Letter of Intent *', 'Reference Letter', 'Status Card *',
                    'Void Cheque *', 'Extra Docs',
                ) else 'text'
                FormField.objects.create(
                    form=form,
                    label=field_label,
                    field_type=field_type,
                    is_required=field_label.endswith('*'),
                    order=i,
                )

            self.stdout.write(self.style.SUCCESS(f"  CREATED: {form_def['title']} ({len(form_def['fields'])} fields)"))
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created: {created_count}, Skipped: {skipped_count}"
        ))
