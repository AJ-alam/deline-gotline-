import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import CustomUser

def create_director():
    email = 'director@deline.ca'
    if not CustomUser.objects.filter(email=email).exists():
        director = CustomUser.objects.create_user(
            email=email,
            password='director123',
            full_name='Education Director',
            role='director',
            is_staff=True
        )
        print(f"Director created: {email} / director123")
    else:
        print("Director already exists.")

if __name__ == "__main__":
    create_director()
