import os
import django
import json

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import Form, FormField

User = get_user_model()

def seed():
    print("Seeding database...")
    
    # 1. Create Superuser (Admin)
    admin_email = 'admin@example.com'
    if not User.objects.filter(email=admin_email).exists():
        admin = User.objects.create_superuser(
            email=admin_email,
            password='password123',
            full_name='System Admin',
            role='admin'
        )
        print(f"Admin created: {admin_email}")
    else:
        admin = User.objects.get(email=admin_email)
        print("Admin already exists.")

    # 2. Create Student User
    student_email = 'student@example.com'
    if not User.objects.filter(email=student_email).exists():
        student = User.objects.create_user(
            email=student_email,
            password='password123',
            full_name='John Student',
            role='student'
        )
        print(f"Student created: {student_email}")
    else:
        student = User.objects.get(email=student_email)
        print("Student already exists.")

    # 3. Create a Program
    program, created = Program.objects.get_or_create(
        title='Computer Science Diploma',
        defaults={
            'description': 'A comprehensive program covering software development, networking, and security.',
            'created_by': admin
        }
    )
    if created:
        print(f"Program created: {program.title}")

    # 4. Create Forms
    forms_to_seed = [
        {
            'title': 'FormA - New Student Application',
            'description': 'Main admission form for the DGG Student Portal.',
            'purpose': 'application'
        },
        {
            'title': 'FormC - Travel Assistance',
            'description': 'Request for travel assistance and support.',
            'purpose': 'application'
        }
    ]

    for f_data in forms_to_seed:
        form, created = Form.objects.get_or_create(
            title=f_data['title'],
            program=program,
            defaults={
                'description': f_data['description'],
                'purpose': f_data['purpose'],
                'created_by': admin
            }
        )
        if created:
            print(f"Form created: {form.title}")
            
            # Add basic fields to FormA
            if 'FormA' in form.title:
                FormField.objects.create(form=form, label='Institutional Confirmation', field_type='checkbox', order=1)
                FormField.objects.create(form=form, label='Declaration', field_type='checkbox', order=2)
                print("Fields added to FormA.")

    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed()
