from django.contrib import admin
from .models import Form, FormField, FormSubmission, SubmissionAnswer

class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 1

class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'program', 'purpose', 'is_active', 'created_at')
    list_filter = ('purpose', 'is_active', 'program')
    search_fields = ('title', 'description')
    inlines = [FormFieldInline]

class SubmissionAnswerInline(admin.TabularInline):
    model = SubmissionAnswer
    extra = 0
    readonly_fields = ('field', 'answer_text', 'answer_file')

class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('form', 'student', 'status', 'submitted_at')
    list_filter = ('status', 'form', 'submitted_at')
    search_fields = ('student__email', 'form__title')
    inlines = [SubmissionAnswerInline]
    readonly_fields = ('form', 'student', 'submitted_at')

admin.site.register(Form, FormAdmin)
admin.site.register(FormSubmission, FormSubmissionAdmin)
