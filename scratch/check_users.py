import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

print("Checking users...")
for user in User.objects.all():
    print(f"Email: {user.email}, Role: {user.role}, IsActive: {user.is_active}")
