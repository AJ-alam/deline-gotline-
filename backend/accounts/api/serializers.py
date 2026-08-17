"""User-facing account data."""

from django.utils import timezone
from rest_framework import serializers

from accounts.models import BankAccount, User
from accounts.services import eligibility as eligibility_service


class BankAccountSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source='masked_account_number', read_only=True)

    class Meta:
        model = BankAccount
        # The full account number is never returned. It is written once and read
        # only by the finance export.
        fields = ('id', 'account_holder', 'transit_number', 'institution_number',
                  'account_number', 'is_current', 'added_at')
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
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
        read_only_fields = ('id', 'email', 'role', 'role_label', 'date_joined',
                            'full_name', 'display_name', 'bank_account',
                            'eligible_streams', 'eligibility_assessed_at')

    def get_bank_account(self, user):
        current = user.bank_accounts.filter(is_current=True).first()
        return BankAccountSerializer(current).data if current else None


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
