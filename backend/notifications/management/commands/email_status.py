"""What would happen if the portal tried to send mail right now.

    python manage.py email_status
    python manage.py email_status --send-test you@example.com

The enrolment verification is the one message the whole tuition path depends
on: until the registrar opens their link, no tuition can be confirmed and no
application can be forwarded. It is queued on commit and delivered by a
separate worker, which means it can fail silently in three different places —
credentials not set, the worker never run, or the link pointing at a frontend
that is not there.

This reports all three, rather than leaving them to be discovered by a
registrar who never received anything.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.console import EmailBackend as ConsoleBackend
from django.core.mail.backends.locmem import EmailBackend as LocmemBackend
from django.core.management.base import BaseCommand

from notifications.models import OutboundEmail


def _kind(backend_path: str) -> str:
    """Which family the configured backend belongs to.

    By class rather than by dotted path: the local console backend here is a
    subclass that writes UTF-8, and matching on the path reported it as SMTP
    and complained about credentials it does not need.
    """
    try:
        connection = get_connection(backend=backend_path, fail_silently=True)
    except Exception:
        return 'unknown'
    if isinstance(connection, LocmemBackend):
        return 'locmem'
    if isinstance(connection, ConsoleBackend):
        return 'console'
    return 'smtp'


class Command(BaseCommand):
    help = 'Report whether outbound email is configured and deliverable.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-test', metavar='ADDRESS',
            help='Send one real message to this address, bypassing the queue.',
        )

    def handle(self, *args, **options):
        problems = []
        notes = []

        backend = settings.EMAIL_BACKEND
        self.stdout.write(self.style.MIGRATE_HEADING('Delivery'))
        self.stdout.write(f'  backend        {backend}')

        kind = _kind(backend)
        if kind == 'console':
            notes.append(
                'The console backend prints mail to the terminal running the '
                'worker instead of sending it. Fine for local work; nothing '
                'reaches a real registrar.'
            )
        elif kind == 'locmem':
            problems.append('The locmem backend discards mail. It is for tests only.')
        else:
            self.stdout.write(f'  host           {settings.EMAIL_HOST}:{settings.EMAIL_PORT}'
                              f'  TLS={settings.EMAIL_USE_TLS}')
            self.stdout.write(f'  username       {settings.EMAIL_HOST_USER or "(not set)"}')
            self.stdout.write(f'  password       {"set" if settings.EMAIL_HOST_PASSWORD else "(not set)"}')
            if not settings.EMAIL_HOST_USER:
                problems.append('EMAIL_HOST_USER is not set, so SMTP cannot authenticate.')
            if not settings.EMAIL_HOST_PASSWORD:
                problems.append('EMAIL_HOST_PASSWORD is not set, so SMTP cannot authenticate.')

        self.stdout.write(f'  from           {settings.DEFAULT_FROM_EMAIL}')

        # ── The link inside the message ──
        self.stdout.write(self.style.MIGRATE_HEADING('\nLinks in outgoing mail'))
        frontend = getattr(settings, 'FRONTEND_URL', '')
        self.stdout.write(f'  FRONTEND_URL   {frontend or "(not set)"}')
        self.stdout.write(f'  registrar link {frontend}/enrolment/<token>')
        if not frontend:
            problems.append(
                'FRONTEND_URL is not set, so the registrar link has no host and '
                'the enrolment form cannot be opened.'
            )
        else:
            host = urlparse(frontend).hostname or ''
            if host in ('localhost', '127.0.0.1'):
                notes.append(
                    'FRONTEND_URL points at this machine. A registrar elsewhere '
                    'cannot open that link — set it to the deployed address '
                    'before anyone outside the office is emailed.'
                )

        # ── The queue ──
        self.stdout.write(self.style.MIGRATE_HEADING('\nQueue'))
        counts = {status: OutboundEmail.objects.filter(status=status).count()
                  for status, _ in OutboundEmail.Status.choices}
        for status, count in counts.items():
            self.stdout.write(f'  {status:<9}     {count}')

        if counts.get('pending') and not counts.get('sent'):
            problems.append(
                f"{counts['pending']} messages are queued and none has ever been "
                'sent. Nothing drains the queue automatically — run '
                '`python manage.py send_queued_emails` on a schedule.'
            )
        failed = OutboundEmail.objects.filter(status=OutboundEmail.Status.FAILED).first()
        if failed:
            problems.append(f'Last failure: {failed.last_error}')

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
