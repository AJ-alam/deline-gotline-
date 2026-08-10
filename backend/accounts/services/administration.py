"""Managing who can do what.

Changing a role grants or removes the power to decide funding and release money,
so this is the most sensitive surface in the portal after the rates themselves.
Three guards, all enforced here rather than in a view:

An administrator cannot demote or deactivate themselves. Locking the last person
with access out of the system is not recoverable through the portal.

The last administrator cannot be removed. An office with nobody able to grant
access has to go to a database console to recover.

Nobody is deleted. Decisions, events and audit entries name the person who made
them; removing the row would leave a funding decision signed by nobody. An
account is deactivated instead and keeps its history.
"""

from __future__ import annotations

import logging

from django.db import transaction

from accounts.models import Role, User
from funding.models import AuditEntry

logger = logging.getLogger(__name__)


class AdministrationError(Exception):
    """The change was refused."""


def _admin_count(exclude_pk=None) -> int:
    query = User.objects.filter(role=Role.ADMIN, is_active=True)
    if exclude_pk is not None:
        query = query.exclude(pk=exclude_pk)
    return query.count()


@transaction.atomic
def change_role(user: User, new_role: str, actor: User) -> User:
    if new_role not in Role.values:
        raise AdministrationError(f'{new_role!r} is not a role.')

    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.role == new_role:
        return locked

    if locked.pk == actor.pk and new_role != Role.ADMIN:
        raise AdministrationError(
            'You cannot remove your own administrator access. '
            'Ask another administrator to do it.'
        )
    if locked.role == Role.ADMIN and new_role != Role.ADMIN and _admin_count(locked.pk) == 0:
        raise AdministrationError(
            'This is the only administrator. Give someone else administrator '
            'access before changing this one.'
        )

    previous = locked.role
    locked.role = new_role
    # Admin-site access follows the role rather than being set separately, so
    # the two cannot disagree about who is privileged.
    locked.is_staff = new_role == Role.ADMIN
    locked.save(update_fields=['role', 'is_staff'])

    AuditEntry.objects.create(
        actor=actor, actor_role=actor.role, action='account.role_changed',
        detail=f'{locked.email}: {previous} → {new_role}',
    )
    logger.info('Role for %s changed %s → %s by %s',
                locked.email, previous, new_role, actor.email)
    return locked


@transaction.atomic
def set_active(user: User, is_active: bool, actor: User) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.is_active == is_active:
        return locked

    if not is_active:
        if locked.pk == actor.pk:
            raise AdministrationError('You cannot deactivate your own account.')
        if locked.role == Role.ADMIN and _admin_count(locked.pk) == 0:
            raise AdministrationError(
                'This is the only administrator. Give someone else administrator '
                'access before deactivating this one.'
            )

    locked.is_active = is_active
    locked.save(update_fields=['is_active'])

    AuditEntry.objects.create(
        actor=actor, actor_role=actor.role,
        action='account.activated' if is_active else 'account.deactivated',
        detail=locked.email,
    )
    return locked


def directory(search: str = '', role: str = '', include_inactive: bool = False):
    """Everyone with an account, for the people who administer them."""
    query = User.objects.all()
    if not include_inactive:
        query = query.filter(is_active=True)
    if role:
        query = query.filter(role=role)
    if search:
        from django.db.models import Q
        query = query.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(beneficiary_number__icontains=search)
        )
    return query.order_by('last_name', 'first_name')
