# Database Table Mapping - SQLite to Supabase

## Custom Table Names Reference

All Django models have been configured with custom, readable table names for better database organization and clarity.

### API App Tables

| Model | Table Name | Purpose |
|-------|-----------|---------|
| Profile | `user_profiles` | User profile information (personal details, contact info) |
| Application | `student_applications` | Student funding applications |
| Document | `application_documents` | Documents attached to applications |
| UserDocument | `user_documents` | User-uploaded documents |
| AuditLog | `audit_logs` | System audit trail and activity logs |
| PolicySetting | `policy_settings` | Funding policy configuration and rules |
| PolicyHistory | `policy_history` | Historical changes to policy settings |
| Payment | `payments` | Payment records and disbursements |
| Appeal | `appeals` | Student appeals against decisions |
| ShareableLink | `shareable_links` | Shareable links for applications/submissions |
| DuplicateDetectionLog | `duplicate_detection_logs` | Duplicate detection activity logs |

### Forms App Tables

| Model | Table Name | Purpose |
|-------|-----------|---------|
| Form | `forms` | Form definitions and templates |
| FormField | `form_fields` | Individual form fields |
| FormSubmission | `form_submissions` | Form submission records |
| SubmissionAnswer | `submission_answers` | Answers to form fields |
| SubmissionNote | `submission_notes` | Notes on form submissions |
| MidSemesterChange | `mid_semester_changes` | Mid-semester application changes |
| ApplicationDeadline | `application_deadlines` | Application deadline management |

### Programs App Tables

| Model | Table Name | Purpose |
|-------|-----------|---------|
| Program | `programs` | Funding programs and streams |

### Notifications App Tables

| Model | Table Name | Purpose |
|-------|-----------|---------|
| Notification | `notifications` | User notifications |

### Users App Tables

| Model | Table Name | Purpose |
|-------|-----------|---------|
| CustomUser | `users` | Custom user model with extended fields |

### Django System Tables (Auto-created)

| Table Name | Purpose |
|-----------|---------|
| `auth_user` | Django default user (not used - using CustomUser) |
| `auth_group` | User groups |
| `auth_permission` | Permission definitions |
| `auth_group_permissions` | Group-permission relationships |
| `auth_user_groups` | User-group relationships |
| `auth_user_user_permissions` | User-permission relationships |
| `django_session` | Session management |
| `django_migrations` | Migration tracking |
| `django_content_type` | Content type registry |

## Key Relationships

### User-Related
- `users` (CustomUser) → `user_profiles` (one-to-one)
- `users` → `user_documents` (one-to-many)
- `users` → `student_applications` (one-to-many)
- `users` → `form_submissions` (one-to-many)
- `users` → `payments` (one-to-many)
- `users` → `appeals` (one-to-many)
- `users` → `notifications` (one-to-many)

### Application-Related
- `student_applications` → `application_documents` (one-to-many)
- `student_applications` → `payments` (one-to-many)
- `student_applications` → `appeals` (one-to-many)
- `student_applications` → `shareable_links` (one-to-many)

### Form-Related
- `programs` → `forms` (one-to-many)
- `forms` → `form_fields` (one-to-many)
- `forms` → `form_submissions` (one-to-many)
- `form_submissions` → `submission_answers` (one-to-many)
- `form_submissions` → `submission_notes` (one-to-many)
- `form_submissions` → `mid_semester_changes` (one-to-many)
- `form_submissions` → `shareable_links` (one-to-many)
- `form_submissions` → `duplicate_detection_logs` (one-to-many)

### Policy-Related
- `policy_settings` → `policy_history` (one-to-many)

## Migration Steps

1. **Update `.env`** with Supabase credentials
2. **Create migrations**: `python manage.py makemigrations`
3. **Apply migrations**: `python manage.py migrate`
4. **Verify tables** in Supabase dashboard

## Querying Examples

### Using Django ORM (No changes needed)
```python
# These queries work the same way - Django handles table mapping
from api.models import Profile, Application
from forms.models import FormSubmission

# Get user profile
profile = Profile.objects.get(user_id=1)

# Get applications
apps = Application.objects.filter(student_id=1)

# Get form submissions
submissions = FormSubmission.objects.all()
```

### Direct SQL Queries (if needed)
```sql
-- Get user profiles
SELECT * FROM user_profiles;

-- Get applications for a student
SELECT * FROM student_applications WHERE student_id = 1;

-- Get form submissions
SELECT * FROM form_submissions;

-- Join users with profiles
SELECT u.email, p.phone_number 
FROM users u 
LEFT JOIN user_profiles p ON u.id = p.user_id;
```

## Benefits of Custom Table Names

✅ **Readability**: Clear, descriptive names (e.g., `user_profiles` vs `api_profile`)
✅ **Organization**: Logical grouping by function
✅ **Maintainability**: Easier to understand database structure
✅ **Consistency**: Follows naming conventions across the project
✅ **Scalability**: Easier to add new tables with consistent naming

## Notes

- All table names are lowercase with underscores (snake_case)
- Foreign key columns follow Django's convention: `{model_name}_id`
- Primary keys are auto-incrementing integers (except PolicySetting which uses UUID)
- Timestamps use UTC timezone
- All relationships are properly indexed for performance
