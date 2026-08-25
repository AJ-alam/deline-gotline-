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
    # Deliberately no receives_sfa column. SFA status changes every term, so it
    # belongs to an application rather than to a person; the forms whose award
    # depends on it ask it directly. See funding.services.streams.

    # What the sign-up screening decided, kept rather than recomputed.
    #
    # Two of the screening answers cannot be reconstructed from the columns
    # above — whether the programme is an upgrading programme, which is the only
    # thing separating PSSSP from UCEPP, and whether the person is already
    # funded by another organisation or another land claim agreement. Deriving
    # the streams from `is_indian_act_registered` and `is_deline_beneficiary`
    # alone therefore could not produce UCEPP at all and could not honour either
    # exclusion, which is why UCEPP had rates, rules and no route in.
    eligible_streams = models.JSONField(
        default=list, blank=True,
        help_text="FundingStream values this person qualified for at sign-up.",
    )
    eligibility_answers = models.JSONField(
        default=dict, blank=True,
        help_text='The screening answers the streams above were decided from.',
    )
    eligibility_assessed_at = models.DateTimeField(null=True, blank=True)

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


class EnrolmentProfile(models.Model):
    """What a student keeps on file about their studies, so a form opens filled in.

    This is deliberately *not* on `User`, and deliberately not read by anything
    that decides money. The comment at the top of this module explains why the
    old CustomUser held `institution`, `program` and `enrollment_status`: award
    calculation fell back to `student.enrollment_status` whenever an answer was
    missing, so last year's facts priced this year's application and nobody
    could see it happening.

    So the rule here is one sentence, and it is enforced by a test
    (`test_profile.ProfileNeverPricesTests`):

        **The only reader of this table is `funding.services.prefill`.**

    Nothing in `funding.rules`, `funding.services.streams`, `decisions` or
    `finance` may consult it. An application's answers remain the record its
    decision was made from; this only decides what the boxes are pre-filled
    with before the student confirms or corrects them.

    Which is also why nothing here is required and nothing is validated as
    though it were an application: a half-filled profile is a half-filled
    convenience. The schema validates the form, every time, whatever it opened
    with.

    Per-term facts are absent on purpose — the semester, its dates, the tuition
    quoted, and whether SFA is being received this term. Carrying those forward
    is answering on the student's behalf about a term they have not started.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='enrolment_profile',
    )

    # ── Institution ──
    institution_name = models.CharField(max_length=255, blank=True)
    institution_location = models.CharField(max_length=255, blank=True)
    institution_phone = models.CharField(max_length=32, blank=True)
    # Where the enrolment verification is emailed. Carried from the last
    # application today, which is why a student whose admission was on paper had
    # nothing to carry and their renewal could never be confirmed.
    registrar_email = models.EmailField(blank=True)
    student_number = models.CharField(max_length=64, blank=True)

    # ── Programme ──
    program = models.CharField(max_length=255, blank=True)
    credential_level = models.CharField(max_length=32, blank=True)
    learning_style = models.CharField(max_length=32, blank=True)
    course_load = models.CharField(max_length=32, blank=True)
    program_start = models.DateField(null=True, blank=True)
    program_end = models.DateField(null=True, blank=True)
    program_year = models.PositiveSmallIntegerField(null=True, blank=True)
    program_length_years = models.PositiveSmallIntegerField(null=True, blank=True)

    # ── Household ──
    # Stable enough to keep, unlike the semester. Still asked on every form that
    # prices against it.
    dependent_count = models.PositiveSmallIntegerField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'enrolment_profile'

    def __str__(self):
        return f'{self.user.email}: {self.program or "no programme on file"}'


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
