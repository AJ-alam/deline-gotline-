import os
import sys
import django
from pathlib import Path

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

serializer = TokenObtainPairSerializer()
print(f"Username field: {serializer.username_field}")
print(f"Fields: {list(serializer.fields.keys())}")
