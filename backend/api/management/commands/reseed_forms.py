"""
Reseed all Programs and Forms.
Run: python manage.py reseed_forms

Safe to run multiple times — uses get_or_create so nothing is duplicated.
Does NOT touch users, submissions, or policy settings.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import Form, FormField

User = get_user_model()

FORMS = [
    {
        'title': 'Form A — Admission Application',
        'description': 'New student application for C-DFN Post-Secondary Student Support Program.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Date of Birth', 'date', True, 2),
            ('Beneficiary Number', 'text', True, 3),
            ('Treaty / SCN Number', 'text', True, 4),
            ('Phone Number', 'text', True, 5),
            ('Email Address', 'email', True, 6),
            ('Mailing Address', 'textarea', True, 7),
            ('Town / City', 'text', True, 8),
            ('Province / Territory', 'text', True, 9),
            ('Postal Code', 'text', True, 10),
            ('Institution Name', 'text', True, 11),
            ('Program of Study', 'text', True, 12),
            ('Credential Type', 'dropdown', True, 13),
            ('Enrollment Status', 'dropdown', True, 14),
            ('Course Load (%)', 'number', True, 15),
            ('Semester Start Date', 'date', True, 16),
            ('Semester End Date', 'date', True, 17),
            ('Tuition Amount', 'number', True, 18),
            ('Funding Stream', 'dropdown', True, 19),
            ('Has Dependents', 'dropdown', True, 20),
            ('Number of Dependents', 'number', False, 21),
            ('Bank Institution Number', 'text', True, 22),
            ('Bank Transit Number', 'text', True, 23),
            ('Bank Account Number', 'text', True, 24),
            ('SIN', 'text', False, 25),
            ('Proof of Enrollment', 'file', True, 26),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Form C — Continuing Funding Application',
        'description': 'Continuing student funding application for returning students.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Beneficiary Number', 'text', True, 2),
            ('Institution Name', 'text', True, 3),
            ('Program of Study', 'text', True, 4),
            ('Enrollment Status', 'dropdown', True, 5),
            ('Course Load (%)', 'number', True, 6),
            ('Semester Start Date', 'date', True, 7),
            ('Semester End Date', 'date', True, 8),
            ('Tuition Amount', 'number', True, 9),
            ('Funding Stream', 'dropdown', True, 10),
            ('Has Dependents', 'dropdown', True, 11),
            ('GPA / Transcript', 'file', True, 12),
            ('Proof of Enrollment', 'file', True, 13),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Form D — Appeal / Reconsideration',
        'description': 'Appeal form for reconsidering a funding decision.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Beneficiary Number', 'text', True, 2),
            ('Original Application Reference', 'text', True, 3),
            ('Reason for Appeal', 'textarea', True, 4),
            ('Supporting Documents', 'file', False, 5),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Form E — Travel Claim',
        'description': 'Travel assistance and relocation claim for eligible students.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Beneficiary Number', 'text', True, 2),
            ('Travel Purpose', 'dropdown', True, 3),
            ('Departure City', 'text', True, 4),
            ('Destination City', 'text', True, 5),
            ('Travel Date', 'date', True, 6),
            ('Return Date', 'date', False, 7),
            ('Estimated Distance (km)', 'number', False, 8),
            ('Travel Receipts', 'file', True, 9),
            ('Has Dependents', 'dropdown', True, 10),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Form F — Practicum / Placement Allowance',
        'description': 'Supervisor report for practicum or summer student placement award.',
        'purpose': 'application',
        'fields': [
            ('Organization Name', 'text', True, 1),
            ('Supervisor Title', 'text', True, 2),
            ('Student Name', 'text', True, 3),
            ('Placement Start Date', 'date', True, 4),
            ('Placement End Date', 'date', True, 5),
            ('Roles and Responsibilities', 'textarea', True, 6),
            ('Work Performance Summary', 'textarea', True, 7),
            ('Supervisor Signature', 'text', True, 8),
            ('Submission Date', 'date', True, 9),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Form G — Graduation Bursary',
        'description': 'One-time graduation bursary for successful program completion.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Date of Birth', 'date', True, 2),
            ('Treaty Number', 'text', True, 3),
            ('SIN', 'text', False, 4),
            ('Phone', 'text', True, 5),
            ('Email', 'email', True, 6),
            ('City', 'text', True, 7),
            ('Province', 'text', True, 8),
            ('Postal Code', 'text', True, 9),
            ('Institution', 'text', True, 10),
            ('Program', 'text', True, 11),
            ('Completion Date', 'date', True, 12),
            ('Credential', 'dropdown', True, 13),
            ('Bank Institution', 'text', True, 14),
            ('Bank Transit', 'text', True, 15),
            ('Bank Account', 'text', True, 16),
            ('Recipient Name', 'text', False, 17),
            ('Recipient Relationship', 'text', False, 18),
            ('Proof of Completion', 'file', True, 19),
            ('Student Signature', 'text', True, 20),
            ('Submission Date', 'date', True, 21),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Form H — Emergency Relief',
        'description': 'Emergency financial relief for students facing unexpected hardship.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Beneficiary Number', 'text', True, 2),
            ('Nature of Emergency', 'textarea', True, 3),
            ('Amount Requested', 'number', True, 4),
            ('Supporting Documents', 'file', False, 5),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Academic Scholarship — Merit Award',
        'description': 'Merit-based academic scholarship for high-achieving students.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Beneficiary Number', 'text', True, 2),
            ('Institution Name', 'text', True, 3),
            ('Program of Study', 'text', True, 4),
            ('GPA / Grade Average', 'number', True, 5),
            ('Academic Year', 'text', True, 6),
            ('Official Transcript', 'file', True, 7),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
    {
        'title': 'Hardship Bursary — Financial Hardship',
        'description': 'Financial hardship bursary for students in need.',
        'purpose': 'application',
        'fields': [
            ('Full Name', 'text', True, 1),
            ('Beneficiary Number', 'text', True, 2),
            ('Description of Hardship', 'textarea', True, 3),
            ('Amount Requested', 'number', True, 4),
            ('Supporting Documents', 'file', False, 5),
            ('Declaration of Accuracy', 'checkbox', True, 99),
        ]
    },
]


class Command(BaseCommand):
    help = 'Reseed all programs and forms (safe to run multiple times)'

    def handle(self, *args, **options):
        # Get or create admin user
        admin = User.objects.filter(role='admin').first() or User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.WARNING(
                'No admin user found. Create one first: python manage.py createsuperuser'
            ))
            return

        self.stdout.write(f'Using admin: {admin.email}')

        # Create program
        program, created = Program.objects.get_or_create(
            title="Deline Got'ı̨nę Government Education Program",
            defaults={
                'description': 'Primary education and student support program for Délı̨nę beneficiaries.',
                'created_by': admin,
                'is_active': True,
            }
        )
        self.stdout.write(
            self.style.SUCCESS(f'{"Created" if created else "Found"} program: {program.title}')
        )

        # Create forms and fields
        self.stdout.write('\nSeeding forms...')
        for form_data in FORMS:
            form, form_created = Form.objects.get_or_create(
                title=form_data['title'],
                defaults={
                    'description': form_data['description'],
                    'program': program,
                    'purpose': form_data['purpose'],
                    'created_by': admin,
                    'is_active': True,
                }
            )

            if form_created:
                # Create all fields for new forms
                for label, field_type, required, order in form_data['fields']:
                    # Add dropdown options where relevant
                    options = None
                    if label == 'Credential':
                        options = ['High School Diploma', 'Certificate', 'Trades Certificate',
                                   'Trades Journeyperson Licence', 'Diploma', 'Degree (Bachelors)',
                                   'Masters', 'Doctorate', 'Professional Pilot Licence']
                    elif label == 'Enrollment Status':
                        options = ['Full-Time', 'Part-Time']
                    elif label == 'Has Dependents':
                        options = ['Yes', 'No']
                    elif label == 'Funding Stream':
                        options = ['C-DFN PSSSP', 'UCEPP', 'DGGR']
                    elif label == 'Travel Purpose':
                        options = ['Start of Semester', 'End of Semester', 'Graduation', 'Other']
                    elif label == 'Credential Type':
                        options = ['Certificate', 'Diploma', 'Degree', 'Masters', 'Doctorate', 'Trades']

                    FormField.objects.create(
                        form=form,
                        label=label,
                        field_type=field_type,
                        is_required=required,
                        order=order,
                        options=options,
                    )
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ Created: {form.title} ({len(form_data["fields"])} fields)')
                )
            else:
                self.stdout.write(f'  — Exists:  {form.title}')

        self.stdout.write(self.style.SUCCESS('\n✅ Forms reseed complete!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('  python manage.py seed_policies   (if policies are empty)')
        self.stdout.write('  python manage.py createsuperuser (if you need a new admin)')
