from django.db import models
from django.conf import settings
from programs.models import Program

class Form(models.Model):
    PURPOSE_CHOICES = (
        ('application', 'Application'),
        ('registration', 'Registration'),
        ('survey', 'Survey'),
        ('feedback', 'Feedback'),
        ('other', 'Other'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='forms')
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='application')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.purpose})"

class FormField(models.Model):
    FIELD_TYPE_CHOICES = (
        ('text', 'Text'),
        ('textarea', 'Textarea'),
        ('number', 'Number'),
        ('email', 'Email'),
        ('date', 'Date'),
        ('dropdown', 'Dropdown'),
        ('checkbox', 'Checkbox'),
        ('radio', 'Radio'),
        ('file', 'File'),
    )

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    options = models.JSONField(blank=True, null=True, help_text="Options for dropdown, checkbox, or radio (e.g. ['A', 'B'])")
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.label} ({self.field_type})"

class FormSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('forwarded', 'Forwarded to Director'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('more_info_required', 'More Info Required'),
    )
    
    # Core Fields
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submissions', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    office_use_data = models.JSONField(blank=True, null=True, default=dict)
    
    # Approval Timeline Tracker (Staff Review)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_submissions')
    
    # Forward Step (Staff to Director)
    forwarded_at = models.DateTimeField(null=True, blank=True)
    forwarded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='forwarded_submissions')
    
    # Final Decision Step (Director)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='decided_submissions')
    decision_reason = models.TextField(blank=True, null=True)
    
    # Deadline Tracking
    deadline_met = models.BooleanField(default=True)
    submitted_after_deadline = models.BooleanField(default=False)
    late_application_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_late_submissions')
    late_application_approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Submission for {self.form.title} by {self.student.email}"

class SubmissionAnswer(models.Model):
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='answers')
    field = models.ForeignKey(FormField, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True, null=True)
    answer_file = models.FileField(upload_to='submission_files/', blank=True, null=True)

    def __str__(self):
        return f"Answer for {self.field.label}"

class SubmissionNote(models.Model):
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note by {self.author.email} on {self.submission.id}"


class MidSemesterChange(models.Model):
    """Model for tracking mid-semester changes to applications."""
    
    CHANGE_TYPE_CHOICES = (
        ('enrollment_status', 'Enrollment Status Change'),
        ('dependents', 'Dependents Change'),
        ('institution', 'Institution Change'),
        ('program', 'Program Change'),
        ('other', 'Other Change'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='mid_semester_changes')
    change_type = models.CharField(max_length=50, choices=CHANGE_TYPE_CHOICES)
    old_value = models.TextField()
    new_value = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='submitted_changes')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_changes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    recalculated_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.get_change_type_display()} for Submission {self.submission.id}"


class ApplicationDeadline(models.Model):
    """Model for managing application deadlines per funding stream."""
    
    STREAM_CHOICES = (
        ('PSSSP', 'C-DFN PSSSP'),
        ('UCEPP', 'C-DFN UCEPP'),
        ('DGGR', 'DGGR Bursaries'),
    )
    
    funding_stream = models.CharField(max_length=50, choices=STREAM_CHOICES)
    semester = models.CharField(max_length=50)  # e.g., 'Fall 2025', 'Winter 2026'
    deadline_date = models.DateTimeField()
    late_application_allowed = models.BooleanField(default=False)
    late_application_deadline = models.DateTimeField(null=True, blank=True)
    requires_director_approval = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-deadline_date']
        unique_together = ('funding_stream', 'semester')
    
    def __str__(self):
        return f"{self.get_funding_stream_display()} - {self.semester}"
