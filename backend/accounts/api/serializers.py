"""User-facing account data."""

from rest_framework import serializers

from accounts.models import BankAccount, User


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
                  'role', 'role_label', 'date_joined', 'bank_account')
        read_only_fields = ('id', 'email', 'role', 'role_label', 'date_joined',
                            'full_name', 'display_name', 'bank_account')

    def get_bank_account(self, user):
        current = user.bank_accounts.filter(is_current=True).first()
        return BankAccountSerializer(current).data if current else None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'phone')

    def validate_email(self, value):
        # Matched case-insensitively so a second account cannot be opened by
        # capitalising an address that already exists.
        if User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError('An account already uses this email.')
        return value

    def create(self, validated):
        return User.objects.create_user(**validated)
