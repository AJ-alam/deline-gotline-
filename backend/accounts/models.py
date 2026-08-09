"""People who use the portal.

Replaces CustomUser (40 fields) plus a separate Profile that duplicated eight of
them. Two models held the same facts, and code read from whichever one it
happened to know about.

What is here is what stays true of a person between applications. What is not
here is anything that describes a moment in someone's studies — institution,
program, course load, semester, enrollment status. Those change every term and
belong to the application that claims them. Keeping them on the user is why
award calculation quietly fell back to `student.enrollment_status` when an
answer was missing, mixing this year's facts into last year's decision.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Role(models.TextChoices):
    """What someone does here.

    Not named STAFF: Django's `is_staff` already means 'may open the admin site',
    and one model carrying two unrelated meanings of the same word is how the
    previous codebase became unreadable.
    """

    STUDENT = 'student', 'Student'
    SUPPORT_WORKER = 'support_worker', 'Student Support Worker'
    DIRECTOR = 'director', 'Director'
    FINANCE = 'finance', 'Finance'
    ADMIN = 'admin', 'Administrator'


class UserManager(BaseUserManager):
    """Email is the identifier; there are no usernames."""

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        """Lowercase the whole address, not just the domain.

        Django's own normalize_email lowercases only the domain, so
        'Jane@example.com' and 'jane@example.com' are distinct — one person could
        hold two accounts and the office would see two applicants. Mail servers
        in practice treat the local part case-insensitively.
        """
        return super().normalize_email(email or '').lower()

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError('An email address is required.')
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        # Sign-in must find the account whatever case was typed.
        return self.get(email__iexact=(email or '').strip())

    def create_user(self, email, password=None, **extra):
        extra.setdefault('role', Role.STUDENT)
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('role', Role.ADMIN)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        if not extra['is_staff'] or not extra['is_superuser']:
            raise ValueError('A superuser must have is_staff and is_superuser set.')
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    # ── Identity ──
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    preferred_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    pronouns = models.CharField(max_length=50, blank=True)

    # ── Contact ──
    phone = models.CharField(max_length=32, blank=True)
    alternate_phone = models.CharField(max_length=32, blank=True)
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=16, blank=True)

    # ── Eligibility ──
    # Determines which funding a person may apply for at all, so it belongs to
    # the person rather than to any one application.
    beneficiary_number = models.CharField(max_length=64, blank=True)
    treaty_number = models.CharField(max_length=64, blank=True)
    is_deline_beneficiary = models.BooleanField(null=True, blank=True)
    is_indian_act_registered = models.BooleanField(null=True, blank=True)

    # ── Access ──
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False, help_text='Can sign in to the Django admin.',
    )
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'user'
        ordering = ('last_name', 'first_name')
        constraints = [
            # Enforced by the database, not only by the manager: any code path
            # that inserts a user must not be able to create a second account
            # for the same address in different case.
            models.UniqueConstraint(Lower('email'), name='uniq_user_email_ci'),
        ]
        indexes = [
            models.Index(fields=('role', 'is_active')),
            models.Index(fields=('beneficiary_number',)),
        ]

    def __str__(self):
        return f'{self.full_name} <{self.email}>'

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def display_name(self) -> str:
        """What to call this person on screen."""
        return self.preferred_name or self.first_name or self.email

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.display_name

    # Role questions are asked constantly across the codebase. Naming them here
    # keeps `user.role == 'ssw' or user.role == 'admin'` from being rewritten,
    # slightly differently, at every call site.
    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT

    @property
    def reviews_applications(self) -> bool:
        return self.role in (Role.SUPPORT_WORKER, Role.ADMIN)

    @property
    def decides_applications(self) -> bool:
        return self.role in (Role.DIRECTOR, Role.ADMIN)

    @property
    def handles_payments(self) -> bool:
        return self.role in (Role.FINANCE, Role.ADMIN)


class BankAccount(models.Model):
    """Where a person's money is sent.

    Separate from User because it is the most sensitive data here and changes
    independently of identity — and because a payment must be traceable to the
    account details in force when it was issued, not to whatever the student
    has since updated them to.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_accounts')
    account_holder = models.CharField(max_length=255)
    transit_number = models.CharField(max_length=16)
    institution_number = models.CharField(max_length=16)
    account_number = models.CharField(max_length=64)

    is_current = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bank_account'
        ordering = ('-added_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('user',), condition=models.Q(is_current=True),
                name='one_current_bank_account_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.account_holder} ****{self.account_number[-4:]}'

    @property
    def masked_account_number(self) -> str:
        """Never show a full account number back to the screen."""
        tail = self.account_number[-4:] if self.account_number else ''
        return f'****{tail}'
