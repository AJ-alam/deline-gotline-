# Quick Start - Supabase Migration

## 5-Minute Setup

### Step 1: Get Credentials (2 min)
1. Go to https://app.supabase.com
2. Select your project
3. Click **Settings > Database**
4. Copy your **password** (you'll need this)

### Step 2: Update `.env` (1 min)
Edit `backend/.env`:
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD_HERE@db.whxqwxwznrsqahsjrfih.supabase.co:5432/postgres?sslmode=require
```

Replace `YOUR_PASSWORD_HERE` with your actual Supabase password.

### Step 3: Run Migration (2 min)
```bash
cd backend
python migrate_to_supabase.py
```

That's it! ✅

---

## What Happened?

✅ All tables created in Supabase with readable names
✅ Data backed up (if migrating from SQLite)
✅ Connection verified
✅ Ready to use

---

## Verify It Worked

### In Supabase Dashboard
1. Go to https://app.supabase.com
2. Select your project
3. Click **SQL Editor**
4. Run: `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';`
5. Should show 30+ tables

### In Django
```bash
cd backend
python manage.py shell
```

Then:
```python
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT version();")
    print(cursor.fetchone())
```

Should print PostgreSQL version.

---

## Table Names Reference

| Old Name | New Name |
|----------|----------|
| api_profile | user_profiles |
| api_application | student_applications |
| forms_formsubmission | form_submissions |
| forms_form | forms |
| programs_program | programs |
| users_customuser | users |

See `TABLE_MAPPING.md` for complete list.

---

## Common Issues

### "Connection refused"
- Check Supabase project is active (not paused)
- Verify password is correct
- Ensure `?sslmode=require` is in DATABASE_URL

### "SSL certificate error"
- Update psycopg2: `pip install --upgrade psycopg2-binary`
- Ensure `?sslmode=require` is in DATABASE_URL

### "No tables created"
- Run: `python manage.py migrate`
- Check for errors in output

---

## Rollback to SQLite (if needed)

Edit `backend/.env`:
```env
DATABASE_URL=sqlite:///db.sqlite3
```

Then:
```bash
cd backend
python manage.py migrate
```

---

## Need Help?

- **Full Guide**: See `SUPABASE_MIGRATION_GUIDE.md`
- **Table Reference**: See `TABLE_MAPPING.md`
- **Detailed Summary**: See `MIGRATION_SUMMARY.md`

---

## What's Next?

1. Create superuser: `python manage.py createsuperuser`
2. Test your application
3. Deploy to production
4. Monitor in Supabase dashboard

Enjoy your new Supabase database! 🚀
