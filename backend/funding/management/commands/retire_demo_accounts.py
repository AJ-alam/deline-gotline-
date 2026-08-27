"""Take the seeded demo accounts out of a real deployment.

`seed_demo` invents six people who share one password, and that password is
published in this repository. On a laptop that is fine and is the point. On a
public deployment it is a set of live credentials, and §10 of the handover says
plainly that it must not happen — yet `admin@dgg.test`, `director@dgg.test`,
`worker@dgg.test` and `finance@dgg.test` have been sitting on the production
database since it was first filled.

`purge_applications` deliberately never touches staff, so this was left to be
done by hand and therefore was not done at all. A command is the difference: it
can be run, re-run, and checked.

**Deactivated and locked, not deleted.** Nothing in this system deletes an
account: decisions, events and audit entries name the person who made them, and
removing the row leaves a funding decision signed by nobody. Deactivating stops
the login; the password is also rotated to an unguessable value so that
reactivating one later — by a person, in the People screen, months from now —
does not silently restore a published credential along with it.

    python manage.py retire_demo_accounts                 # report only
    python manage.py retire_demo_accounts --yes           # do it
    python manage.py retire_demo_accounts --yes --include-students

Students are left alone unless asked for: `student@dgg.test` may be the account
somebody is using to demonstrate the portal, and it can read only its own file.
The four staff accounts are the ones that can read other people's.
"""

from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User
from funding.models import AuditEntry

# Exactly what `seed_demo` creates. Matched on the address rather than on a
# domain pattern, so a real person who happens to use a `.test` address — or a
# staff account the office made by hand — is never caught by this.
STAFF = (
    'admin@dgg.test',
    'director@dgg.test',
    'worker@dgg.test',
    'finance@dgg.test',
)
STUDENTS = (
    'student@dgg.test',
    'student2@dgg.test',
)


class Command(BaseCommand):
    help = 'Deactivate and lock the seeded demo accounts on a real deployment.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help='Actually make the change. Without it this only reports.')
        parser.add_argument(
            '--include-students', action='store_true',
            help='Also retire student@dgg.test and student2@dgg.test.')

    def handle(self, *args, **options):
        wanted = list(STAFF) + (list(STUDENTS) if options['include_students'] else [])
        found = list(User.objects.filter(email__in=wanted).order_by('email'))

        if not found:
            self.stdout.write(self.style.SUCCESS(
                'No seeded demo accounts on this database. Nothing to do.'))
            return

        self.stdout.write('Seeded demo accounts on this database:\n')
        for person in found:
            state = 'active' if person.is_active else 'already inactive'
            self.stdout.write(f'  {person.email:24} {person.role:16} {state}')

        # The guard `administration.set_active` applies, restated here because
        # this command does not go through it: there is no actor to attribute
        # the change to, and the office must not be left unable to grant access.
        # A deployment whose *only* administrator is the seeded one has a
        # bigger problem than a published password, and locking it would turn
        # that into an outage.
        remaining_admins = (User.objects
                            .filter(role=Role.ADMIN, is_active=True)
                            .exclude(email__in=[p.email for p in found]))
        if not remaining_admins.exists():
            raise CommandError(
                'Refusing: no other active administrator would be left, so '
                'nobody could grant access afterwards. Create the office\'s own '
                'administrator first:\n'
                '    python manage.py createsuperuser'
            )
        self.stdout.write(
            f'\nAdministrators that remain: '
            f'{", ".join(remaining_admins.values_list("email", flat=True))}')

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                '\nReport only. Re-run with --yes to deactivate and lock these.'))
            return

        changed = []
        with transaction.atomic():
            for person in found:
                was_active = person.is_active
                person.is_active = False
                # Rotated as well as deactivated. Reactivating an account is a
                # thing a person does from the People screen without thinking
                # about its password, and the published one would come back
                # with it. A random value rather than `set_unusable_password`,
                # so `manage.py changepassword` still works on the row if the
                # office ever wants to hand one to a real person.
                person.set_password(secrets.token_urlsafe(48))
                person.save(update_fields=['is_active', 'password'])
                changed.append((person.email, was_active))

                AuditEntry.objects.create(
                    actor=None, actor_role='',
                    action='account.deactivated',
                    detail=(f'{person.email} — seeded demo account retired by '
                            f'manage.py retire_demo_accounts; password rotated'),
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nRetired {len(changed)} account(s). Their password is no longer '
            f'the published one, and none of them can sign in.'))
        self.stdout.write(
            'To give one back to a real person, change the address and set a '
            'password: manage.py changepassword <email>')
