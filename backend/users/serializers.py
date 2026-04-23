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
            'expected_graduation_date', 'years_in_program', 'institution_location'
        )
        read_only_fields = ('id', 'role', 'date_joined')

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
            'expected_graduation_date', 'years_in_program', 'institution_location'
        )

    def create(self, validated_data):
        # Pass ALL validated_data to create_user (handled by **extra_fields in CustomUserManager)
        user = User.objects.create_user(**validated_data)
        return user
