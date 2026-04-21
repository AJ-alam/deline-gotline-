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
    
    class Meta:
        model = SubmissionAnswer
        fields = ('id', 'field', 'field_label', 'answer_text', 'answer_file')
        extra_kwargs = {'field': {'required': False}}

class FormSubmissionSerializer(serializers.ModelSerializer):
    answers = SubmissionAnswerSerializer(many=True, required=False)
    form_title = serializers.CharField(source='form.title', read_only=True)
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

    def get_student_details(self, obj):
        if obj.student:
            return {
                'id': obj.student.id,
                'full_name': obj.student.full_name,
                'email': obj.student.email,
                'phone': obj.student.phone,
                'beneficiary_number': obj.student.beneficiary_number,
                'treaty_number': obj.student.treaty_number,
                'dob': obj.student.dob
            }
        return None

    def get_notes(self, obj):
        # Only admins should see notes? For now let's return them
        # if the request user is staff.
        request = self.context.get('request')
        if request and (request.user.is_staff or request.user.role in ['admin', 'director']):
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
