from rest_framework import serializers
from .models import Form, FormField, FormSubmission, SubmissionAnswer, SubmissionNote

class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = ('id', 'label', 'field_type', 'options', 'is_required', 'order')

class FormSerializer(serializers.ModelSerializer):
    fields = FormFieldSerializer(many=True, read_only=True)
    
    class Meta:
        model = Form
        fields = ('id', 'title', 'description', 'program', 'purpose', 'is_active', 'fields', 'created_at', 'updated_at')
        read_only_fields = ('created_by', 'created_at', 'updated_at')

class SubmissionAnswerSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(write_only=True, required=False)
    label = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionAnswer
        fields = ('id', 'field', 'field_label', 'label', 'answer_text', 'answer_file')
        extra_kwargs = {'field': {'required': False}}

    def get_label(self, obj):
        return obj.field.label if obj.field else None

class FormSubmissionSerializer(serializers.ModelSerializer):
    answers = SubmissionAnswerSerializer(many=True, required=False)
    form_title = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_details = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    
    class Meta:
        model = FormSubmission
        fields = (
            'id', 'form', 'form_title', 'student', 'student_name', 'student_details',
            'submitted_at', 'status', 'amount', 'answers', 'notes',
            'reviewed_at', 'reviewed_by', 'forwarded_at', 'forwarded_by',
            'decided_at', 'decided_by', 'decision_reason', 'office_use_data'
        )
        read_only_fields = ('student', 'submitted_at')
    
    def get_form_title(self, obj):
        # Try to find a specific purpose or category in the answers
        # This makes the dashboard much more descriptive (e.g. "Dropped / Added Courses" vs "Form D")
        answers = obj.answers.all()
        
        # Look for "Change Categories" (Form D)
        category_ans = next((a for a in answers if a.field and "Change Categories" in a.field.label), None)
        if not category_ans:
             # Fallback check for labels without field relationship (robustness for direct submissions)
             category_ans = next((a for a in answers if "Change Categories" in (getattr(a, 'field_label', '') or '')), None)

        if category_ans and category_ans.answer_text:
            # Map internal keys just in case old data exists
            mapping = {
                'drop': 'Dropped / Added Courses',
                'withdraw': 'Program Withdrawal',
                'school': 'Changed Schools / Programs',
                'dependents': 'Dependent Update',
                'contact': 'Contact Info Update',
                'sfa': 'SFA Status Update',
                'other': 'Other Change'
            }
            text = category_ans.answer_text
            if text in mapping:
                return mapping[text]
            return text

        # Fallback to Form title but strip generic prefixes (Form A: , Form B -, FormA , etc.)
        import re
        title = obj.form.title if obj.form else "Application"
        
        # Specific overrides for legacy/technical names
        if "PSSSP" in title:
            return "Admission Application"
            
        # Matches "Form" + Letter + any separator chars like :, -, dash, or mangled chars
        title = re.sub(r'^Form\s*[A-Z].*?[:\-\u2014\u2013\ufffd\s]+\s*', '', title)
        return title

    def get_student_details(self, obj):
        if not obj.student:
            return None
        s = obj.student
        base = {
            'id': s.id,
            'full_name': s.full_name,
            'email': s.email,
            'phone': s.phone,
            'beneficiary_number': s.beneficiary_number,
            'treaty_number': s.treaty_number,
            'dob': s.dob,
            'gender': s.gender,
            'pronouns': s.pronouns,
            'mailing_address': s.mailing_address,
            'num_dependents': s.num_dependents,
            'disability_accommodation': s.disability_accommodation,
            # Enrollment
            'institution_name': s.institution_name,
            'program_credential': s.program_credential,
            'enrollment_status': s.enrollment_status,
            'course_load': s.course_load,
            'current_semester': s.current_semester,
            'institution_location': s.institution_location,
            'expected_graduation_date': s.expected_graduation_date,
            'financial_assistance_status': s.financial_assistance_status,
            # Banking (only for admin/director)
            'bank_name': s.bank_name,
            'transit_number': s.transit_number,
            'inst_number': s.inst_number,
            'account_number': s.account_number,
            'account_holder_name': s.account_holder_name,
            'account_type': s.account_type,
        }
        request = self.context.get('request')
        if request and request.user.role not in ('admin', 'director'):
            # Strip banking info for non-admin
            for key in ('bank_name', 'transit_number', 'inst_number', 'account_number', 'account_holder_name', 'account_type'):
                base.pop(key, None)
        return base

    def get_notes(self, obj):
        request = self.context.get('request')
        if request and request.user.role in ('admin', 'director'):
            return SubmissionNoteSerializer(obj.notes.all(), many=True).data
        return []

    def create(self, validated_data):
        answers_data = validated_data.pop('answers', [])
        submission = FormSubmission.objects.create(**validated_data)
        for answer_data in answers_data:
            field_label = answer_data.pop('field_label', None)
            field = answer_data.get('field')
            
            if not field and field_label:
                # Try to find the field by label within this form
                from .models import FormField
                field = FormField.objects.filter(form=submission.form, label__icontains=field_label).first()
                if not field:
                    # If still not found, create a dummy field or ignore? 
                    # For now, let's create it to be robust
                    field = FormField.objects.create(
                        form=submission.form, 
                        label=field_label, 
                        field_type='text'
                    )
            
            if field:
                SubmissionAnswer.objects.create(submission=submission, field=field, **answer_data)
        return submission

class SubmissionNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)

    class Meta:
        model = SubmissionNote
        fields = ('id', 'author', 'author_name', 'text', 'created_at')
        read_only_fields = ('id', 'author', 'created_at')
