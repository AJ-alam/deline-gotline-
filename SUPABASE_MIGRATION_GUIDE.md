# SQLite to Supabase PostgreSQL Migration Guide

## Overview
This guide walks you through migrating your Django project from SQLite to Supabase PostgreSQL. Your project is already configured to support both databases via `dj-database-url`.

## Prerequisites
- Supabase account and project created
- Supabase project URL and credentials
- Python 3.8+
- All dependencies installed: `pip install -r backend/requirements.txt`

## Step 1: Get Supabase Credentials

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Navigate to **Settings > Database**
4. Copy the connection details:
   - **Host**: `db.whxqwxwznrsqahsjrfih.supabase.co`
   - **Port**: `5432` (Direct) or `6543` (Pooler)
   - **Database**: `postgres`
   - **User**: `postgres`
   - **Password**: Your database password (shown in dashboard)

## Step 2: Update Environment Variables

Edit `backend/.env` and replace the placeholder password:

```env
DATABASE_URL=postgresql://postgres:[YOUR_PASSWORD]@db.whxqwxwznrsqahsjrfih.supabase.co:5432/postgres?sslmode=require
```

**Important**: 
- Replace `[YOUR_PASSWORD]` with your actual Supabase password
- Use port `5432` for persistent connections (recommended for Django)
- Use port `6543` for serverless/stateless applications
- Always include `?sslmode=require` for security

## Step 3: Verify Dependencies

Your `requirements.txt` already includes:
- ✅ `psycopg2-binary==2.9.11` - PostgreSQL adapter
- ✅ `dj-database-url==3.1.2` - Database URL parser
- ✅ `Django==5.2.13` - Django framework

No additional packages needed!

## Step 4: Create and Run Migrations

### Option A: Fresh Database (Recommended for new Supabase project)

```bash
cd backend

# Create fresh migrations
python manage.py makemigrations

# Apply all migrations to Supabase
python manage.py migrate
```

### Option B: Migrate Existing Data from SQLite

If you have existing data in SQLite that you want to preserve:

```bash
cd backend

# Export data from SQLite
python manage.py dumpdata > data_backup.json

# Create fresh migrations
python manage.py makemigrations

# Apply migrations to Supabase
python manage.py migrate

# Load data into Supabase
python manage.py loaddata data_backup.json
```

## Step 5: Verify Connection

Test the connection with Django shell:

```bash
cd backend
python manage.py shell
```

Then run:
```python
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT version();")
    print(cursor.fetchone())
```

You should see PostgreSQL version information.

## Step 6: Create Superuser (if needed)

```bash
cd backend
python manage.py createsuperuser
```

## Database Schema Overview

Your Django models will create the following tables in Supabase:

### Core Tables
- `auth_user` - Django user authentication
- `auth_group` - User groups
- `auth_permission` - Permissions
- `django_session` - Session management
- `django_migrations` - Migration tracking

### API App Tables
- `api_profile` - User profiles with personal info
- `api_application` - Student applications
- `api_document` - Application documents
- `api_userdocument` - User documents
- `api_auditlog` - Audit trail
- `api_policysetting` - Policy configuration
- `api_policyhistory` - Policy change history
- `api_payment` - Payment records
- `api_appeal` - Appeals
- `api_shareablelink` - Shareable links
- `api_duplicatedetectionlog` - Duplicate detection logs

### Forms App Tables
- `forms_form` - Form definitions
- `forms_formfield` - Form fields
- `forms_formsubmission` - Form submissions
- `forms_submissionanswer` - Submission answers
- `forms_submissionnote` - Submission notes
- `forms_midsemesterchange` - Mid-semester changes
- `forms_applicationdeadline` - Application deadlines

### Programs App Tables
- `programs_program` - Program definitions

### Notifications App Tables
- `notifications_notification` - Notifications

### Dashboard App Tables
- `dashboard_*` - Dashboard-related tables

### Users App Tables
- `users_customuser` - Custom user model

## Important Notes

### Table Naming
Django automatically converts model names to lowercase table names:
- `Profile` → `api_profile`
- `Application` → `api_application`
- `FormSubmission` → `forms_formsubmission`

### Indexes
Django creates indexes for:
- Primary keys (id)
- Foreign keys
- Fields marked with `db_index=True`
- Unique fields

### Constraints
- Foreign key relationships are enforced
- Unique constraints are applied
- NOT NULL constraints follow model definitions

## Troubleshooting

### Connection Refused
- Verify Supabase project is active (not paused)
- Check password is correct
- Ensure IP is whitelisted (Supabase allows all IPs by default)

### SSL Certificate Error
- Ensure `?sslmode=require` is in DATABASE_URL
- Update psycopg2: `pip install --upgrade psycopg2-binary`

### Migration Conflicts
- Delete `db.sqlite3` after successful migration
- Keep `backend/.env` with Supabase credentials

### Slow Queries
- Check Supabase dashboard for query performance
- Add indexes for frequently queried fields
- Consider connection pooling (port 6543)

## Switching Back to SQLite (Development)

To temporarily use SQLite for local development:

```env
DATABASE_URL=sqlite:///db.sqlite3
```

Then run migrations again:
```bash
python manage.py migrate
```

## Production Deployment

When deploying to production:

1. Set `DEBUG=False` in `.env`
2. Use Supabase connection string in production environment
3. Run migrations on deployment:
   ```bash
   python manage.py migrate --noinput
   ```
4. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

## Security Best Practices

1. **Never commit credentials** - Keep `.env` in `.gitignore`
2. **Use strong passwords** - Supabase generates secure passwords
3. **Enable SSL** - Always use `?sslmode=require`
4. **Rotate passwords regularly** - Change in Supabase dashboard
5. **Use environment variables** - Never hardcode credentials
6. **Backup regularly** - Use Supabase backup features

## Support Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Django Database Documentation](https://docs.djangoproject.com/en/5.2/ref/databases/postgresql/)
- [psycopg2 Documentation](https://www.psycopg.org/psycopg2/docs/)
- [dj-database-url](https://github.com/jacobian/dj-database-url)

## Next Steps

1. ✅ Update `.env` with Supabase credentials
2. ✅ Run migrations: `python manage.py migrate`
3. ✅ Create superuser: `python manage.py createsuperuser`
4. ✅ Test connection in Django shell
5. ✅ Verify all tables in Supabase dashboard
6. ✅ Run your application and test functionality
