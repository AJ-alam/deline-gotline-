"""Turning applications into JSON and back.

Answers are validated by the schema, not by a hand-written serializer field per
question. One definition drives API validation, the rendered form and the
generated TypeScript types, so they cannot disagree.
"""

from rest_framework import serializers

from django.db import models

from funding.models import (
    ApplicantIdentifier, Application, ApplicationEvent, ApplicationStatus,
    ApplicationType, Award, AwardDecision, FundingStream, SupportingDocument,
)
from funding.schemas import ValidationError as SchemaValidationError
from funding.schemas import all_schemas, get_schema
from funding.services import workflow


class FieldSerializer(serializers.Serializer):
    """One question, described well enough for a client to render it."""

    key = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField(source='type.value')
    required = serializers.BooleanField()
    help_text = serializers.CharField()
    section = serializers.CharField()
    # Worked out by the server. Sent so the renderer can leave it out of the
    # form and the review screen can still label it.
    computed = serializers.BooleanField()
    # Split off and never returned, so a form opened on a stored application has
    # no value for it. Published because the client cannot otherwise tell the
    # difference between "withheld" and "unanswered", and required, it held the
    # Save button disabled on every edit of every form that asks for a SIN or a
    # bank account — the server accepting the edit made no difference, because
    # nobody could press the button.
    private = serializers.SerializerMethodField()

    def get_private(self, field):
        # Matched the way the schema matches: a SIN is private by its type.
        from funding.schemas import FieldType
        return bool(field.private or field.type is FieldType.SIN)
    # The most rows or files this accepts. 0 means no limit.
    max_items = serializers.IntegerField()
    # Opens on today's date. The client fills it, so a guest submission gets it
    # too.
    defaults_to_today = serializers.BooleanField()
    choices = serializers.SerializerMethodField()
    columns = serializers.SerializerMethodField()

    def get_choices(self, field):
        return [{'value': c.value, 'label': c.label} for c in field.choices]

    def get_columns(self, field):
        """A table's columns, described the same way its parent is.

        Recursive rather than a second, flatter shape: a column is a Field, and
        a client that can render a field can render a cell.
        """
        return FieldSerializer(field.columns, many=True).data


class SchemaSerializer(serializers.Serializer):
    """An application type's questions.

    This is what lets one renderer serve every form: the client asks what to
    show rather than shipping nine hand-written copies of it.
    """

    slug = serializers.CharField()
    label = serializers.SerializerMethodField()
    summary = serializers.CharField()
    # Whether a student may start this one themselves. The client filters its
    # "apply for funding" list on this rather than holding its own list of
    # exceptions, which would be a second place for the answer to live.
    apply_in_portal = serializers.BooleanField()
    sections = serializers.ListField(child=serializers.CharField())
    fields = FieldSerializer(many=True)

    def get_label(self, schema):
        return ApplicationType(schema.slug).label


class AwardSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Award
        fields = ('id', 'category', 'category_label', 'amount', 'status',
                  'rule_code', 'reference', 'created_at')
        read_only_fields = fields


class AwardDecisionSerializer(serializers.ModelSerializer):
    lines = AwardSerializer(many=True, read_only=True)

    class Meta:
        model = AwardDecision
        fields = ('id', 'total', 'rule_set_version', 'priced_on', 'is_complete',
                  'is_current', 'trace', 'lines', 'created_at')
        read_only_fields = fields


class ApplicationEventSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source='get_action_display', read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationEvent
        fields = ('id', 'action', 'action_label', 'actor_name', 'note', 'occurred_at')
        read_only_fields = fields

    def get_actor_name(self, event):
        return event.actor.full_name if event.actor else None


def enrolment_state(application) -> dict:
    """Where the institution's confirmation has got to.

    On the list as well as the detail, because the queue is where staff decide
    what to pick up: an application that cannot be forwarded yet should say so
    before it is opened.
    """
    verification = getattr(application, 'enrollment_verification', None)
    if verification is None:
        # "Not required" was said for two different situations: a form that
        # genuinely needs no institution, and one that needs one and was never
        # asked — which happens when no registrar address could be carried from
        # an earlier application. The second is a dead end: the application
        # cannot be forwarded or approved until a figure arrives, and no figure
        # can arrive until somebody asks. Saying "not required" told staff the
        # one thing that would stop them looking.
        if application.type in workflow.NEEDS_ENROLMENT_CONFIRMATION:
            # No address looked up here. This runs for every row of the staff
            # queue, and finding the registrar means reading the student's
            # earlier applications — one query per row, which is exactly the
            # cost `QueryCostTests` exists to hold flat. Staff are asked for the
            # address when they issue the request.
            return {
                'required': True,
                'status': 'not_requested',
                'label': 'No confirmation requested yet',
                'confirmed': False,
            }
        return {'required': False, 'status': 'not_required', 'label': 'Not required'}

    labels = {
        'requested': 'Awaiting institution',
        'completed': 'Confirmed by institution',
        'expired': 'Request expired',
    }
    confirmed = bool(
        verification.status == 'completed' and verification.confirmed_enrolled)
    return {
        'required': True,
        'status': verification.status,
        'label': ('Enrolment not confirmed'
                  if verification.status == 'completed' and not confirmed
                  else labels.get(verification.status, verification.status)),
        'confirmed': confirmed,
        'registrar_email': verification.registrar_email,
        'requested_at': verification.requested_at,
        'responded_at': verification.responded_at,
    }


class ApplicationListSerializer(serializers.ModelSerializer):
    """The shape the staff queue reads. Deliberately without answers or trace —
    the previous list endpoint returned 30KB per 50 rows and grew linearly."""

    type_label = serializers.CharField(source='get_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    student_name = serializers.SerializerMethodField()
    enrolment = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ('id', 'type', 'type_label', 'stream', 'status', 'status_label',
                  'student_name', 'awarded_total', 'submitted_at',
                  'submitted_after_deadline', 'residency_flag', 'enrolment')
        read_only_fields = fields

    def get_enrolment(self, application):
        return enrolment_state(application)

    def get_student_name(self, application):
        return application.student.full_name if application.student else None


class SupportingDocumentSerializer(serializers.ModelSerializer):
    """A file attached to an application, as a screen needs it.

    `answers` holds a reference like `document:12`, which is meaningless to a
    person. A reviewer was shown that string and had no way to open the
    transcript an assessment depends on.
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = SupportingDocument
        fields = ('id', 'field_key', 'original_name', 'uploaded_at', 'url')
        read_only_fields = fields

    def get_url(self, document):
        # Served by Django rather than linked to MEDIA_URL: the file must not be
        # readable by anyone who guesses the path, and the permission check
        # lives on the endpoint.
        return f'/api/documents/{document.pk}/'


class ApplicationDetailSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source='get_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    student_name = serializers.SerializerMethodField()
    events = ApplicationEventSerializer(many=True, read_only=True)
    decision = serializers.SerializerMethodField()
    enrolment = serializers.SerializerMethodField()
    enrolment_answers = serializers.SerializerMethodField()
    identifiers = serializers.SerializerMethodField()
    banking = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    can_revise = serializers.SerializerMethodField()
    information_requested = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ('id', 'type', 'type_label', 'stream', 'status', 'status_label',
                  'schema_slug', 'answers', 'office_notes', 'student_name',
                  'awarded_total', 'submitted_at', 'submitted_after_deadline',
                  'residency_flag', 'events', 'decision', 'enrolment',
                  'enrolment_answers', 'identifiers', 'banking', 'documents',
                  'can_revise', 'information_requested')
        read_only_fields = fields

    def get_documents(self, application):
        """Everything attached, including files uploaded before it existed.

        A document is uploaded as soon as it is chosen — before the application
        is created — so it belongs to the person until a submission claims it.
        The ones named by this application's own answers are what a reviewer
        needs, so they are matched by reference rather than by foreign key
        alone.
        """
        referenced = set()
        for value in (application.answers or {}).values():
            for item in (value if isinstance(value, list) else [value]):
                text = str(item)
                if text.startswith('document:'):
                    referenced.add(text.removeprefix('document:'))

        documents = SupportingDocument.objects.filter(
            models.Q(application=application)
            | models.Q(pk__in=[pk for pk in referenced if pk.isdigit()])
        ).distinct().order_by('uploaded_at')
        return SupportingDocumentSerializer(documents, many=True).data

    def get_can_revise(self, application):
        """Whether the person reading this may edit it.

        Only the student it belongs to, and only while the office is waiting for
        something. An application under review must not change under the
        reviewer, and a decided one is a record.
        """
        user = getattr(self.context.get('request'), 'user', None)
        return bool(
            user and user.is_authenticated
            and application.student_id == user.pk
            and application.status == ApplicationStatus.INFO_REQUESTED
        )

    def get_information_requested(self, application):
        """What the office asked for, and who asked.

        Read from the event log rather than stored twice. Without it the student
        opens the application knowing only that something is needed.
        """
        event = (application.events
                 .filter(action=ApplicationEvent.Action.INFO_REQUESTED)
                 .order_by('-occurred_at')
                 .first())
        if event is None:
            return None
        return {
            'note': event.note,
            'asked_by': event.actor.full_name if event.actor else '',
            'asked_at': event.occurred_at,
        }

    def get_banking(self, application):
        """Whether this can actually be paid — without showing the account.

        Staff used to read the whole number straight off `answers`. The one
        thing a reviewer needs is whether an account is on file, because that
        is what holds an approved award in the payment run. The digits belong
        to the payment file, not to a review screen.
        """
        blank = {'on_file': False, 'account': '', 'holder': '', 'held': False}

        student = application.student
        if student is not None:
            account = next(
                (a for a in student.bank_accounts.all() if a.is_current), None)
            if account is None:
                return blank
            return {
                'on_file': True,
                'account': f'••••{account.account_number[-4:]}',
                'holder': account.account_holder,
                'held': False,
            }

        # A guest application: the details are held encrypted until the office
        # attaches it to an account, and move across when it does.
        for identifier in application.identifiers.all():
            if identifier.kind == ApplicantIdentifier.Kind.BANK_ACCOUNT:
                return {
                    'on_file': True,
                    'account': f'•••{identifier.last_three}',
                    'holder': '',
                    'held': True,
                }
        return blank

    def get_enrolment(self, application):
        return enrolment_state(application)

    def get_enrolment_answers(self, application):
        """What the institution declared, once it has."""
        verification = getattr(application, 'enrollment_verification', None)
        if verification is None or verification.status != 'completed':
            return None
        return verification.answers or {}

    def get_identifiers(self, application):
        """Masked only. The full number is never serialised — reading it is a
        separate, audited act."""
        return {
            identifier.kind: f'•••••{identifier.last_three}'
            for identifier in application.identifiers.all()
        }

    def get_student_name(self, application):
        return application.student.full_name if application.student else None

    def get_decision(self, application):
        # Read from the prefetched set rather than issuing a fresh filter: a
        # queryset method here would defeat the prefetch and add a query per
        # application whenever this serializer is used for more than one.
        for decision in application.decisions.all():
            if decision.is_current:
                return AwardDecisionSerializer(decision).data
        return None


class ApplicationCreateSerializer(serializers.Serializer):
    """Submitting an application.

    `type` selects the schema; `answers` is validated against it. An unknown
    field is rejected rather than stored and never read.

    The funding stream is not accepted from the client. It follows from the
    eligibility answers given at sign-up and the SFA answer on this
    application, and it gates which tuition and living-allowance rules apply —
    so a client that could choose it could choose one the applicant does not
    qualify for and change what they are paid.
    """

    type = serializers.ChoiceField(choices=ApplicationType.choices)
    answers = serializers.DictField()

    def validate(self, attrs):
        try:
            schema = get_schema(attrs['type'])
        except KeyError:
            raise serializers.ValidationError(
                {'type': f"No schema is defined for {attrs['type']!r}."}
            )
        try:
            attrs['cleaned_answers'] = schema.clean(attrs['answers'])
        except SchemaValidationError as exc:
            # Field-level errors, so a client can show each message against the
            # question it belongs to.
            raise serializers.ValidationError({'answers': exc.errors})
        return attrs

    def create(self, validated):
        from funding.services import banking, identifiers, streams

        schema = get_schema(validated['type'])
        # Split before the write, so a withheld answer is never in the
        # dictionary that becomes `answers` — not even briefly.
        ordinary, private = schema.split_private(validated['cleaned_answers'])

        user = self.context['request'].user
        application = Application.objects.create(
            student=user,
            type=validated['type'],
            stream=streams.for_application(
                user, validated['type'], validated['cleaned_answers']),
            schema_slug=validated['type'],
            answers=jsonable(ordinary),
            # Left as a draft: the view records the submission event, which is
            # what moves it. Assigning the status here would bypass the workflow.
        )
        for key in schema.sensitive_keys:
            if key in private:
                identifiers.store(application, key, str(private[key]))
        banking.record(application, private)
        return application


def _json_value(value):
    """One answer as JSON can hold it.

    Recurses, because two field types hold a list: FILES a list of document
    references and TABLE a list of rows. Stringifying those whole — which is
    what this did — stored the literal text "[{'amount': Decimal('812.50')}]"
    as the answer, so a travel claim's expenses were unreadable by anything and
    its total was derived from a Python repr.
    """
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    # bool before int is not needed here — both are JSON scalars — but None is
    # not caught by the isinstance check and must stay null rather than 'None'.
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def jsonable(answers: dict) -> dict:
    """Answers as JSON can hold them.

    The schema cleans dates and decimals into Python objects; the column stores
    JSON. Anything that is not already a JSON scalar is written as its string.
    """
    return {key: _json_value(value) for key, value in answers.items()}


# What may be applied for without an account.
#
# Both are one-time awards claimed after the fact, by people who are often not
# otherwise students here: a summer placement, or a credential just finished.
# Requiring a portal account first is what stopped those claims being made.
# Everything else — anything continuing, anything paying tuition — needs an
# account, because it needs a record that persists across semesters.
GUEST_TYPES = (ApplicationType.PRACTICUM, ApplicationType.GRADUATION_BURSARY)

# Both are bursaries from the government's own funds rather than a federal
# programme, so the guest does not choose a stream: there is only one it can be.
GUEST_STREAM = FundingStream.DGGR


class GuestApplicationSerializer(serializers.Serializer):
    """An application from someone who has no account and does not need one.

    The same schema validation as any other application — a guest submission is
    not a lesser record. What differs is that `student` is null until staff
    attach it to a person, and that the type is restricted to the two awards
    that make sense without a continuing relationship.
    """

    type = serializers.ChoiceField(choices=[(t.value, t.label) for t in GUEST_TYPES])
    answers = serializers.DictField()

    def validate(self, attrs):
        schema = get_schema(attrs['type'])
        try:
            attrs['cleaned_answers'] = schema.clean(attrs['answers'])
        except SchemaValidationError as exc:
            raise serializers.ValidationError({'answers': exc.errors})
        return attrs

    def create(self, validated):
        from funding.services import banking, identifiers

        schema = get_schema(validated['type'])
        # The same split as the signed-in path. A guest practicum asks for bank
        # details too, and they were going straight into `answers`.
        ordinary, private = schema.split_private(validated['cleaned_answers'])

        application = Application.objects.create(
            student=None,
            type=validated['type'],
            stream=GUEST_STREAM,
            schema_slug=validated['type'],
            answers=jsonable(ordinary),
        )
        # Government identifiers, exactly as the signed-in path stores them.
        #
        # This branch did not, and the omission was invisible while no guest
        # form asked for one: a SIN would be validated, split out of `answers`
        # so that it could be stored somewhere safer, and then dropped on the
        # floor. The applicant would have typed a regulated identifier that was
        # never recorded, and nothing would have said so.
        for key in schema.sensitive_keys:
            if key in private:
                identifiers.store(application, key, str(private[key]))
        banking.record(application, private)
        return application


class AttachSerializer(serializers.Serializer):
    """Which account a guest application belongs to."""

    student_id = serializers.IntegerField()


class ReviseSerializer(serializers.Serializer):
    """A student answering a request for more information.

    The whole answer set, validated by the same schema that validated the
    original: a revision is the application as it now stands, not a patch. That
    keeps one code path for what a valid application is — a partial update would
    need a second, weaker notion of "complete", and the second one is always the
    one that lets something through.

    Private answers are split off exactly as they are on submission, so a
    student correcting a bank account does not put the number into `answers`.
    """

    answers = serializers.DictField()
    note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        application = self.context['application']
        schema = get_schema(application.type)

        # Answers the application carries that its own schema does not define.
        # `confirmed_tuition` is the case that matters: the registrar's figure
        # is written onto the application when they confirm the enrolment, and
        # the admission schema has no such question — so re-posting a stored
        # application was refused for an answer the *server* had put there, and
        # every admission application became uneditable the moment its
        # institution answered.
        #
        # Kept, not re-validated, and never taken from the client: tuition is
        # funded against the registrar's figure, and a route by which an edit
        # could set it is a route by which an award can be inflated. A key that
        # is not already on the application is still refused as unknown.
        carried = {key: value for key, value in (application.answers or {}).items()
                   if key not in schema.keys}
        submitted = {key: value for key, value in attrs['answers'].items()
                     if key not in carried}

        try:
            attrs['cleaned_answers'] = schema.clean(submitted, revising=True)
        except SchemaValidationError as exc:
            raise serializers.ValidationError({'answers': exc.errors})
        attrs['carried_answers'] = carried
        return attrs


class TransitionSerializer(serializers.Serializer):
    # Only the actions that actually are transitions. AMENDED is an event and
    # not a step through review, so offering it here would let a correction be
    # posted as a workflow move and be refused deeper in for a reason that
    # reads like a bug.
    action = serializers.ChoiceField(
        choices=[(value, value) for value in workflow.RESULTING_STATUS])
    note = serializers.CharField(required=False, allow_blank=True, default='')


def schema_payload():
    return SchemaSerializer(all_schemas(), many=True).data
