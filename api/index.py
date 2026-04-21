import os
import sys

# Add the backend directory to the sys.path so we can import 'core'
path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if path not in sys.path:
    sys.path.append(path)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.wsgi import get_wsgi_application

# Export the handler for Vercel
app = get_wsgi_application()
