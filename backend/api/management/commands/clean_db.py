from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Wipe all transactional data from the database. '
        'Keeps: Form, FormField, Program, PolicySetting, ApplicationDeadline.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Required to execute. Without this flag the command is a dry-run.',
        )

    def _delete(self, label, qs):
        count = qs.count()
        if count:
            qs.delete()
        self.stdout.write(f'  {label:<35} {count:>6} rows deleted')
        return count

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                '\n'
                '  WARNING: PRODUCTION DATABASE WIPE\n'
                '  ──────────────────────────────────────────────────────\n'
                '  Deletes ALL users, applications, submissions, payments,\n'
                '  appeals, audit logs, notifications, and documents.\n\n'
                '  PRESERVED: Form, FormField, Program, PolicySetting,\n'
                '             ApplicationDeadline\n\n'
                '  Run with --confirm to proceed.\n'
            ))
            return

        from api.models import (
            AuditLog, PolicyHistory, Application, Document,
            UserDocument, Payment, Appeal, ShareableLink,
            DuplicateDetectionLog, Profile,
        )
        from forms.models import (
            FormSubmission, SubmissionAnswer, SubmissionNote,
            MidSemesterChange, FormBResponse,
        )
        from notifications.models import Notification
        from django.contrib.auth import get_user_model

        User = get_user_model()

        self.stdout.write('\nDeleting transactional data...\n')

        # Deepest dependents first
        self._delete('PolicyHistory',          PolicyHistory.objects.all())
        self._delete('AuditLog',               AuditLog.objects.all())
        self._delete('DuplicateDetectionLog',  DuplicateDetectionLog.objects.all())
        self._delete('FormBResponse',          FormBResponse.objects.all())
        self._delete('MidSemesterChange',      MidSemesterChange.objects.all())
        self._delete('SubmissionNote',         SubmissionNote.objects.all())
        self._delete('SubmissionAnswer',       SubmissionAnswer.objects.all())
        self._delete('ShareableLink',          ShareableLink.objects.all())
        self._delete('Payment',                Payment.objects.all())
        self._delete('Appeal',                 Appeal.objects.all())
        self._delete('Document',               Document.objects.all())
        self._delete('UserDocument',           UserDocument.objects.all())
        self._delete('FormSubmission',         FormSubmission.objects.all())
        self._delete('Application',            Application.objects.all())
        self._delete('Notification',           Notification.objects.all())
        self._delete('Profile',                Profile.objects.all())
        self._delete('CustomUser (all roles)', User.objects.all())

        self.stdout.write(self.style.SUCCESS(
            '\nDone. Static data (Forms, Programs, Policies, Deadlines) intact.\n'
        ))
