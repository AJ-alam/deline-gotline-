"""Funding domain.

Replaces 23 models spread across api/ forms/ programs/ with the eight things this
system actually has. The nine Form* variants were never nine kinds of object —
they were one application carrying different fields, and fields now live in
forms.schema. So `Application.type` distinguishes them and `answers` holds them.

Naming is what the office calls things. 'Form A' is an Admission Application;
'Form G' is a Graduation Bursary. The letters were an internal filing habit that
leaked into class names, URLs, database columns and award logic.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApplicationType(models.TextChoices):
    """What the applicant is asking for.

    Replaces `form_type` CharChoices matched with `title__icontains`, which made
    the funding stream a property of an editable display title.
    """

    ADMISSION = 'admission', 'Admission Application'                    # was Form A
    ENROLLMENT_VERIFICATION = 'enrollment_verification', 'Enrollment Verification'  # was Form B
    CONTINUING_FUNDING = 'continuing_funding', 'Continuing Funding'     # was Form C
    APPEAL = 'appeal', 'Appeal / Reconsideration'                       # was Form D
    TRAVEL = 'travel', 'Travel & Emergency Assistance'                  # was Form E
    PRACTICUM = 'practicum', 'Practicum Placement Allowance'            # was Form F
    GRADUATION_BURSARY = 'graduation_bursary', 'Graduation Bursary'     # was Form G
    EMERGENCY_RELIEF = 'emergency_relief', 'Emergency Relief'            # was Form H
    # 'Form H' meant three different things: the calculator read it as summer
    # student employment, seed_forms created it as Emergency Relief, and the
    # frontend mapped it to Form D (Appeal). The seeded form is authoritative.
    HARDSHIP_BURSARY = 'hardship_bursary', 'Hardship Bursary'
    ACADEMIC_SCHOLARSHIP = 'academic_scholarship', 'Academic Scholarship'


class FundingStream(models.TextChoices):
    """Which pot the money comes from. Was derived by substring-matching titles."""

    PSSSP = 'psssp', 'C-DFN PSSSP'
    UCEPP = 'ucepp', 'C-DFN UCEPP'
    DGGR = 'dggr', 'DGGR Bursaries'


class ApplicationStatus(models.TextChoices):
    """One workflow. Application and FormSubmission previously had two, with
    different member sets, and a record could sit in both at once."""

    DRAFT = 'draft', 'Draft'
    SUBMITTED = 'submitted', 'Submitted'
    UNDER_REVIEW = 'under_review', 'Under Review'
    INFO_REQUESTED = 'info_requested', 'More Information Requested'
    AWAITING_DECISION = 'awaiting_decision', 'Awaiting Director Decision'
    APPROVED = 'approved', 'Approved'
    DECLINED = 'declined', 'Declined'
    SENT_TO_FINANCE = 'sent_to_finance', 'Sent to Finance'

    @classmethod
    def open_states(cls):
        return (cls.SUBMITTED, cls.UNDER_REVIEW, cls.INFO_REQUESTED, cls.AWAITING_DECISION)


class Application(models.Model):
    """A student's request for funding.

    Was FormSubmission plus a shadow Application row synthesized by the payment
    path, which meant one request could appear twice with two mutable statuses.

    `answers` is keyed by the stable field keys in forms.schema. It replaces the
    FormField / SubmissionAnswer tables, where a field's identity was its display
    string and award amounts were resolved by substring matching.
    """

    type = models.CharField(max_length=32, choices=ApplicationType.choices)
    stream = models.CharField(max_length=16, choices=FundingStream.choices)
    status = models.CharField(
        max_length=24, choices=ApplicationStatus.choices,
        default=ApplicationStatus.SUBMITTED,
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='applications', null=True, blank=True,
    )

    # Schema-validated answers, keyed by stable field key.
    schema_slug = models.CharField(max_length=64)
    answers = models.JSONField(default=dict)

    # What staff record on top of the applicant's answers.
    office_notes = models.JSONField(default=dict, blank=True)

    awarded_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    submitted_at = models.DateTimeField(default=timezone.now)
    academic_year = models.CharField(max_length=16, blank=True)
    semester = models.CharField(max_length=16, blank=True)

    # Deadline handling (§4.4/§4.5)
    submitted_after_deadline = models.BooleanField(default=False)
    late_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    late_approved_at = models.DateTimeField(null=True, blank=True)

    # Residency consistency check
    residency_flag = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'application'
        ordering = ('-submitted_at',)
        indexes = [
            # The staff dashboard filters on these. The old query was
            # title__icontains — a LIKE '%…%' scan that no index could serve.
            models.Index(fields=('status', '-submitted_at')),
            models.Index(fields=('type', 'status')),
            models.Index(fields=('stream', 'status')),
            models.Index(fields=('student', '-submitted_at')),
        ]

    def __str__(self):
        return f"{self.get_type_display()} #{self.pk}"

    @property
    def is_open(self):
        return self.status in ApplicationStatus.open_states()


class ApplicationEvent(models.Model):
    """Every status transition, with who and why.

    Replaces the scattered reviewed_at/forwarded_at/decided_at/more_info_* column
    pairs on FormSubmission — sixteen columns encoding a history that was never
    queryable and could contradict `status`.
    """

    class Action(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        REVIEWED = 'reviewed', 'Reviewed'
        INFO_REQUESTED = 'info_requested', 'Information Requested'
        INFO_PROVIDED = 'info_provided', 'Information Provided'
        FORWARDED = 'forwarded', 'Forwarded to Director'
        APPROVED = 'approved', 'Approved'
        DECLINED = 'declined', 'Declined'
        SENT_TO_FINANCE = 'sent_to_finance', 'Sent to Finance'

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='events',
    )
    action = models.CharField(max_length=24, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    note = models.TextField(blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'application_event'
        # Ordered by id as well as time: auto_now_add timestamps can tie, and an
        # ambiguous order would fold the same history to different statuses.
        ordering = ('occurred_at', 'id')
        indexes = [models.Index(fields=('application', 'occurred_at'))]

    def __str__(self):
        return f"{self.application_id}: {self.action}"


class Award(models.Model):
    """One disbursable line of an approved application.

    Was Payment, which carried FKs to both Application and FormSubmission because
    the two models overlapped. One parent now.
    """

    class Category(models.TextChoices):
        TUITION = 'tuition', 'Tuition'
        LIVING = 'living', 'Living Allowance'
        BOOKS = 'books', 'Books & Supplies'
        TRAVEL = 'travel', 'Travel'
        BURSARY = 'bursary', 'Bursary'
        SCHOLARSHIP = 'scholarship', 'Scholarship'
        BACK_PAY = 'back_pay', 'Back Pay'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT_TO_FINANCE = 'sent_to_finance', 'Sent to Finance'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='awards',
    )
    # Which pricing produced this line. Lines belong to a decision, so replacing
    # a decision replaces its lines as a set rather than editing them in place.
    decision = models.ForeignKey(
        'AwardDecision', on_delete=models.CASCADE,
        related_name='lines', null=True, blank=True,
    )
    rule_code = models.CharField(
        max_length=64, blank=True,
        help_text='The rule that produced this line, for the audit trail.',
    )
    category = models.CharField(max_length=24, choices=Category.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)

    reference = models.CharField(max_length=64, unique=True, null=True, blank=True)
    sent_to_finance_at = models.DateTimeField(null=True, blank=True)
    sent_to_finance_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'award'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('application', 'category')),
            models.Index(fields=('status', '-created_at')),
        ]

    def __str__(self):
        return f"{self.get_category_display()} ${self.amount}"


class PolicySetting(models.Model):
    """A configurable rate or rule that award calculation reads.

    A missing setting must never be read as a rate of zero — that produced $0.00
    awards indistinguishable from real decisions.
    """

    section = models.CharField(max_length=64)
    key = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'policy_setting'
        # The old table had no uniqueness guard, so duplicate rows for one
        # setting were possible and .get() would raise on them.
        constraints = [
            models.UniqueConstraint(fields=('section', 'key'), name='uniq_policy_setting'),
        ]
        ordering = ('section', 'key')

    def __str__(self):
        return f"{self.section}:{self.key} = {self.value}"


class PolicyChange(models.Model):
    """Audit trail of policy edits, with the date a change takes effect.

    §7.5: an application is priced with the rates in force when it was submitted,
    so history has to be queryable by date.
    """

    setting = models.ForeignKey(
        PolicySetting, on_delete=models.CASCADE, related_name='changes',
    )
    previous_value = models.DecimalField(max_digits=12, decimal_places=2)
    new_value = models.DecimalField(max_digits=12, decimal_places=2)
    effective_date = models.DateField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'policy_change'
        ordering = ('-effective_date',)
        indexes = [models.Index(fields=('setting', 'effective_date'))]

    def __str__(self):
        return f"{self.setting_id}: {self.previous_value} → {self.new_value}"


class ApplicationDeadline(models.Model):
    """Submission cut-off per stream and semester."""

    stream = models.CharField(max_length=16, choices=FundingStream.choices)
    academic_year = models.CharField(max_length=16)
    semester = models.CharField(max_length=16)
    closes_at = models.DateTimeField()
    late_allowed = models.BooleanField(default=False)

    class Meta:
        db_table = 'application_deadline'
        constraints = [
            models.UniqueConstraint(
                fields=('stream', 'academic_year', 'semester'), name='uniq_deadline',
            ),
        ]
        ordering = ('-closes_at',)

    def __str__(self):
        return f"{self.stream} {self.semester} {self.academic_year}"


class SupportingDocument(models.Model):
    """A file attached to an application.

    Was two models — Document and UserDocument — differing only in what they
    hung off.
    """

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE,
        related_name='documents', null=True, blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents',
    )
    # Matches the schema field key it satisfies (e.g. 'doc_transcripts').
    field_key = models.CharField(max_length=64, blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/')
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supporting_document'
        ordering = ('-uploaded_at',)
        indexes = [models.Index(fields=('application', 'field_key'))]

    def __str__(self):
        return self.original_name


class EnrollmentVerification(models.Model):
    """A registrar's confirmation that a student is enrolled — the old Form B.

    Sent to the institution by link; the registrar completes it without an account.
    """

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Expired'

    application = models.OneToOneField(
        Application, on_delete=models.CASCADE, related_name='enrollment_verification',
    )
    registrar_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)

    confirmed_enrolled = models.BooleanField(null=True, blank=True)
    confirmed_course_load = models.CharField(max_length=32, blank=True)
    registrar_name = models.CharField(max_length=255, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'enrollment_verification'
        indexes = [models.Index(fields=('token',))]

    def __str__(self):
        return f"Enrollment verification for application {self.application_id}"


class ShareLink(models.Model):
    """A time-limited, unauthenticated view of one application.

    Was ShareableLink, which carried FKs to both Application and FormSubmission
    because the two models overlapped.
    """

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='share_links',
    )
    token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'share_link'
        indexes = [models.Index(fields=('token',))]

    @property
    def is_valid(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'Share link for application {self.application_id}'


class ActionToken(models.Model):
    """A single-use link that performs one decision from an email.

    Unifies DirectorActionToken and FinanceConfirmToken, which were the same
    pattern duplicated for two purposes.

    Consumed exactly once: `used_at` is what stops a forwarded email from being
    replayed to approve an application twice.
    """

    class Purpose(models.TextChoices):
        APPROVE = 'approve', 'Approve application'
        DECLINE = 'decline', 'Decline application'
        CONFIRM_PAYMENT = 'confirm_payment', 'Confirm payment issued'

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='action_tokens',
    )
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    token = models.CharField(max_length=64, unique=True)
    issued_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'action_token'
        indexes = [models.Index(fields=('token',))]

    @property
    def is_usable(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'{self.get_purpose_display()} token for application {self.application_id}'


class AuditEntry(models.Model):
    """Who changed what, for actions outside a single application's timeline.

    ApplicationEvent covers an application's own history and PolicyChange covers
    rate edits; this records the rest — user administration, exports, dispatches.
    Government funding decisions have to be reconstructable after the fact.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    actor_role = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=128)
    detail = models.TextField(blank=True)
    application = models.ForeignKey(
        Application, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_entries',
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_entry'
        ordering = ('-occurred_at',)
        indexes = [
            models.Index(fields=('-occurred_at',)),
            models.Index(fields=('actor', '-occurred_at')),
        ]
        verbose_name_plural = 'audit entries'

    def __str__(self):
        return f'{self.action} by {self.actor_id or "system"}'


class RuleSet(models.Model):
    """A dated, versioned collection of funding rules.

    Award amounts used to live in an 847-line service branching on form titles.
    Changing a rate meant a deploy, nobody could see why an amount was produced,
    and re-running an old calculation silently applied today's logic to a
    decision made years ago.

    An award records the RuleSet that priced it, so any decision can be replayed
    exactly as it was made — which is what an appeal requires.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        SUPERSEDED = 'superseded', 'Superseded'

    name = models.CharField(max_length=128)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True, blank=True,
        help_text='Null means still in force.',
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'rule_set'
        ordering = ('-effective_from', '-version')
        constraints = [
            models.UniqueConstraint(fields=('name', 'version'), name='uniq_ruleset_version'),
        ]
        indexes = [models.Index(fields=('status', '-effective_from'))]

    def __str__(self):
        return f'{self.name} v{self.version}'

    @classmethod
    def in_force_on(cls, when):
        """The rule set that governed a given date.

        Superseded sets are included: 'superseded' means no longer current, not
        never applied. Excluding them made applications from before the latest
        policy change unpriceable, which defeats the point of versioning — a
        decision must be reproducible under the rules that actually governed it.

        Drafts are excluded because they have never governed anything.
        """
        return (cls.objects
                .exclude(status=cls.Status.DRAFT)
                .filter(effective_from__lte=when)
                .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=when))
                .order_by('-effective_from', '-version')
                .first())


class Rule(models.Model):
    """One funding rule: when it applies, and what it awards.

    `condition` and `effect` are data, not code. `effect.kind` names one of a
    closed set of calculators in funding.rules.effects — a general expression
    language stored in the database would be a programming language nobody can
    audit, which is the opposite of the point.
    """

    rule_set = models.ForeignKey(RuleSet, on_delete=models.CASCADE, related_name='rules')

    code = models.CharField(
        max_length=64,
        help_text='Stable identifier, cited in the decision trace.',
    )
    description = models.CharField(
        max_length=255,
        help_text='Shown to staff and applicants as the reason for an amount.',
    )

    applies_to_types = models.JSONField(
        default=list, blank=True,
        help_text='ApplicationType values. Empty means every type.',
    )
    applies_to_streams = models.JSONField(
        default=list, blank=True,
        help_text='FundingStream values. Empty means every stream.',
    )

    condition = models.JSONField(
        default=dict, blank=True,
        help_text='Predicate over the application. Empty means always.',
    )
    effect = models.JSONField(
        help_text='{"kind": ..., ...} naming a calculator and its parameters.',
    )

    category = models.CharField(
        max_length=24, choices=Award.Category.choices,
        help_text='Which kind of award this produces.',
    )
    order = models.PositiveSmallIntegerField(
        default=100,
        help_text='Evaluation order. Tuition rules allocate against a shared '
                  'remaining balance, so their order decides which stream pays first.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'rule'
        ordering = ('order', 'id')
        constraints = [
            models.UniqueConstraint(fields=('rule_set', 'code'), name='uniq_rule_code'),
        ]

    def __str__(self):
        return f'{self.code} ({self.rule_set})'


class AwardDecision(models.Model):
    """An immutable record of one pricing of one application.

    Amounts used to be recalculated in place: re-running a calculation
    overwrote the previous result, so the reasoning behind a decision that had
    already been communicated to a student simply disappeared. There was no way
    to answer 'why was I awarded this?' after the fact.

    Repricing creates a new decision and supersedes the old one. Nothing is ever
    edited. Together with the RuleSet version and the snapshot of the answers
    used, any decision can be reconstructed exactly as it was made.
    """

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='decisions',
    )

    # PROTECT: a rule set that has priced something is part of the record and
    # must not be deletable out from under it.
    rule_set = models.ForeignKey(
        'RuleSet', on_delete=models.PROTECT, related_name='decisions',
    )
    rule_set_version = models.PositiveIntegerField(
        help_text='Copied so the version survives independently of the rule set.',
    )

    total = models.DecimalField(max_digits=12, decimal_places=2)

    # The answers as they stood when priced. Editing an application later must
    # not silently change what an earlier decision was based on.
    inputs = models.JSONField(default=dict)
    trace = models.JSONField(
        default=dict,
        help_text='Every rule considered, whether it fired, and why.',
    )
    is_complete = models.BooleanField(
        default=True,
        help_text='False when a rate a rule needed was not configured.',
    )

    is_current = models.BooleanField(default=True)
    superseded_by = models.OneToOneField(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='supersedes',
    )

    priced_on = models.DateField(
        null=True, blank=True,
        help_text='The date whose rates applied — the submission date, not today.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'award_decision'
        ordering = ('-created_at',)
        constraints = [
            # At most one current decision per application, enforced by the
            # database rather than by whichever code path happens to write next.
            models.UniqueConstraint(
                fields=('application',),
                condition=models.Q(is_current=True),
                name='one_current_decision_per_application',
            ),
        ]
        indexes = [models.Index(fields=('application', '-created_at'))]

    def __str__(self):
        return f'Decision for application {self.application_id}: ${self.total}'
