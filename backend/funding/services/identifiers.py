"""Government identifiers, kept out of everything that returns answers.

A Social Insurance Number is required for federal reporting, so the admission
application has to collect one. Where it must not end up is the `answers` JSON
column: that is returned whole by the application detail endpoint, printed on
the paper form, and copied into the enrolment verification sent to the
institution. One regulated identifier in that blob is readable by five staff
roles, by anyone with database access, and by a registrar who has no business
seeing it.

So it is split off at validation, encrypted, and written to its own table. What
comes back to any client is the last three digits and nothing else. Reading the
whole number is a deliberate act with its own audit entry — see `reveal`.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from funding.models import ApplicantIdentifier, AuditEntry


class IdentifierError(Exception):
    """The identifier could not be stored or read."""


def _key() -> bytes:
    """The encryption key, as Fernet wants it.

    An explicit FIELD_ENCRYPTION_KEY is what a deployment should set: it can
    then be rotated independently of SECRET_KEY, and rotating SECRET_KEY (which
    only invalidates sessions) does not silently make every stored SIN
    unreadable. Local and test runs derive one instead, so nothing has to be
    configured to run the suite.
    """
    configured = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if configured:
        return configured.encode() if isinstance(configured, str) else configured

    if not (settings.DEBUG or getattr(settings, 'TESTING', False)):
        raise ImproperlyConfigured(
            'FIELD_ENCRYPTION_KEY is not set. Refusing to encrypt government '
            'identifiers with a key derived from SECRET_KEY in a deployed '
            'process: rotating SECRET_KEY would make every stored number '
            'unreadable.'
        )

    derived = hashlib.sha256(f'field-encryption:{settings.SECRET_KEY}'.encode()).digest()
    return base64.urlsafe_b64encode(derived)


def store(application, kind: str, value: str, last_three: str = '') -> ApplicantIdentifier:
    """Encrypt and record one identifier against an application.

    `last_three` is what screens show. It defaults to the end of the value,
    which is right for a number; a caller storing something structured passes
    the three digits a person would actually recognise instead.
    """
    if not value:
        raise IdentifierError('No value to store.')

    token = Fernet(_key()).encrypt(value.encode())
    identifier, _ = ApplicantIdentifier.objects.update_or_create(
        application=application, kind=kind,
        defaults=dict(ciphertext=token.decode(),
                      last_three=(last_three or value[-3:])),
    )
    return identifier


def decrypt(identifier) -> str:
    """The stored value, for code that is moving it rather than showing it.

    No audit entry, because nothing is disclosed to anybody: this is used to
    carry held bank details from an application onto the account they belong
    to. Every path that puts a value in front of a person goes through
    `reveal`, which demands a reason and records it before returning anything.
    """
    try:
        return Fernet(_key()).decrypt(identifier.ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise IdentifierError(
            'The stored value could not be decrypted. The encryption key has '
            'changed since it was written.'
        ) from exc


def masked(application, kind: str = ApplicantIdentifier.Kind.SIN) -> str:
    """What a client is allowed to see: enough to recognise, not to use."""
    identifier = ApplicantIdentifier.objects.filter(
        application=application, kind=kind).first()
    return f'•••••{identifier.last_three}' if identifier else ''


def reveal(application, actor, reason: str,
           kind: str = ApplicantIdentifier.Kind.SIN) -> str:
    """The whole number, for the one person who needs it, on the record.

    Never called by a serializer. Reading a SIN is an act with a reason, and
    the audit entry is written before the value is returned so that a failure
    to record cannot produce an unlogged read.
    """
    identifier = ApplicantIdentifier.objects.filter(
        application=application, kind=kind).first()
    if identifier is None:
        raise IdentifierError('No identifier of that kind is stored.')
    if not reason.strip():
        raise IdentifierError('A reason is required to read a full identifier.')

    AuditEntry.objects.create(
        actor=actor, actor_role=getattr(actor, 'role', ''),
        action='identifier.revealed', application=application,
        detail=f'Read the full {kind.upper()} — {reason.strip()}',
    )

    try:
        return Fernet(_key()).decrypt(identifier.ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise IdentifierError(
            'The stored identifier could not be decrypted. The encryption key '
            'has changed since it was written.'
        ) from exc


