import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import Form, FormField

User = get_user_model()

def seed_forms():
    print("Seeding full form set...")
    
    admin = User.objects.filter(role='admin').first()
    if not admin:
        print("Error: No admin user found. Run seed_data.py first.")
        return

    program = Program.objects.first()
    if not program:
        print("Error: No program found. Run seed_data.py first.")
        return

    forms_to_seed = [
        {
            'title': 'Form A - New Student Application',
            'description': 'Main admission form for the DGG Student Portal.',
            'purpose': 'application'
        },
        {
            'title': 'Form C - Continuing Student Application',
            'description': 'For returning students applying for a new semester.',
            'purpose': 'application'
        },
        {
            'title': 'Form D - Change of Information',
            'description': 'Notify DGG of changes to address, school, or banking.',
            'purpose': 'application'
        },
        {
            'title': 'Form E - Travel Assistance Claim',
            'description': 'Request reimbursement for travel expenses.',
            'purpose': 'application'
        },
        {
            'title': 'Form F - Summer / Practicum Award',
            'description': 'Application for practicum or summer work support.',
            'purpose': 'application'
        },
        {
            'title': 'Form G - Graduation Award',
            'description': 'Celebrate your completion with a DGG award.',
            'purpose': 'application'
        },
        {
            'title': 'Form H - Appeal',
            'description': 'Request review of an educational funding decision.',
            'purpose': 'application'
        },
        {
            'title': 'Academic Scholarship',
            'description': 'Merit-based funding for high achieving students.',
            'purpose': 'application'
        },
        {
            'title': 'Hardship Bursary',
            'description': 'Emergency financial support for unexpected needs.',
            'purpose': 'application'
        }
    ]

    for f_data in forms_to_seed:
        form, created = Form.objects.update_or_create(
            title=f_data['title'],
            defaults={
                'description': f_data['description'],
                'purpose': f_data['purpose'],
                'program': program,
                'created_by': admin,
                'is_active': True
            }
        )
        if created:
            print(f"Form created: {form.title}")
        else:
            print(f"Form updated: {form.title}")

    print("Form seeding completed!")

if __name__ == "__main__":
    seed_forms()
