from rest_framework import serializers
from django.contrib.auth import get_user_model
User = get_user_model()
from .models import Profile, Application, Document, AuditLog, UserDocument, PolicySetting, PolicyHistory, Payment, Appeal, ShareableLink

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('beneficiary_number', 'indian_status', 'phone_number', 'mailing_address', 'town_city', 'postal_code', 'institute', 'is_sfa_active', 'profile_completeness', 'preferred_name', 'date_of_birth', 'gender', 'pronouns', 'alt_phone_number')

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'full_name', 'role', 'profile',
            'num_dependents', 'financial_assistance_status', 'enrollment_status',
            'institution_name', 'program_credential', 'current_semester',
            'course_load', 'institution_location', 'dob'
        )

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'

class UserDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDocument
        fields = ('id', 'user', 'name', 'file', 'category', 'uploaded_at')
        read_only_fields = ('id', 'user', 'uploaded_at')

class ApplicationSerializer(serializers.ModelSerializer):
    student_details = UserSerializer(source='student', read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Application
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_details = UserSerializer(source='performed_by', read_only=True)
    class Meta:
        model = AuditLog
        fields = '__all__'

class PolicyHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyHistory
        fields = '__all__'

class PolicySettingSerializer(serializers.ModelSerializer):
    last_updated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PolicySetting
        fields = ('id', 'section', 'field_key', 'field_label', 'value', 'unit', 'last_updated_by', 'last_updated_by_name', 'last_updated_at')
        read_only_fields = ('id', 'last_updated_by', 'last_updated_at')

    def get_last_updated_by_name(self, obj):
        if obj.last_updated_by:
            return obj.last_updated_by.get_full_name() or obj.last_updated_by.username
        return None

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

class AppealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appeal
        fields = '__all__'

class ShareableLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareableLink
        fields = '__all__'
