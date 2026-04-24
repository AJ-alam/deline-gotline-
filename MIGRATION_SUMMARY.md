# Supabase Migration Summary

## What Was Changed

### 1. **Environment Configuration** (`backend/.env`)
- Updated DATABASE_URL to use Supabase PostgreSQL connection string
- Added placeholder for Supabase credentials
- Kept SQLite option commented for local development

### 2. **Model Updates** - Added Custom Table Names

All Django models now have custom, readable table names via `db_table` in Meta class:

#### API App (`backend/api/models.py`)
- `Profile` → `user_profiles`
- `Application` → `student_applications`
- `Document` → `application_documents`
- `UserDocument` → `user_documents`
- `AuditLog` → `audit_logs`
- `PolicySetting` → `policy_settings`
- `PolicyHistory` → `policy_history`
- `Payment` → `payments`
- `Appeal` → `appeals`
- `ShareableLink` → `shareable_links`
- `DuplicateDetectionLog` → `duplicate_detection_logs`

#### Forms App (`backend/forms/models.py`)
- `Form` → `forms`
- `FormField` → `form_fields`
- `FormSubmission` → `form_submissions`
- `SubmissionAnswer` → `submission_answers`
- `SubmissionNote` → `submission_notes`
- `MidSemesterChange` → `mid_semester_changes`
- `ApplicationDeadline` → `application_deadlines`

#### Programs App (`backend/programs/models.py`)
- `Program` → `programs`

#### Notifications App (`backend/notifications/models.py`)
- `Notification` → `notifications`

#### Users App (`backend/users/models.py`)
- `CustomUser` → `users`

### 3. **Documentation Created**

- **SUPABASE_MIGRATION_GUIDE.md** - Complete migration instructions
- **TABLE_MAPPING.md** - Database table reference and relationships
- **backend/migrate_to_supabase.sh** - Bash migration script
- **backend/migrate_to_supabase.py** - Python migration script (Windows compatible)

## Next Steps

### 1. Get Supabase Credentials
```
Go to: https://app.supabase.com
Select your project → Settings > Database
Copy: Host, Port, Database, User, Password
```

### 2. Update `.env` File
```bash
# Replace [YOUR_PASSWORD] with actual Supabase password
DATABASE_URL=postgresql://postgres:[YOUR_PASSWORD]@db.whxqwxwznrsqahsjrfih.supabase.co:5432/postgres?sslmode=require
```

### 3. Run Migration (Choose One)

**Option A: Using Python Script (Recommended for Windows)**
```bash
cd backend
python migrate_to_supabase.py
```

**Option B: Manual Steps**
```bash
cd backend

# Create migrations
python manage.py makemigrations

# Apply migrations to Supabase
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Verify connection
python manage.py shell
# Then run:
# from django.db import connection
# with connection.cursor() as cursor:
#     cursor.execute("SELECT version();")
#     print(cursor.fetchone())
```

### 4. Verify in Supabase Dashboard
- Go to Supabase Dashboard
- Select your project
- Navigate to SQL Editor
- Run: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';`
- Verify all tables are created with correct names

## Key Features

✅ **Custom Table Names** - Readable, descriptive names instead of Django defaults
✅ **Backward Compatible** - All Django ORM queries work unchanged
✅ **Production Ready** - SSL/TLS encryption enabled
✅ **Data Preservation** - Option to migrate existing SQLite data
✅ **Easy Rollback** - Can switch back to SQLite for development

## Database Connection Details

### Direct Connection (Recommended for Django)
- **Port**: 5432
- **Best for**: Long-lived connections, web applications
- **Connection string**: `postgresql://postgres:[PASSWORD]@db.whxqwxwznrsqahsjrfih.supabase.co:5432/postgres?sslmode=require`

### Connection Pooler (Optional)
- **Port**: 6543
- **Best for**: Serverless functions, stateless applications
- **Connection string**: `postgresql://postgres:[PASSWORD]@db.whxqwxwznrsqahsjrfih.supabase.co:6543/postgres?sslmode=require`

## Table Summary

**Total Tables**: 30+
- **API App**: 11 tables
- **Forms App**: 7 tables
- **Programs App**: 1 table
- **Notifications App**: 1 table
- **Users App**: 1 table
- **Django System**: 8+ tables

## Important Notes

1. **No Code Changes Required** - All Django ORM queries work as-is
2. **Foreign Keys** - All relationships are preserved
3. **Indexes** - All indexes are created automatically
4. **Constraints** - Unique and NOT NULL constraints are enforced
5. **Timestamps** - All timestamps use UTC timezone

## Troubleshooting

### Connection Issues
- Verify Supabase project is active (not paused)
- Check password is correct
- Ensure `?sslmode=require` is in DATABASE_URL

### Migration Errors
- Run `python manage.py makemigrations` first
- Check for conflicting migrations
- Verify all dependencies are installed

### Data Loss Prevention
- Backups are created automatically by migration script
- Check `backend/backups/` directory for backup files
- Keep `data_backup.json` for recovery

## Support

- **Supabase Docs**: https://supabase.com/docs
- **Django Docs**: https://docs.djangoproject.com/en/5.2/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

## Files Modified

```
backend/
├── .env (updated)
├── api/models.py (updated)
├── forms/models.py (updated)
├── programs/models.py (updated)
├── notifications/models.py (updated)
├── users/models.py (updated)
├── migrate_to_supabase.py (new)
└── migrate_to_supabase.sh (new)

Root:
├── SUPABASE_MIGRATION_GUIDE.md (new)
├── TABLE_MAPPING.md (new)
└── MIGRATION_SUMMARY.md (this file)
```

## Ready to Migrate?

1. ✅ Models updated with custom table names
2. ✅ Environment configuration prepared
3. ✅ Migration scripts created
4. ✅ Documentation complete

**Next**: Update `.env` with Supabase credentials and run migration!
