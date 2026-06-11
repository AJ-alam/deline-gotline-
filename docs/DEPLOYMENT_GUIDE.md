# DGG SFAP — Deployment Guide

## Prerequisites

- Python 3.11+, Node.js 18+
- Supabase project (Canada region recommended for data residency)
- SMTP credentials (Gmail or equivalent)
- Render or Heroku account for backend hosting

---

## Environment Variables

Create `backend/.env` (never commit this file):

```
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# JWT
SECRET_KEY=<50+ char random string>
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=30
JWT_REFRESH_TOKEN_LIFETIME_DAYS=3

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=DGG Education <your@email.com>
FINANCE_EMAIL=finance@gov.deline.ca
DIRECTOR_EMAILS=director@gov.deline.ca

# Site URL (used for tokenized email links)
SITE_URL=https://your-backend-domain.com

# CORS
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com

# Feature flags
DEBUG=False
TESTING=False
```

---

## Backend Deployment (Render)

1. **Build command:** `pip install -r requirements.txt`
2. **Start command:** `gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT`
3. **Database migrations** (run once after deploy):
   ```
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
4. **Seed forms** (creates Form A–H templates):
   ```
   python manage.py seed_forms
   ```

### Cron Jobs (Render Cron or similar)

| Schedule | Command | Purpose |
|----------|---------|---------|
| `0 8 * * 5` | `python manage.py send_monthly_finance_report` | Last Friday of month: email finance master list |
| `0 9 * * *` | `python manage.py send_deadline_reminders` | Daily: 30-day and 7-day deadline reminders |

---

## Frontend Deployment (Vercel)

1. Set **Build command:** `npm run build`
2. Set **Output directory:** `dist`
3. Add env var: `VITE_API_BASE_URL=https://your-backend-domain.com/api`
4. The `_redirects.txt` and `vercel.json` already handle SPA routing.

---

## Post-Deployment Checklist

- [ ] `SITE_URL` env var set — required for director/finance tokenized email links
- [ ] Run `python manage.py migrate` — applies all migrations including 0019–0021
- [ ] Run `python manage.py seed_forms` — creates form templates
- [ ] Test director one-click approve email by creating a test submission
- [ ] Test finance confirm email via `python manage.py send_monthly_finance_report --force`
- [ ] Confirm Supabase region is `ca-central-1` (Canada) for data residency
- [ ] Set `DEBUG=False` and `TESTING=False` in production
- [ ] Configure cron jobs for monthly report and deadline reminders
- [ ] Verify CORS `CORS_ALLOWED_ORIGINS` includes the frontend domain

---

## Data Residency

Supabase Canada (ca-central-1) region satisfies Canadian data residency requirements for First Nations government data. Confirm in Supabase dashboard → Settings → General → Region.

---

## Database Migrations (current state)

```
users/0001 → users/0009
api/0001 → api/0021
forms/0001 → forms/0015
programs/0001 → programs/0001
notifications/0001 → notifications/0001
```

All migrations are sequential and safe to apply with `python manage.py migrate`.
