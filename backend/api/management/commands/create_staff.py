"""
Create admin or director accounts from the command line.

Usage:
    python manage.py create_staff
    python manage.py create_staff --email director@deline.ca --role director --name "Wajiha Shah" --password MyPass123
    python manage.py create_staff --email admin@deline.ca --role admin --name "John Admin" --password MyPass123
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

VALID_ROLES = ('admin', 'director')


class Command(BaseCommand):
    help = 'Create an admin or director staff account'

    def add_arguments(self, parser):
        parser.add_argument('--email',    type=str, help='Email address')
        parser.add_argument('--name',     type=str, help='Full name')
        parser.add_argument('--role',     type=str, choices=VALID_ROLES, help='Role: admin or director')
        parser.add_argument('--password', type=str, help='Password (prompted if not provided)')

    def handle(self, *args, **options):
        self.stdout.write('\n── Create Staff Account ──\n')

        # Collect inputs interactively if not passed as arguments
        email = options.get('email') or input('Email: ').strip()
        full_name = options.get('name') or input('Full Name: ').strip()

        role = options.get('role')
        while role not in VALID_ROLES:
            role = input(f'Role ({"/".join(VALID_ROLES)}): ').strip().lower()

        password = options.get('password')
        if not password:
            import getpass
            password = getpass.getpass('Password: ')
            confirm = getpass.getpass('Confirm Password: ')
            if password != confirm:
                self.stdout.write(self.style.ERROR('Passwords do not match.'))
                return

        # Validate
        if not email or '@' not in email:
            self.stdout.write(self.style.ERROR('Invalid email address.'))
            return
        if len(password) < 6:
            self.stdout.write(self.style.ERROR('Password must be at least 6 characters.'))
            return
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'User with email "{email}" already exists.'))
            update = input('Update password and name? (y/n): ').strip().lower()
            if update == 'y':
                user = User.objects.get(email=email)
                user.full_name = full_name
                user.role = role
                user.is_staff = True
                user.is_superuser = (role == 'admin')
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'\n✅ Updated: {email} | Role: {role}'))
            return

        # Create user
        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            is_staff=True,
            is_superuser=(role == 'admin'),
            is_active=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Created successfully!\n'
            f'   Email    : {user.email}\n'
            f'   Name     : {user.full_name}\n'
            f'   Role     : {user.role}\n'
            f'   Password : {"*" * len(password)}\n'
        ))
