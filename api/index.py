"""Vercel serverless entrypoint for the Django application."""

import logging
import os
import sys

# Make 'core' importable from the backend directory.
path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.wsgi import get_wsgi_application

logger = logging.getLogger(__name__)

app = get_wsgi_application()

# Schema changes do not belong in a request path. `migrate` used to run on every
# cold start wrapped in `except Exception: pass`, which meant concurrent cold
# starts raced the same migration lock, every failure was invisible, and the
# first request after each scale-up paid for it.
#
# Migrations now run as a deploy step. RUN_BOOT_MIGRATE=1 remains as an escape
# hatch for environments with no deploy hook; failures are logged, never silenced.
if os.environ.get('RUN_BOOT_MIGRATE') == '1':
    try:
        from django.core.management import call_command
        call_command('migrate', '--no-input', verbosity=0)
        logger.info('Boot migrate completed.')
    except Exception:
        logger.exception('Boot migrate failed — the schema may be out of date.')
