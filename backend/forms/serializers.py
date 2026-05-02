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
    reviewed_by_name = serializers.SerializerMethodField()
    forwarded_by_name = serializers.SerializerMethodField()
    decided_by_name = serializers.SerializerMethodField()
    more_info_requested_by_name = serializers.SerializerMethodField()

    form_type = serializers.CharField(source='form.title', read_only=True)

    class Meta:
        model = FormSubmission
        fields = (
            'id', 'form', 'form_title', 'form_type', 'student', 'student_name', 'student_details',
            'submitted_at', 'status', 'amount', 'answers', 'notes',
            'reviewed_at', 'reviewed_by', 'reviewed_by_name',
            'forwarded_at', 'forwarded_by', 'forwarded_by_name',
            'decided_at', 'decided_by', 'decided_by_name',
            'decision_reason', 'office_use_data',
            'more_info_requested_at', 'more_info_requested_by',
            'more_info_requested_by_name', 'more_info_request_notes',
            'more_info_responded_at',
            'finance_sent_at', 'finance_sent_by',
        )
        read_only_fields = ('student', 'submitted_at', 'finance_sent_at', 'finance_sent_by')

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.full_name if obj.reviewed_by else None

    def get_forwarded_by_name(self, obj):
        return obj.forwarded_by.full_name if obj.forwarded_by else None

    def get_decided_by_name(self, obj):
        return obj.decided_by.full_name if obj.decided_by else None

    def get_more_info_requested_by_name(self, obj):
        return obj.more_info_requested_by.full_name if obj.more_info_requested_by else None
    
    def get_form_title(self, obj):
        answers = obj.answers.all()
        category_ans = next((a for a in answers if a.field and "Change Categories" in a.field.label), None)
        if not category_ans:
             category_ans = next((a for a in answers if "Change Categories" in (getattr(a, 'field_label', '') or '')), None)

        if category_ans and category_ans.answer_text:
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
            if text in mapping: return mapping[text]
            return text

        import re
        title = obj.form.title if obj.form else "Application"
        if "PSSSP" in title: return "Admission Application"
        title = re.sub(r'^Form\s*[A-Z].*?[:\-\s]+\s*', '', title)
        return title

    def get_student_details(self, obj):
        if obj.student:
            s = obj.student
            base = {
                'id': s.id, 'full_name': s.full_name, 'email': s.email, 'phone': s.phone,
                'beneficiary_number': s.beneficiary_number, 'treaty_number': s.treaty_number,
                'dob': s.dob, 'gender': s.gender, 'pronouns': s.pronouns,
                'mailing_address': s.mailing_address, 'num_dependents': s.num_dependents,
                'disability_accommodation': s.disability_accommodation,
                'institution_name': s.institution_name, 'program_credential': s.program_credential,
                'enrollment_status': s.enrollment_status, 'course_load': s.course_load,
                'current_semester': s.current_semester, 'institution_location': s.institution_location,
                'expected_graduation_date': s.expected_graduation_date,
                'financial_assistance_status': s.financial_assistance_status,
                'is_indian_act_registered': s.is_indian_act_registered,
                'is_deline_beneficiary': s.is_deline_beneficiary,
                'province_of_residence': s.province_of_residence,
                'primary_stream': s.primary_stream, 'secondary_stream': s.secondary_stream,
                'bank_name': s.bank_name, 'transit_number': s.transit_number,
                'inst_number': s.inst_number, 'account_number': s.account_number,
                'account_holder_name': s.account_holder_name, 'account_type': s.account_type,
            }
        else:
            # Guest: extract from answers
            answers = {a.field.label.lower(): a.answer_text for a in obj.answers.all() if a.field}
            def get_ans(keys):
                for k in keys:
                    if k.lower() in answers: return answers[k.lower()]
                return None
            base = {
                'id': f"GUEST-{obj.id}",
                'full_name': get_ans(['full name', 'fullname', 'name']) or f"Guest-{obj.id}",
                'email': get_ans(['email', 'email address']),
                'phone': get_ans(['phone', 'contact']),
                'beneficiary_number': get_ans(['beneficiary number', 'beneficiary #']),
                'dob': get_ans(['dob', 'date of birth']),
                'institution_name': get_ans(['institution', 'school']),
                'program_credential': get_ans(['program', 'degree']),
                'current_semester': get_ans(['semester']),
                'primary_stream': get_ans(['stream', 'funding']),
            }

        request = self.context.get('request')
        if request and request.user.role not in ('admin', 'director'):
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
        validated_data['status'] = 'pending'
        submission = FormSubmission.objects.create(**validated_data)
        
        from .models import FormField
        form_fields = {f.label.lower(): f for f in FormField.objects.filter(form=submission.form)}
        
        answers_to_create = []
        for answer_data in answers_data:
            field_label = answer_data.get('field_label', '')
            if field_label:
                field = form_fields.get(field_label.lower())
                if not field:
                    field = FormField.objects.create(form=submission.form, label=field_label, field_type='text')
                    form_fields[field_label.lower()] = field
                answer_data.pop('field_label', None)
                answers_to_create.append(SubmissionAnswer(submission=submission, field=field, **answer_data))
        
        if answers_to_create:
            SubmissionAnswer.objects.bulk_create(answers_to_create)

        try:
            from api.services.calculation_service import CalculationService
            CalculationService.calculate_and_pay(submission)
        except Exception as e:
            print(f"Calculation Error: {str(e)}")

        try:
            from api.models import DuplicateDetectionLog
            import hashlib
            id_source = submission.student.email if submission.student else "guest"
            for ans in answers_to_create[:3]:
                id_source += (ans.answer_text or "")
            id_hash = hashlib.sha256(id_source.encode()).hexdigest()
            is_flagged = DuplicateDetectionLog.objects.filter(identifier_hash=id_hash).exclude(submission=submission).exists()
            DuplicateDetectionLog.objects.create(submission=submission, identifier_hash=id_hash, is_flagged=is_flagged)
        except Exception as e:
            print(f"Duplicate Detection Error: {str(e)}")

        return submission

class SubmissionNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    class Meta:
        model = SubmissionNote
        fields = ('id', 'author', 'author_name', 'text', 'created_at')
        read_only_fields = ('id', 'author', 'created_at')
