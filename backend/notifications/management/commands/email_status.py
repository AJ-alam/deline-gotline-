"""What would happen if the portal tried to send mail right now.

    python manage.py email_status
    python manage.py email_status --send-test you@example.com

The assessment itself lives in `notifications.diagnostics.email_health` and is
shared with `GET /api/tasks/email-status/`, which is the only way to ask this
question of a serverless deployment — where nothing can run a management
command, and where the answer therefore mattered most. This file renders that
dict as text and decides nothing about it.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from notifications.diagnostics import email_health


class Command(BaseCommand):
    help = 'Report whether outbound email is configured and deliverable.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-test', metavar='ADDRESS',
            help='Send one real message to this address, bypassing the queue.',
        )

    def handle(self, *args, **options):
        health = email_health()
        problems = list(health['problems'])
        notes = list(health['notes'])

        delivery = health['delivery']
        self.stdout.write(self.style.MIGRATE_HEADING('Delivery'))
        self.stdout.write(f'  backend        {delivery["backend"]}')

        if delivery['kind'] == 'smtp':
            self.stdout.write(
                f'  host           {delivery["host"]}:{delivery["port"]}'
                f'  TLS={delivery["use_tls"]}')
            self.stdout.write(f'  username       {delivery["username"] or "(not set)"}')
            self.stdout.write(
                f'  password       {"set" if delivery["password_set"] else "(not set)"}')

        self.stdout.write(f'  from           {delivery["from_email"]}')

        links = health['links']
        self.stdout.write(self.style.MIGRATE_HEADING('\nLinks in outgoing mail'))
        self.stdout.write(f'  FRONTEND_URL   {links["frontend_url"] or "(not set)"}')
        self.stdout.write(f'  registrar link {links["registrar_link"] or "(nowhere)"}')

        queue = health['queue']
        self.stdout.write(self.style.MIGRATE_HEADING('\nQueue'))
        for key in ('pending', 'sent', 'failed'):
            self.stdout.write(f'  {key:<9}     {queue[key]}')
        if queue['oldest_pending_at']:
            self.stdout.write(f'  oldest        {queue["oldest_pending_at"]}')

        if options['send_test']:
            self.stdout.write(self.style.MIGRATE_HEADING('\nTest message'))
            try:
                message = EmailMultiAlternatives(
                    subject='DGG Student Funding — test message',
                    body='If you are reading this, outbound email works.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[options['send_test']],
                )
                message.send(fail_silently=False)
                self.stdout.write(self.style.SUCCESS(
                    f'  sent to {options["send_test"]}'))
            except Exception as exc:
                problems.append(f'Test send failed: {type(exc).__name__}: {exc}')

        self.stdout.write(self.style.MIGRATE_HEADING('\nVerdict'))
        for note in notes:
            self.stdout.write(self.style.WARNING(f'  note     {note}'))
        for problem in problems:
            self.stdout.write(self.style.ERROR(f'  problem  {problem}'))
        if not problems:
            self.stdout.write(self.style.SUCCESS('  Outbound email is deliverable.'))
