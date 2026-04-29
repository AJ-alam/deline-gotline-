"""
Comprehensive DB fix command.
Run: python manage.py fix_db

Fixes:
1. Form titles — strips 'FormX —' prefix to proper 'Form X — Full Name'
2. Policy settings — adds all missing keys the calculation service expects
3. Ensures Form F and Form G exist with correct titles
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from forms.models import Form, FormField
from programs.models import Program
from api.models import PolicySetting
from decimal import Decimal

User = get_user_model()


# ── Form title corrections ─────────────────────────────────────────────────
FORM_TITLE_MAP = {
    # Current DB titles → Proper descriptive names
    'Form A — C-DFN PSSSP Application':          'C-DFN PSSSP — New Student Application',
    'Form A — New Student Application':           'C-DFN PSSSP — New Student Application',
    'Form B — Student Profile Update':            'Student Profile Update',
    'Form C — Continuing Funding Application':    'Continuing Funding Application',
    'Form D — Appeal / Reconsideration':          'Appeal & Reconsideration',
    'Form D — Specialized Training':              'Specialized Training Request',
    'Form E — Travel Claim':                      'Travel & Relocation Claim',
    'Form E — Emergency Funding':                 'Emergency Funding Request',
    'Form F — Practicum / Placement Allowance':   'Practicum & Placement Allowance',
    'Form G — Graduation Bursary':                'Graduation Bursary',
    'Form H — Emergency Relief':                  'Emergency Relief Fund',
    'Form H — Summer Student Employment':         'Summer Student Employment Award',
    'Academic Scholarship — Merit Award':         'Academic Scholarship — Merit Award',
    'Hardship Bursary — Financial Hardship':      'Hardship Bursary',
    # Legacy fallbacks
    'FormA — C-DFN PSSSP Application':            'C-DFN PSSSP — New Student Application',
    'FormA - New Student Application':            'C-DFN PSSSP — New Student Application',
    'FormB - Student Profile Update':             'Student Profile Update',
    'FormC — Continuing Funding Application':     'Continuing Funding Application',
    'FormC - Travel Assistance':                  'Continuing Funding Application',
    'FormD — Appeal / Reconsideration':           'Appeal & Reconsideration',
    'FormD - Specialized Training':               'Specialized Training Request',
    'FormE — Travel Claim':                       'Travel & Relocation Claim',
    'FormE - Emergency Funding':                  'Emergency Funding Request',
    'FormF — Practicum / Placement Allowance':    'Practicum & Placement Allowance',
    'FormF - Laptop & Tech Support':              'Practicum & Placement Allowance',
    'FormG — Graduation Bursary':                 'Graduation Bursary',
    'FormG - Graduation Award':                   'Graduation Bursary',
    'FormH — Emergency Relief':                   'Emergency Relief Fund',
    'FormH - Summer Student Employment':          'Summer Student Employment Award',
    'HardshipBursary — Financial Hardship':       'Hardship Bursary',
    'Hardship - Secondary Support':               'Hardship Bursary',
    'Scholarship - Academic Excellence':          'Academic Scholarship — Merit Award',
    'AcademicScholarship — Merit Award':          'Academic Scholarship — Merit Award',
}

# ── Full policy settings the calculation service needs ────────────────────
# Format: (section, field_key, field_label, value, unit)
REQUIRED_POLICIES = [
    # ── PSSSP Tuition ──────────────────────────────────────────────────────
    ('psssp_tuition', 'max_per_semester',           'Max Tuition Per Semester',             5000,   '$'),
    ('psssp_tuition', 'admin_fee',                  'Admin Fee %',                          10,     '%'),

    # ── PSSSP Living ───────────────────────────────────────────────────────
    ('psssp_living', 'monthly_base',                'Monthly Base Rate',                    1200,   '$'),
    ('psssp_living', 'dependent_rate',              'Additional Rate Per Dependent',        300,    '$'),
    ('psssp_living', 'fulltime_no_dependents',      'Full-Time, No Dependents (per month)', 1200,   '$'),
    ('psssp_living', 'fulltime_with_dependents',    'Full-Time, With Dependents (per month)',1700,  '$'),
    ('psssp_living', 'parttime_no_dependents',      'Part-Time, No Dependents (per month)', 720,    '$'),
    ('psssp_living', 'parttime_with_dependents',    'Part-Time, With Dependents (per month)',1020,  '$'),

    # ── PSSSP Travel ───────────────────────────────────────────────────────
    ('psssp_travel', 'max_trips',                   'Max Trips Per Year',                   2,      'trips'),
    ('psssp_travel', 'mileage_rate',                'Mileage Rate Per KM',                  0.55,   'per km'),
    ('psssp_travel', 'max_trips_per_year',          'Max Trips Per Year',                   2,      'trips'),
    ('psssp_travel', 'min_distance_km',             'Min Distance From Home (km)',           200,    'km'),
    ('psssp_travel', 'max_per_trip_no_dependents',  'Max Per Trip — No Dependents',         2000,   '$'),
    ('psssp_travel', 'max_per_trip_with_dependents','Max Per Trip — With Dependents',       3500,   '$'),

    # ── PSSSP Books ────────────────────────────────────────────────────────
    ('psssp_books', 'max_per_year',                 'Max Books Per Year',                   1500,   '$'),

    # ── PSSSP Graduation Travel ────────────────────────────────────────────
    ('psssp_graduation_travel', 'max_grant',        'Max Total Grant',                      1500,   '$'),
    ('psssp_graduation_travel', 'max_total',        'Max Total Bursary',                    5000,   '$'),
    ('psssp_graduation_travel', 'max_family_members','Max Family Members Covered',          2,      'people'),
    ('psssp_graduation_travel', 'max_hotel_per_night','Max Hotel Per Night',                350,    '$'),
    ('psssp_graduation_travel', 'max_hotel_nights', 'Max Hotel Nights',                    3,      'nights'),

    # ── UCEPP Tuition ──────────────────────────────────────────────────────
    ('ucepp_tuition', 'max_per_semester',           'Max Tuition Per Semester',             4000,   '$'),

    # ── UCEPP Living ───────────────────────────────────────────────────────
    ('ucepp_living', 'monthly_base',                'Monthly Base Rate',                    1000,   '$'),
    ('ucepp_living', 'fulltime_no_dependents',      'Full-Time, No Dependents (per month)', 700,    '$'),
    ('ucepp_living', 'fulltime_with_dependents',    'Full-Time, With Dependents (per month)',1000,  '$'),
    ('ucepp_living', 'parttime_no_dependents',      'Part-Time, No Dependents (per month)', 420,    '$'),
    ('ucepp_living', 'parttime_with_dependents',    'Part-Time, With Dependents (per month)',600,   '$'),

    # ── DGGR Tuition ───────────────────────────────────────────────────────
    ('dggr_tuition', 'max_per_semester',            'Max Tuition Per Semester',             6000,   '$'),
    ('dggr_tuition', 'fulltime_per_semester',       'Full-Time Per Semester',               1500,   '$'),
    ('dggr_tuition', 'parttime_per_semester',       'Part-Time Per Semester',               900,    '$'),

    # ── DGGR Extra Tuition ─────────────────────────────────────────────────
    ('dggr_extra_tuition', 'top_up_max',            'Top-Up Max',                           2000,   '$'),
    ('dggr_extra_tuition', 'annual_cap_all_students','Annual Cap (All Students Combined)',  36000,  '$'),
    ('dggr_extra_tuition', 'threshold_per_semester','Tuition Threshold Per Semester',       5000,   '$'),
    ('dggr_extra_tuition', 'threshold_per_year',    'Tuition Threshold Per Year',           15000,  '$'),
    ('dggr_extra_tuition', 'max_percent_covered',   'Max % of Tuition Covered',             25,     '%'),
    ('dggr_extra_tuition', 'max_per_semester',      'Max Bursary Per Semester',             4000,   '$'),
    ('dggr_extra_tuition', 'max_per_year',          'Max Bursary Per Year',                 12000,  '$'),

    # ── DGGR Living ────────────────────────────────────────────────────────
    ('dggr_living', 'monthly_base',                 'Monthly Base Rate',                    1500,   '$'),
    ('dggr_living', 'fulltime_no_dependents',       'Full-Time, No Dependents (per month)', 700,    '$'),
    ('dggr_living', 'fulltime_with_dependents',     'Full-Time, With Dependents (per month)',950,   '$'),
    ('dggr_living', 'parttime_no_dependents',       'Part-Time, No Dependents (per month)', 420,    '$'),
    ('dggr_living', 'parttime_with_dependents',     'Part-Time, With Dependents (per month)',570,   '$'),

    # ── DGGR Travel ────────────────────────────────────────────────────────
    ('dggr_travel', 'max_grant',                    'Max Travel Grant',                     2500,   '$'),

    # ── DGGR Practicum Award ───────────────────────────────────────────────
    ('dggr_practicum_award', 'award_amount',        'Practicum Award Amount',               1000,   '$'),
    ('dggr_practicum_award', 'application_deadline_months', 'Application Deadline (months after placement)', 6, 'months'),

    # ── DGGR Graduation Bursary (per credential) ───────────────────────────
    ('dggr_grad_bursary', 'bursary_amount',         'Default Bursary Amount',               500,    '$'),
    ('dggr_grad_bursary', 'high_school_diploma',    'High School Diploma',                  500,    '$'),
    ('dggr_grad_bursary', 'certificate',            'Certificate',                          1000,   '$'),
    ('dggr_grad_bursary', 'trades_certificate',     'Trades Certificate of Qualification',  2000,   '$'),
    ('dggr_grad_bursary', 'trades_journeyperson',   'Trades Journeyperson Licence',         3000,   '$'),
    ('dggr_grad_bursary', 'diploma',                'Diploma',                              2000,   '$'),
    ('dggr_grad_bursary', 'pilot_licence',          'Professional Pilot Licence',           3000,   '$'),
    ('dggr_grad_bursary', 'bachelors_degree',       'Bachelors Degree',                     3000,   '$'),
    ('dggr_grad_bursary', 'masters_degree',         'Masters Degree',                       4000,   '$'),
    ('dggr_grad_bursary', 'doctorate',              'Doctorate / PhD',                      5000,   '$'),

    # ── DGGR Academic Scholarship ──────────────────────────────────────────
    ('dggr_academic_scholarship', 'award_amount',   'Scholarship Award Amount',             2000,   '$'),
    ('dggr_academic_scholarship', 'gpa_threshold',  'Minimum GPA Required',                 3.5,    'GPA'),

    # ── DGGR Hardship ──────────────────────────────────────────────────────
    ('dggr_hardship', 'max_per_incident',           'Max Per Incident',                     1000,   '$'),

    # ── Application Deadlines ──────────────────────────────────────────────
    ('application_deadlines', 'fall_deadline',      'Fall Semester Deadline',               30,     'days before start'),
    ('application_deadlines', 'winter_deadline',    'Winter Semester Deadline',             30,     'days before start'),
    ('application_deadlines', 'summer_deadline',    'Summer Semester Deadline',             15,     'days before start'),
    ('application_deadlines', 'spring_deadline',    'Spring Semester Deadline',             15,     'days before start'),

    # ── Eligibility Rules ──────────────────────────────────────────────────
    ('eligibility_rules', 'max_years',              'Max Years of Funding',                 4,      'years'),
    ('eligibility_rules', 'min_gpa',                'Minimum GPA',                          2.0,    'GPA'),

    # ── Payment Schedule ───────────────────────────────────────────────────
    ('payment_schedule', 'payment_day',             'Payment Day of Month',                 15,     'th'),
    ('payment_schedule', 'payment_frequency',       'Payment Frequency',                    15,     'th of month'),
    ('payment_schedule', 'processing_days',         'Processing Days',                      10,     'business days'),

    # ── System Config ──────────────────────────────────────────────────────
    ('system_config', 'share_link_expiry_days',     'Share Link Expiry (days)',              7,      'days'),
    ('system_config', 'finance_email',              'Finance Department Email',             0,      'finance@deline.ca'),
    ('system_config', 'registrar_email',            'Registrar Email',                      0,      'registrar@institution.ca'),
]


class Command(BaseCommand):
    help = 'Fix form titles and ensure all required policy settings exist'

    def handle(self, *args, **options):
        self.fix_form_titles()
        self.ensure_forms_exist()
        self.fix_policy_settings()
        self.stdout.write(self.style.SUCCESS('\n✅ Database fix complete!'))

    def fix_form_titles(self):
        self.stdout.write('\n── Fixing form titles ──')
        updated = 0
        for form in Form.objects.all():
            new_title = FORM_TITLE_MAP.get(form.title)
            if new_title and new_title != form.title:
                self.stdout.write(f'  "{form.title}"  →  "{new_title}"')
                form.title = new_title
                form.save(update_fields=['title'])
                updated += 1
        if updated:
            self.stdout.write(self.style.SUCCESS(f'  Updated {updated} form title(s)'))
        else:
            self.stdout.write('  All form titles already correct')

    def ensure_forms_exist(self):
        self.stdout.write('\n── Ensuring Form F and Form G exist ──')
        admin = User.objects.filter(role='admin').first()
        program = Program.objects.first()
        if not program:
            self.stdout.write(self.style.WARNING('  No program found — skipping form creation'))
            return

        required_forms = [
            ('Practicum & Placement Allowance', 'application'),
            ('Graduation Bursary', 'application'),
        ]
        for title, purpose in required_forms:
            form, created = Form.objects.get_or_create(
                title=title,
                defaults={'program': program, 'purpose': purpose, 'created_by': admin, 'is_active': True}
            )
            if created:
                # Add declaration field
                FormField.objects.get_or_create(
                    form=form,
                    label='Declaration of Accuracy',
                    defaults={'field_type': 'checkbox', 'is_required': True, 'order': 99}
                )
                self.stdout.write(self.style.SUCCESS(f'  Created: {title}'))
            else:
                self.stdout.write(f'  Exists: {title}')

    def fix_policy_settings(self):
        self.stdout.write('\n── Ensuring all policy settings exist ──')
        created_count = 0
        skipped_count = 0

        for section, field_key, field_label, value, unit in REQUIRED_POLICIES:
            _, created = PolicySetting.objects.get_or_create(
                section=section,
                field_key=field_key,
                defaults={
                    'field_label': field_label,
                    'value': Decimal(str(value)),
                    'unit': unit,
                }
            )
            if created:
                self.stdout.write(f'  + {section}.{field_key} = {value} {unit}')
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'  Created {created_count} new policy settings, {skipped_count} already existed'
        ))
