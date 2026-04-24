# Supabase Migration Checklist

## Pre-Migration

- [ ] Backup current SQLite database
  ```bash
  cp backend/db.sqlite3 backend/db.sqlite3.backup
  ```

- [ ] Verify all dependencies are installed
  ```bash
  pip install -r backend/requirements.txt
  ```

- [ ] Check Django version
  ```bash
  python -c "import django; print(django.VERSION)"
  ```

- [ ] Verify psycopg2 is installed
  ```bash
  python -c "import psycopg2; print(psycopg2.__version__)"
  ```

## Supabase Setup

- [ ] Create Supabase account at https://app.supabase.com
- [ ] Create new project
- [ ] Wait for project to initialize (2-3 minutes)
- [ ] Navigate to Settings > Database
- [ ] Copy database credentials:
  - [ ] Host: `db.whxqwxwznrsqahsjrfih.supabase.co`
  - [ ] Port: `5432`
  - [ ] Database: `postgres`
  - [ ] User: `postgres`
  - [ ] Password: ___________________

## Configuration

- [ ] Update `backend/.env` with Supabase credentials
  ```env
  DATABASE_URL=postgresql://postgres:[PASSWORD]@db.whxqwxwznrsqahsjrfih.supabase.co:5432/postgres?sslmode=require
  ```

- [ ] Verify `.env` is in `.gitignore`
  ```bash
  grep ".env" backend/.gitignore
  ```

- [ ] Test connection string format
  ```bash
  cd backend
  python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DATABASE_URL'))"
  ```

## Model Updates

- [ ] Verify all models have custom table names
  - [ ] `backend/api/models.py` - 11 models updated
  - [ ] `backend/forms/models.py` - 7 models updated
  - [ ] `backend/programs/models.py` - 1 model updated
  - [ ] `backend/notifications/models.py` - 1 model updated
  - [ ] `backend/users/models.py` - 1 model updated

- [ ] Check for any custom migrations
  ```bash
  ls backend/api/migrations/
  ls backend/forms/migrations/
  ```

## Migration Execution

### Option A: Automated (Recommended)

- [ ] Run Python migration script
  ```bash
  cd backend
  python migrate_to_supabase.py
  ```

- [ ] Verify script output shows:
  - [ ] ✅ .env file configured
  - [ ] ✅ Backup created (if migrating from SQLite)
  - [ ] ✅ Migrations created
  - [ ] ✅ Migrations applied to Supabase
  - [ ] ✅ Data loaded (if applicable)
  - [ ] ✅ Connection verified
  - [ ] ✅ Tables verified

### Option B: Manual Steps

- [ ] Create migrations
  ```bash
  cd backend
  python manage.py makemigrations
  ```

- [ ] Review migration files
  ```bash
  ls backend/api/migrations/
  ```

- [ ] Apply migrations
  ```bash
  python manage.py migrate
  ```

- [ ] Verify no errors in output

## Post-Migration Verification

### Django Level

- [ ] Test Django shell connection
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

- [ ] Verify tables exist
  ```python
  from django.apps import apps
  for model in apps.get_models():
      print(f"{model.__name__} -> {model._meta.db_table}")
  ```

- [ ] Test basic queries
  ```python
  from users.models import CustomUser
  users = CustomUser.objects.all()
  print(f"Total users: {users.count()}")
  ```

### Supabase Dashboard

- [ ] Go to https://app.supabase.com
- [ ] Select your project
- [ ] Click **SQL Editor**
- [ ] Run query to count tables:
  ```sql
  SELECT COUNT(*) as table_count 
  FROM information_schema.tables 
  WHERE table_schema = 'public';
  ```
  Expected: 30+ tables

- [ ] Verify key tables exist:
  ```sql
  SELECT table_name 
  FROM information_schema.tables 
  WHERE table_schema = 'public' 
  ORDER BY table_name;
  ```

- [ ] Check table row counts:
  ```sql
  SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
  FROM pg_stat_user_tables
  ORDER BY n_live_tup DESC;
  ```

### Data Verification

- [ ] If migrating from SQLite, verify data:
  ```bash
  cd backend
  python manage.py shell
  ```
  
  Then:
  ```python
  from users.models import CustomUser
  from api.models import Application
  from forms.models import FormSubmission
  
  print(f"Users: {CustomUser.objects.count()}")
  print(f"Applications: {Application.objects.count()}")
  print(f"Submissions: {FormSubmission.objects.count()}")
  ```

## User Management

- [ ] Create superuser
  ```bash
  cd backend
  python manage.py createsuperuser
  ```

- [ ] Verify superuser created
  ```bash
  cd backend
  python manage.py shell
  ```
  
  Then:
  ```python
  from users.models import CustomUser
  admin = CustomUser.objects.get(email='admin@example.com')
  print(f"Admin: {admin.email}, Role: {admin.role}")
  ```

## Application Testing

- [ ] Start Django development server
  ```bash
  cd backend
  python manage.py runserver
  ```

- [ ] Test API endpoints
  - [ ] GET /api/users/
  - [ ] GET /api/applications/
  - [ ] GET /api/forms/

- [ ] Test admin panel
  - [ ] Go to http://localhost:8000/admin
  - [ ] Login with superuser credentials
  - [ ] Verify tables are accessible

- [ ] Test form submissions
  - [ ] Create a test form
  - [ ] Submit test data
  - [ ] Verify data in database

## Performance Testing

- [ ] Check query performance
  ```bash
  cd backend
  python manage.py shell
  ```
  
  Then:
  ```python
  from django.db import connection
  from django.test.utils import CaptureQueriesContext
  
  with CaptureQueriesContext(connection) as context:
      from users.models import CustomUser
      users = list(CustomUser.objects.all())
  
  print(f"Queries: {len(context)}")
  for query in context:
      print(f"Time: {query['time']}s - {query['sql'][:100]}")
  ```

- [ ] Monitor Supabase dashboard
  - [ ] Check query performance
  - [ ] Monitor connection count
  - [ ] Check storage usage

## Backup & Recovery

- [ ] Verify backup files created
  ```bash
  ls -la backend/backups/
  ```

- [ ] Test backup restoration (optional)
  ```bash
  # Switch to SQLite
  # Update DATABASE_URL in .env
  # Run: python manage.py migrate
  # Load backup: python manage.py loaddata backend/backups/data.*.json
  ```

## Documentation

- [ ] Review QUICK_START.md
- [ ] Review TABLE_MAPPING.md
- [ ] Review DATABASE_SCHEMA.md
- [ ] Review SUPABASE_MIGRATION_GUIDE.md
- [ ] Update team documentation

## Deployment Preparation

- [ ] Update production `.env` with Supabase credentials
- [ ] Set `DEBUG=False` in production
- [ ] Configure allowed hosts
- [ ] Set up SSL certificates
- [ ] Configure CORS settings
- [ ] Set up logging and monitoring

- [ ] Test production deployment
  ```bash
  cd backend
  DEBUG=False python manage.py collectstatic --noinput
  ```

- [ ] Verify static files collected
  ```bash
  ls -la backend/staticfiles/
  ```

## Rollback Plan (if needed)

- [ ] Keep SQLite backup
  ```bash
  ls backend/db.sqlite3.backup
  ```

- [ ] Keep data backup
  ```bash
  ls backend/backups/data.*.json
  ```

- [ ] Document rollback steps
  - [ ] Update DATABASE_URL to SQLite
  - [ ] Run migrations
  - [ ] Restore data if needed

## Final Checklist

- [ ] ✅ All models updated with custom table names
- [ ] ✅ Environment configured with Supabase credentials
- [ ] ✅ Migrations created and applied
- [ ] ✅ Connection verified
- [ ] ✅ Tables verified in Supabase
- [ ] ✅ Data verified (if migrating)
- [ ] ✅ Superuser created
- [ ] ✅ Application tested
- [ ] ✅ Performance verified
- [ ] ✅ Backups created
- [ ] ✅ Documentation updated
- [ ] ✅ Team notified
- [ ] ✅ Ready for production

## Post-Migration Tasks

- [ ] Monitor application for 24 hours
- [ ] Check error logs
- [ ] Verify all features working
- [ ] Get team feedback
- [ ] Update deployment documentation
- [ ] Schedule regular backups
- [ ] Set up monitoring alerts

## Support Contacts

- **Supabase Support**: https://supabase.com/support
- **Django Documentation**: https://docs.djangoproject.com/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/

## Notes

```
Migration Date: _______________
Migrated By: ___________________
Supabase Project: ______________
Database: ______________________
Notes: __________________________
________________________________
```

---

**Status**: ⬜ Not Started | 🟡 In Progress | ✅ Complete

**Overall Progress**: _____ / 100%

**Estimated Time**: 30-60 minutes

**Difficulty Level**: 🟢 Easy | 🟡 Medium | 🔴 Hard
