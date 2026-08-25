"""User-facing account data."""

from django.utils import timezone
from rest_framework import serializers

from accounts.models import BankAccount, EnrolmentProfile, User
from accounts.services import eligibility as eligibility_service


class BlankMeansNothingOnFile:
    """An empty box means "nothing on file", whatever kind of box it is.

    The profile posts every field in a section, so a student who has never
    given their date of birth posts `date_of_birth: ''`. A DRF DateField reads
    that as a malformed date and an IntegerField as a malformed number, and the
    save comes back with errors against boxes the student never typed in — the
    section cannot be saved at all until they invent a value. Registration does
    not collect a date of birth, so on `/api/me/` that was *every* student, on
    their first visit to the screen.

    A CharField takes '' and says nothing, which is what made this invisible
    from the inside: the first tests to clear a field cleared a text one.

    Derived from the field rather than from a list of keys, so a date or a count
    added tomorrow behaves the same way without anybody remembering this. Shared
    by both serializers that back the profile screen, because a rule applied at
    one of two entrances is not applied.
    """

    def to_internal_value(self, data):
        if hasattr(data, 'dict'):  # a QueryDict from a form post
            data = data.dict()
        if isinstance(data, dict):
            data = {
                key: (None if (value == '' and not isinstance(
                    self.fields.get(key), serializers.CharField)) else value)
                for key, value in data.items()
            }
        return super().to_internal_value(data)


class BankAccountSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source='masked_account_number', read_only=True)

    class Meta:
        model = BankAccount
        # The full account number is never returned. It is written once and read
        # only by the finance export.
        fields = ('id', 'account_holder', 'transit_number', 'institution_number',
                  'account_number', 'is_current', 'added_at')
        read_only_fields = fields


class UserSerializer(BlankMeansNothingOnFile, serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source='get_role_display', read_only=True)
    bank_account = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'preferred_name',
                  'full_name', 'display_name', 'date_of_birth', 'pronouns',
                  'phone', 'alternate_phone', 'street_address', 'city', 'province',
                  'postal_code', 'beneficiary_number', 'treaty_number',
                  'is_deline_beneficiary', 'is_indian_act_registered',
                  'eligible_streams', 'eligibility_assessed_at',
                  'role', 'role_label', 'date_joined', 'bank_account')
        # The streams are the office's decision about a person, not a preference
        # they may edit. Returned so the portal can show what someone qualifies
        # for; changed only by re-running the screening.
        #
        # The two eligibility booleans are read-only for the same reason, and it
        # is the stronger case: they are *answers to the screening*, and
        # `streams.saved_streams` falls back to them on accounts opened before
        # the tags existed. Left writable here, a student could PATCH
        # `is_indian_act_registered` to true and hand themselves PSSSP without
        # the screening ever running — the eligibility rules would live in the
        # client all over again. They move only through
        # `/api/me/eligibility/`, which re-runs `eligibility.assess` and writes
        # the tags, the answers and an audit entry together.
        read_only_fields = ('id', 'email', 'role', 'role_label', 'date_joined',
                            'full_name', 'display_name', 'bank_account',
                            'eligible_streams', 'eligibility_assessed_at',
                            'is_deline_beneficiary', 'is_indian_act_registered')

    def get_bank_account(self, user):
        current = user.bank_accounts.filter(is_current=True).first()
        return BankAccountSerializer(current).data if current else None


class EnrolmentProfileSerializer(BlankMeansNothingOnFile, serializers.ModelSerializer):
    """The study facts a student keeps on file, so their next form opens filled in.

    The choice fields are validated against the *schema's* choices rather than
    against a list written out here. A profile holding `course_load =
    'fulltime'` would pre-fill a form with a value the schema refuses, and the
    student would meet a validation error on an answer they never typed — which
    is the same class of fault as pre-filling a key the schema does not define.
    """

    class Meta:
        model = EnrolmentProfile
        fields = ('institution_name', 'institution_location', 'institution_phone',
                  'registrar_email', 'student_number', 'program', 'credential_level',
                  'learning_style', 'course_load', 'program_start', 'program_end',
                  'program_year', 'program_length_years', 'dependent_count',
                  'updated_at')
        read_only_fields = ('updated_at',)

    def _choice_values(self, name: str) -> set[str]:
        from funding.schemas import admission

        return {choice.value for choice in getattr(admission, name)}

    def validate_course_load(self, value):
        return self._one_of(value, 'COURSE_LOAD', 'course load')

    def validate_credential_level(self, value):
        return self._one_of(value, 'CREDENTIAL_LEVEL', 'credential')

    def validate_learning_style(self, value):
        return self._one_of(value, 'LEARNING_STYLE', 'learning style')

    def _one_of(self, value, name: str, description: str):
        if not value:
            return ''
        allowed = self._choice_values(name)
        if value not in allowed:
            raise serializers.ValidationError(
                f'{value!r} is not a {description} the forms recognise. '
                f'Expected one of: {", ".join(sorted(allowed))}.')
        return value

    def validate(self, attrs):
        # Read through the instance, so a partial update is checked against what
        # the profile will actually hold rather than only against what arrived.
        start = attrs.get('program_start', getattr(self.instance, 'program_start', None))
        end = attrs.get('program_end', getattr(self.instance, 'program_end', None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {'program_end': 'The programme cannot end before it starts.'})
        return attrs


class BankingSerializer(serializers.Serializer):
    """Where this student is paid.

    Write-only by design: what comes back is the masked account from
    `BankAccountSerializer`. The four values are the same block the forms
    collect (`schemas.common.banking`), and they are routed to the same place by
    the same service — `funding.services.banking.set_current` — so a student who
    fills this in on their profile and a student who fills it in on a form end
    up with one account record and one history, not two ideas of where their
    money goes.
    """

    account_holder = serializers.CharField(max_length=255)
    transit_number = serializers.CharField(max_length=16)
    institution_number = serializers.CharField(max_length=16)
    account_number = serializers.CharField(max_length=64)

    def validate(self, attrs):
        from funding.services import banking

        values = {key: str(value).strip() for key, value in attrs.items()}
        problems = banking.unpayable_reasons(values)
        if problems:
            # Keyed by field, so each message lands under the box it is about.
            raise serializers.ValidationError(problems)
        return values


class EligibilityUpdateSerializer(serializers.Serializer):
    """A student answering the screening questions again.

    Not a patch: the whole answer set, because the outcome is decided by all six
    together. Answering three of them would re-screen against a mixture of what
    is true now and what was true at sign-up, and the mixture is the one thing
    that was never true.
    """

    answers = serializers.DictField(child=serializers.CharField(allow_blank=True))

    def validate_answers(self, value):
        missing = eligibility_service.missing_answers(value)
        if missing:
            raise serializers.ValidationError(
                'Answer all six questions. Still unanswered: '
                + ', '.join(missing) + '.')
        unrecognised = eligibility_service.unrecognised_answers(value)
        if unrecognised:
            # Refused rather than read as a no. `_yes` treats anything it does
            # not recognise as a negative, so an unoffered value decided a
            # funding stream by falling through a comparison.
            raise serializers.ValidationError(unrecognised)
        known = {question['key'] for question in eligibility_service.QUESTIONS}
        return {key: str(answer).strip() for key, answer in value.items() if key in known}


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    eligibility = serializers.DictField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'confirm_password', 'first_name',
                  'last_name', 'phone', 'eligibility')

    def validate(self, attrs):
        if attrs.get('password') != attrs.pop('confirm_password', None):
            raise serializers.ValidationError(
                {'confirm_password': 'The two passwords do not match.'})

        # The same check the profile makes when these answers are given again.
        # A rule enforced at one of two entrances is not enforced: an answer
        # nobody offered reads as a no, and decides a funding stream on the way
        # past.
        unrecognised = eligibility_service.unrecognised_answers(
            attrs.get('eligibility') or {})
        if unrecognised:
            raise serializers.ValidationError({'eligibility': unrecognised})

        # Checked on the server, not only in the browser: the previous version
        # ran this rule inside a React component, where calling the API directly
        # bypassed it entirely.
        outcome = eligibility_service.assess(attrs.get('eligibility') or {})
        if not outcome.eligible:
            raise serializers.ValidationError(
                {'eligibility': outcome.message, 'eligibility_title': outcome.title})
        attrs['_eligibility_outcome'] = outcome
        return attrs

    def validate_email(self, value):
        # Matched case-insensitively so a second account cannot be opened by
        # capitalising an address that already exists.
        if User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError('An account already uses this email.')
        return value

    def create(self, validated):
        answers = validated.pop('eligibility', {})
        outcome = validated.pop('_eligibility_outcome', None)
        user = User.objects.create_user(**validated)

        # What the answers say about the person is kept; what they say about a
        # particular course of study belongs to the application, not here.
        user.is_indian_act_registered = eligibility_service._yes(
            answers, 'indian_act_registered')
        user.is_deline_beneficiary = eligibility_service._yes(
            answers, 'deline_beneficiary')

        # The decision itself, saved rather than re-derived. Two of the answers
        # it rests on have no column of their own, so recomputing it later from
        # the account would quietly give a different result — see the comment on
        # User.eligible_streams.
        user.eligible_streams = list(outcome.streams) if outcome else []
        user.eligibility_answers = dict(answers)
        user.eligibility_assessed_at = timezone.now()
        user.save(update_fields=[
            'is_indian_act_registered', 'is_deline_beneficiary',
            'eligible_streams', 'eligibility_answers', 'eligibility_assessed_at',
        ])
        return user
