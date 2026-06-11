import os
import sys

# Add the backend directory to the sys.path so we can import 'core'
path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if path not in sys.path:
    sys.path.append(path)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()

# Run pending migrations on cold start — idempotent, ~100ms if all applied.
# Ensures first deploy and future deploys apply schema changes automatically.
try:
    from django.core.management import call_command
    call_command('migrate', '--no-input', verbosity=0)
    # Seed reference data if tables are empty
    call_command('seed_forms', verbosity=0)
    call_command('seed_policies', verbosity=0)
except Exception:
    pass
