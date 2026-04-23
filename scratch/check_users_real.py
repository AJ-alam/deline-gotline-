import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import CustomUser

print("Listing all users:")
print("-" * 50)
for user in CustomUser.objects.all():
    print(f"Email: {user.email} | Role: {user.role} | Is Staff: {user.is_staff} | Is Superuser: {user.is_superuser}")
print("-" * 50)
