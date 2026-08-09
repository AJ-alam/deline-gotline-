"""Turning applications into JSON and back.

Answers are validated by the schema, not by a hand-written serializer field per
question. One definition drives API validation, the rendered form and the
generated TypeScript types, so they cannot disagree.
"""

from rest_framework import serializers

from funding.models import (
    Application, ApplicationEvent, ApplicationType, Award, AwardDecision,
    FundingStream,
)
from funding.schemas import ValidationError as SchemaValidationError
from funding.schemas import all_schemas, get_schema


class FieldSerializer(serializers.Serializer):
    """One question, described well enough for a client to render it."""

    key = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField(source='type.value')
    required = serializers.BooleanField()
    help_text = serializers.CharField()
    section = serializers.CharField()
    choices = serializers.SerializerMethodField()

    def get_choices(self, field):
        return [{'value': c.value, 'label': c.label} for c in field.choices]


class SchemaSerializer(serializers.Serializer):
    """An application type's questions.

    This is what lets one renderer serve every form: the client asks what to
    show rather than shipping nine hand-written copies of it.
    """

    slug = serializers.CharField()
    label = serializers.SerializerMethodField()
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


class ApplicationListSerializer(serializers.ModelSerializer):
    """The shape the staff queue reads. Deliberately without answers or trace —
    the previous list endpoint returned 30KB per 50 rows and grew linearly."""

    type_label = serializers.CharField(source='get_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ('id', 'type', 'type_label', 'stream', 'status', 'status_label',
                  'student_name', 'awarded_total', 'submitted_at',
                  'submitted_after_deadline', 'residency_flag')
        read_only_fields = fields

    def get_student_name(self, application):
        return application.student.full_name if application.student else None


class ApplicationDetailSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source='get_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    student_name = serializers.SerializerMethodField()
    events = ApplicationEventSerializer(many=True, read_only=True)
    decision = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ('id', 'type', 'type_label', 'stream', 'status', 'status_label',
                  'schema_slug', 'answers', 'office_notes', 'student_name',
                  'awarded_total', 'submitted_at', 'submitted_after_deadline',
                  'residency_flag', 'events', 'decision')
        read_only_fields = fields

    def get_student_name(self, application):
        return application.student.full_name if application.student else None

    def get_decision(self, application):
        current = application.decisions.filter(is_current=True).first()
        return AwardDecisionSerializer(current).data if current else None


class ApplicationCreateSerializer(serializers.Serializer):
    """Submitting an application.

    `type` selects the schema; `answers` is validated against it. An unknown
    field is rejected rather than stored and never read.
    """

    type = serializers.ChoiceField(choices=ApplicationType.choices)
    stream = serializers.ChoiceField(choices=FundingStream.choices)
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
        answers = {
            key: (str(value) if not isinstance(value, (str, int, float, bool)) else value)
            for key, value in validated['cleaned_answers'].items()
        }
        return Application.objects.create(
            student=self.context['request'].user,
            type=validated['type'],
            stream=validated['stream'],
            schema_slug=validated['type'],
            answers=answers,
            # Left as a draft: the view records the submission event, which is
            # what moves it. Assigning the status here would bypass the workflow.
        )


class TransitionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=ApplicationEvent.Action.choices)
    note = serializers.CharField(required=False, allow_blank=True, default='')


def schema_payload():
    return SchemaSerializer(all_schemas(), many=True).data
