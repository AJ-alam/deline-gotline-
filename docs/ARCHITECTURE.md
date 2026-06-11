# DGG SFAP — Architecture Snapshot
**Captured:** 2026-06-11  **Auditor:** Pre-deployment QA pass

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite 5 |
| Backend | Django 4.x + Django REST Framework 3.x |
| Auth | SimpleJWT (access 60 min, refresh 7 days) |
| Database | Supabase PostgreSQL (production) / SQLite (local dev) |
| File Storage | Supabase Storage (production) / local filesystem (dev) |
| Email | SMTP via `email_sender.py` (Gmail by default) |
| Frontend deploy | Vercel / Netlify (SPA rewrite via `_redirects.txt`) |
| Backend deploy | Render / Heroku (Procfile + `build.sh`) |

---

## Repository Layout

```
deline-gotline-/
├── src/                        # React frontend
│   ├── App.tsx                 # Router (BrowserRouter + ProtectedRoute)
│   ├── api/client.ts           # Axios client (JWT header injection)
│   ├── config/api.ts           # API base URL config
│   ├── components/
│   │   ├── Auth/               # ProtectedRoute, AdminErrorBoundary
│   │   └── Forms/              # FormWizard, StandaloneFormWrapper, FieldHint
│   ├── pages/
│   │   ├── Forms/              # FormA–H, HardshipBursary, AcademicScholarship
│   │   ├── Dashboard.tsx       # Student dashboard
│   │   ├── StaffDashboard.tsx  # Unified staff/director dashboard
│   │   ├── SignIn/SignUp/…     # Auth pages
│   │   └── FormBPublic.tsx     # Registrar form (no-login)
│   └── styles/                 # auth.css, dashboard.css, forms.css, staff.css
├── backend/
│   ├── core/
│   │   ├── settings.py         # All config (env-driven via python-decouple)
│   │   ├── urls.py             # Root URL conf
│   │   └── supabase_storage.py # Custom storage backend
│   ├── users/                  # CustomUser model, serializers, permissions, URLs
│   ├── api/                    # Main app
│   │   ├── models.py           # Profile, Application, AuditLog, PolicySetting,
│   │   │                       #   Payment, Appeal, ShareableLink, DuplicateDetectionLog
│   │   ├── views.py            # ApplicationViewSet, PaymentViewSet, etc.
│   │   ├── controllers/
│   │   │   ├── auth_controller.py   # Login, Register, ForgotPwd, ResetPwd, StaffUsers
│   │   │   ├── form_controller.py   # FormController (submit, approve, review)
│   │   │   └── policy_controller.py # PolicySettingViewSet
│   │   ├── services/
│   │   │   ├── calculation_service.py   # Funding engine (ALL policy-driven)
│   │   │   ├── eligibility_service.py   # Stream eligibility checks
│   │   │   ├── duplicate_detection_service.py  # SHA-256 hash duplicate check
│   │   │   └── form_service.py          # FormService (create/answer submission)
│   │   ├── management/commands/
│   │   │   ├── seed_policies.py   # Seeds PolicySetting from §4 rules
│   │   │   └── seed_forms.py      # Seeds Form + FormField definitions
│   │   └── migrations/            # 18 migrations
│   ├── forms/                  # Form, FormField, FormSubmission, SubmissionAnswer,
│   │                           #   SubmissionNote, MidSemesterChange, ApplicationDeadline,
│   │                           #   FormBResponse
│   ├── programs/               # Program model
│   ├── notifications/          # Notification model + utils (create_notification, email helpers)
│   ├── dashboard/              # Deprecated; all logic in api/controllers
│   └── email_sender.py         # Standalone SMTP module (all email types)
└── docs/                       # (this directory — created during audit)
```

---

## Data Flow (happy path: student → payment)

```
Student → SignUp (RegisterController) → JWT stored in localStorage
Student → Dashboard → pick form → FormWizard → POST /api/forms/{id}/submit/
FormController._submit_inner() → FormService.create_submission()
  → DuplicateDetectionService.check_for_duplicates()
  → CalculationService.calculate_and_pay()        ← Policy-driven funding engine
  → email_sender.send_application_received()

SSW → StaffDashboard → review → POST /api/forms/submissions/{id}/review/
  → status: pending → forwarded → Director notified

Director → email one-click OR portal approve → POST /api/forms/submissions/{id}/approve/
  → status: accepted → AuditLog created
  → email_sender.send_application_decision(approved=True)

Admin/Director → POST /api/payments/dispatch_report/
  → _build_full_csv() → send_finance_report() → Finance email
  → Payment.status → ISSUED
  → email_sender.send_funding_processed() → Student notified
```

---

## Role Model (current state — DEFECT: missing roles)

| Role code | Intended use | In model |
|-----------|-------------|---------|
| `student` | Student applicants | ✓ |
| `admin` | SSW / staff (handles review) | ✓ |
| `director` | Director (approves, sees banking) | ✓ |
| `ssw` | Student Support Worker | ✗ MISSING |
| `finance` | Finance department | ✗ MISSING |

`ProtectedRoute` in `App.tsx` already references `ssw` in `allowedRoles` — but `CustomUser.ROLE_CHOICES` does not include it, meaning no user can ever hold that role via the model constraint.

---

## Policy Engine

All dollar amounts, thresholds, and rates live in `api_models.PolicySetting` (db table `policy_settings`). Seeded by `manage.py seed_policies`. The `CalculationService` reads them at runtime via `_get_policy_value(section, field_key)` — **no hardcoded amounts in service code**.

Policy changes require Director/Admin role and go through `policy_controller.py`; each change is logged to `api_models.PolicyHistory`.

---

## Key Defects Found During Architecture Review

See `TEST_MATRIX.md` for the complete traceability matrix. Top-severity items:

1. **ROLE_CHOICES missing `ssw`** — SSW staff cannot be created or authenticated with SSW role.
2. **UPI plaintext in CSV export** — §6.3 prohibits the unique identifier in any export; `_build_full_csv` includes a `UPI` column exposing it.
3. **Banking visible to all `admin` staff** — §6.4 restricts banking details to Director only; current `_is_staff()` check lets all admin see it.
4. **JWT settings drift** — `CHANGES.md` says tokens were tightened (30 min / ROTATE=True) but `settings.py` still has 60 min / ROTATE=False.
5. **No Celery/cron for scheduled jobs** — month-end Finance list, deadline reminders not implemented.
6. **Director email one-click approve** — not implemented; Director must log in to portal.
7. **Form autosave/draft recovery** — not implemented (§7.4 requirement).
8. **`print()` in duplicate detection** — leaks error strings to stdout/logs.
