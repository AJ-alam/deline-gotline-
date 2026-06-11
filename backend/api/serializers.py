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
            'id', 'email', 'full_name', 'role', 'profile',
            'num_dependents', 'financial_assistance_status', 'enrollment_status',
            'institution_name', 'program_credential', 'current_semester',
            'course_load', 'institution_location', 'dob'
        )

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ('id', 'application', 'name', 'file', 'is_verified', 'uploaded_at')

class UserDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = UserDocument
        fields = ('id', 'user', 'name', 'file', 'file_url', 'category', 'uploaded_at')
        read_only_fields = ('id', 'user', 'uploaded_at')

    def get_file_url(self, obj):
        if not obj.file:
            return None
        # obj.file.url calls SupabaseStorage.url() which returns the full public URL
        try:
            return obj.file.url
        except Exception:
            return None

class ApplicationSerializer(serializers.ModelSerializer):
    student_details = UserSerializer(source='student', read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = (
            'id', 'student', 'student_details', 'form_type', 'status', 'amount',
            'semester', 'academic_year', 'institution', 'program', 'form_data',
            'created_at', 'updated_at',
            'ssw_submitted_at', 'decision_by', 'decision_at', 'decision_notes',
            'finance_sent_at', 'finance_sent_by',
            'documents',
        )
        read_only_fields = ('id', 'student', 'created_at', 'updated_at', 'student_details', 'documents')

class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_details = UserSerializer(source='performed_by', read_only=True)
    class Meta:
        model = AuditLog
        fields = (
            'id', 'action', 'timestamp', 'performed_by', 'performed_by_details',
            'role', 'application', 'details',
        )
        read_only_fields = fields

class PolicyHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyHistory
        fields = (
            'id', 'setting', 'user_name', 'field_changed',
            'old_value', 'new_value', 'effective_date', 'timestamp',
        )
        read_only_fields = ('id', 'timestamp')

class PolicySettingSerializer(serializers.ModelSerializer):
    last_updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PolicySetting
        fields = (
            'id', 'section', 'field_key', 'field_label', 'value', 'unit',
            'is_active', 'effective_date',
            'last_updated_by', 'last_updated_by_name', 'last_updated_at',
        )
        read_only_fields = ('id', 'last_updated_by', 'last_updated_at')

    def get_last_updated_by_name(self, obj):
        if obj.last_updated_by:
            return obj.last_updated_by.full_name or obj.last_updated_by.email
        return None

class PaymentSerializer(serializers.ModelSerializer):
    student_details = UserSerializer(source='user', read_only=True)
    # Surface submission metadata so the Payments dashboard can group payments by
    # their originating form submission when no legacy Application FK is set
    # (calculation_service creates payments with application_id=None, linking via
    # `submission` only — without this, the UI would show "No application linked").
    submission_details = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = (
            'id', 'user', 'student_details', 'application', 'submission', 'submission_details',
            'amount', 'payment_type', 'status', 'date_issued', 'reference_number',
        )
        read_only_fields = ('id', 'date_issued', 'reference_number', 'student_details', 'submission_details')

    def get_submission_details(self, obj):
        sub = obj.submission
        if not sub:
            return None
        return {
            'id': sub.id,
            'form_title': sub.form.title if sub.form else None,
            'status': sub.status,
            'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None,
            'amount': str(sub.amount) if sub.amount is not None else None,
        }

class AppealSerializer(serializers.ModelSerializer):
    student_details = UserSerializer(source='user', read_only=True)
    class Meta:
        model = Appeal
        fields = (
            'id', 'user', 'student_details', 'application', 'reason',
            'status', 'decision', 'created_at', 'updated_at',
            'escalation_level', 'escalated_at', 'escalation_notes',
        )
        read_only_fields = (
            'id', 'user', 'created_at', 'updated_at', 'student_details',
            'escalated_at',
        )

class ShareableLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareableLink
        fields = (
            'id', 'token', 'application', 'submission',
            'created_at', 'expires_at', 'is_active',
        )
        read_only_fields = ('id', 'token', 'created_at')
