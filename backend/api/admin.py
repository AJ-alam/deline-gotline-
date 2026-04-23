from django.contrib import admin
from .models import Profile, Application, Document, AuditLog

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'beneficiary_number', 'is_sfa_active', 'profile_completeness')
    search_fields = ('user__username', 'beneficiary_number')

class DocumentInline(admin.TabularInline):
    model = Document
    extra = 1

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'form_type', 'student', 'status', 'semester', 'created_at')
    list_filter = ('status', 'form_type', 'semester')
    search_fields = ('student__username', 'form_type', 'institution')
    inlines = [DocumentInline]
    
    actions = ['approve_applications', 'deny_applications']

    def approve_applications(self, request, queryset):
        queryset.update(status='approved')
    approve_applications.short_description = "Approve selected applications"

    def deny_applications(self, request, queryset):
        queryset.update(status='denied')
    deny_applications.short_description = "Deny selected applications"

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'application', 'is_verified', 'uploaded_at')
    list_filter = ('is_verified',)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'performed_by', 'timestamp', 'application')
    list_filter = ('action', 'timestamp')
