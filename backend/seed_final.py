import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import Form, FormField
from api.models import PolicySetting

User = get_user_model()

def seed():
    print("Seeding full form library...")
    
    admin = User.objects.filter(role='admin').first()
    if not admin:
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='password123',
            full_name='System Admin',
            role='admin'
        )

    program, _ = Program.objects.get_or_create(
        title='Deline Got’ı̨nę Government Education Program',
        defaults={'description': 'Primary education and student support program.', 'created_by': admin}
    )

    forms_to_seed = [
        {'title': 'FormA - New Student Application', 'purpose': 'application'},
        {'title': 'FormB - Student Profile Update', 'purpose': 'application'},
        {'title': 'FormC - Travel Assistance', 'purpose': 'application'},
        {'title': 'FormD - Specialized Training', 'purpose': 'application'},
        {'title': 'FormE - Emergency Funding', 'purpose': 'application'},
        {'title': 'FormF - Laptop & Tech Support', 'purpose': 'application'},
        {'title': 'FormG - Graduation Award', 'purpose': 'application'},
        {'title': 'FormH - Summer Student Employment', 'purpose': 'application'},
        {'title': 'Scholarship - Academic Excellence', 'purpose': 'application'},
        {'title': 'Hardship - Secondary Support', 'purpose': 'application'},
    ]

    for f_data in forms_to_seed:
        form, created = Form.objects.update_or_create(
            title=f_data['title'],
            program=program,
            defaults={
                'purpose': f_data['purpose'],
                'created_by': admin,
                'is_active': True
            }
        )
        # Ensure at least one field exists for the declaration
        FormField.objects.get_or_create(
            form=form,
            label='Declaration of Accuracy',
            defaults={'field_type': 'checkbox', 'is_required': True, 'order': 99}
        )
        print(f"{'Created' if created else 'Updated'} Form: {form.title}")

    print("Seeding Policy Settings...")
    policies = [
        {
            'category': 'tuition',
            'data': [
                {'stream': 'C-DFN PSSSP', 'desc': 'Full-time University/College', 'amt': '5000', 'notes': 'Per semester limit', 'color': '#1a6b3a'},
                {'stream': 'DGGR', 'desc': 'Graduate Studies (Masters/PhD)', 'amt': '8000', 'notes': 'Per semester limit', 'color': '#111'},
                {'stream': 'UCEPP', 'desc': 'University Preparation', 'amt': '3500', 'notes': 'Max 2 semesters', 'color': '#cc3333'}
            ]
        },
        {
            'category': 'living',
            'data': {
                'effectiveDate': '2026-01-01',
                'sections': [
                    {
                        'title': 'SOUTHERN ALLOWANCES (EDMONTON/CALGARY)',
                        'tag': 'ZONE 1',
                        'data': [
                            {'enroll': 'Full-Time', 'noDep': '1550', 'withDep': '2250', 'notes': 'Standard rate'},
                            {'enroll': 'Part-Time', 'noDep': '0', 'withDep': '0', 'notes': 'Books/Tuition only'}
                        ]
                    },
                    {
                        'title': 'NORTHERN ALLOWANCES (YELLOWKNIFE/INUVIK)',
                        'tag': 'ZONE 2',
                        'data': [
                            {'enroll': 'Full-Time', 'noDep': '1950', 'withDep': '2650', 'notes': 'High cost of living adj.'}
                        ]
                    }
                ]
            }
        },
        {
            'category': 'travel',
            'data': [
                {
                    'title': 'KILOMETRIC RATES',
                    'tag': 'Standard',
                    'data': [
                        {'param': 'Personal Vehicle (High)', 'value': '0.62', 'notes': 'Per km rate'},
                        {'param': 'Personal Vehicle (Low)', 'value': '0.45', 'notes': 'Summer rate'}
                    ]
                },
                {
                    'title': 'INCIDENTALS & MEALS',
                    'tag': 'Per Diem',
                    'data': [
                        {'param': 'Daily Incidental', 'noDep': '17.30', 'withDep': '17.30', 'notes': 'CAD'},
                        {'param': 'Full Day Meal Rate', 'noDep': '112.50', 'withDep': '112.50', 'notes': 'Breakfast/Lunch/Dinner'}
                    ]
                }
            ]
        },
        {
            'category': 'extraTuition',
            'data': {
                'effectiveDate': '2026-01-01',
                'params': [
                    {'param': 'Book Allowance', 'val': '1000', 'unit': 'per sem', 'notes': 'Auto-applied'},
                    {'param': 'Lab Fees / Equipment', 'val': '500', 'unit': 'max', 'notes': 'Requires receipt'}
                ]
            }
        },
        {
            'category': 'onetime',
            'data': [
                {
                    'title': 'GRADUATION AWARDS',
                    'tag': 'One-Time',
                    'data': [
                        {'type': 'Certificate/Diploma', 'amt': '500', 'notes': 'Paid upon completion'},
                        {'type': 'Bachelors Degree', 'amt': '1500', 'notes': 'Paid upon convocation'}
                    ]
                }
            ]
        },
        {
            'category': 'deadlines',
            'data': [
                {'sem': 'Fall', 'deadline': 'July 15', 'notes': 'September Start'},
                {'sem': 'Winter', 'deadline': 'Nov 15', 'notes': 'January Start'},
                {'sem': 'Spring', 'deadline': 'April 15', 'notes': 'May Start'}
            ]
        },
        {
            'category': 'timing',
            'data': '15'
        }
    ]

    for p in policies:
        PolicySetting.objects.update_or_create(
            category=p['category'],
            defaults={'data': p['data']}
        )
        print(f"Policy Seeded: {p['category']}")

    print("Form library and Policy seeding complete!")

if __name__ == "__main__":
    seed()
