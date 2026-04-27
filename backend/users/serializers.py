from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Allow either 'username' or 'email' as the identifying field
        # SimpleJWT defaults to 'username', but our frontend sends 'email'
        if 'email' in attrs and 'username' not in attrs:
            attrs['username'] = attrs['email']
        return super().validate(attrs)

class UserSerializer(serializers.ModelSerializer):
    # Profile model fields — read via SerializerMethodField; write captured in to_internal_value
    town_city = serializers.SerializerMethodField()
    postal_code = serializers.SerializerMethodField()
    institute = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'full_name', 'phone', 'role', 'profile_picture',
            'beneficiary_number', 'treaty_number', 'dob', 'date_joined',
            'bank_name', 'transit_number', 'inst_number', 'account_number',
            'primary_stream', 'secondary_stream', 'preferred_name', 'gender',
            'pronouns', 'alternate_phone', 'mailing_address', 'num_dependents',
            'dependent_ages', 'disability_accommodation', 'upi',
            'financial_assistance_status', 'account_holder_name', 'account_type',
            'institution_name', 'program_credential', 'current_semester',
            'enrollment_status', 'course_load', 'program_type',
            'expected_graduation_date', 'years_in_program', 'institution_location',
            'town_city', 'postal_code', 'institute',
            'is_indian_act_registered', 'is_deline_beneficiary', 'province_of_residence',
        )
        # profile_picture is ImageField — sending a URL string back in PUT fails validation.
        # Keep read_only so display works but JSON PUT can't accidentally break it.
        read_only_fields = ('id', 'role', 'date_joined', 'profile_picture',
                            'town_city', 'postal_code', 'institute')

    def get_town_city(self, obj):
        return getattr(getattr(obj, 'profile', None), 'town_city', None)

    def get_postal_code(self, obj):
        return getattr(getattr(obj, 'profile', None), 'postal_code', None)

    def get_institute(self, obj):
        return getattr(getattr(obj, 'profile', None), 'institute', None)

    _PROFILE_FIELDS = ('town_city', 'postal_code', 'institute')

    def to_internal_value(self, data):
        # Capture profile-only fields before normal validation (they're not on CustomUser model)
        self._profile_data = {k: data[k] for k in self._PROFILE_FIELDS if k in data}
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        # Update CustomUser fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Write profile-only fields to the Profile record
        profile_data = getattr(self, '_profile_data', {})
        if profile_data:
            from api.models import Profile
            profile_obj, _ = Profile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                if value is not None:
                    setattr(profile_obj, attr, value)
            profile_obj.save()

        return instance

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'full_name', 'password', 'phone', 'role',
            'beneficiary_number', 'treaty_number', 'dob',
            'bank_name', 'transit_number', 'inst_number', 'account_number',
            'primary_stream', 'secondary_stream', 'preferred_name', 'gender',
            'pronouns', 'alternate_phone', 'mailing_address', 'num_dependents',
            'dependent_ages', 'disability_accommodation', 'upi',
            'financial_assistance_status', 'account_holder_name', 'account_type',
            'institution_name', 'program_credential', 'current_semester',
            'enrollment_status', 'course_load', 'program_type',
            'expected_graduation_date', 'years_in_program', 'institution_location',
            'is_indian_act_registered', 'is_deline_beneficiary', 'province_of_residence',
        )

    def validate_role(self, value):
        # Only allow 'student' role via self-registration.
        # Admin and Director accounts must be created by an existing admin.
        if value in ('admin', 'director'):
            raise serializers.ValidationError(
                "You cannot register with an elevated role. Contact an administrator."
            )
        return value

    def create(self, validated_data):
        # Default role to 'student' if not provided
        validated_data.setdefault('role', 'student')
        # Pass ALL validated_data to create_user (handled by **extra_fields in CustomUserManager)
        user = User.objects.create_user(**validated_data)
        return user
