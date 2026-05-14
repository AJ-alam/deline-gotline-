# DGG Student Portal — Security & Cleanup Audit

**Date:** 2026-05-11  
**Scope:** Full codebase — file cleanup, security hardening, code quality

---

## 1. Irrelevant Files Removed

### Backend root (`backend/`)
| File | Reason removed |
|------|---------------|
| `check_db.py` | One-off dev diagnostic script |
| `create_director.py` | One-off admin bootstrapping script |
| `data_backup.json` | Contained real student data — never track in git |
| `db.sqlite3` | Local SQLite dev database |
| `migrate_to_supabase.py` | One-time migration script, already executed |
| `migrate_to_supabase.sh` | Same as above |
| `seed_data.py` | Dev seed script |
| `seed_final.py` | Dev seed script |
| `seed_forms_full.py` | Dev seed script |
| `seed_policies.py` | Dev seed script |
| `test_auth.py` | Loose test script (not pytest) |
| `test_full_csv.py` | Loose test script |
| `test_login.py` | Loose test script |
| `test_supabase_connection.py` | Loose test script |
| `test_supabase_ip.py` | Loose test script |
| `schema.yml` | Auto-generated OpenAPI schema — regenerate with `manage.py spectacular` |
| `backend/scratch/` (entire folder) | Dev utilities and debug scripts |

### Project root
| File/Folder | Reason removed |
|-------------|---------------|
| `.graphify_ast.json` | Third-party code analysis cache |
| `.graphify_ast_run.py` | Third-party code analysis script |
| `.graphify_detect.json` | Third-party code analysis cache |
| `.graphify_python` | Third-party code analysis artifact |
| `.graphify_uncached.txt` | Third-party code analysis log |
| `graphify-out/` | Third-party code analysis output directory |
| `index-c6cczikz.js` | Stale Vite build artifact (should not be in source) |
| `index-mhoze89a.css` | Stale Vite build artifact |
| `_redirects (1).txt` | Duplicate of `_redirects.txt` |
| `requirements.txt` (root) | Duplicate of `backend/requirements.txt` (incomplete copy) |
| `scratch/` (entire folder) | Dev debugging scripts |

### Python bytecode
All `__pycache__/` directories and `*.pyc` files were deleted across the entire `backend/` tree (including all apps and the `venv/`).

---

## 2. `.gitignore` — Hardened

The `.gitignore` was rewritten to properly exclude:

- `node_modules/` and `dist/` (frontend)
- `venv/`, `backend/venv/` (Python virtual environments)
- `__pycache__/`, `*.pyc`, `*.py[cod]` (Python bytecode)
- `backend/db.sqlite3`, `db.sqlite3` (dev databases)
- `backend/staticfiles/`, `staticfiles/` (collected static files)
- `backend/media/` (user-uploaded files)
- `.env`, `.env.*` — but **not** `.env.example` (template is safe to track)
- `backend/data_backup.json` (data export)
- `index-*.js`, `index-*.css`, `*.map` (build artifacts)
- `.pytest_cache/`, `coverage/`, `htmlcov/` (test artifacts)
- `.graphify*`, `graphify-out/` (code analysis tools)
- `.vscode/*` (editor settings, except extensions.json)
- `.vercel/` (Vercel local config)

---

## 3. `.env.example` Created

`backend/.env.example` was created as a safe template. It lists every required environment variable with placeholder values and instructions. **No real secrets are in this file.** Developers clone the repo, copy this file to `.env`, and fill in real values.

---

## 4. Backend Security — `backend/core/settings.py`

### JWT tokens tightened
| Setting | Before | After | Reason |
|---------|--------|-------|--------|
| `ACCESS_TOKEN_LIFETIME` | 60 minutes | **30 minutes** | Shorter window limits exposure if token is stolen |
| `REFRESH_TOKEN_LIFETIME` | 7 days | **3 days** | Reduced attack window |
| `ROTATE_REFRESH_TOKENS` | False | **True** | Each refresh issues a new token (rolling session) |
| `UPDATE_LAST_LOGIN` | (unset) | **True** | Tracks active sessions |

### Rate throttling added (DRF)
```python
'DEFAULT_THROTTLE_CLASSES': [
    'rest_framework.throttling.AnonRateThrottle',
    'rest_framework.throttling.UserRateThrottle',
],
'DEFAULT_THROTTLE_RATES': {
    'anon': '200/day',
    'user': '2000/day',
    'auth': '10/minute',        # login, register
    'password_reset': '5/hour', # forgot-password, reset-password
},
```
This prevents brute-force login attacks and password-reset abuse.

### Custom exception handler
```python
'EXCEPTION_HANDLER': 'api.utils.responses.custom_exception_handler',
```
Ensures all API errors return our standard `{ success, data, message }` envelope — Django's raw HTML error pages never reach API clients.

### Production security headers (added)
```python
SECURE_HSTS_SECONDS = 31536000          # 1-year HSTS
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'DENY'               # Block clickjacking
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600              # 1-hour session timeout
```

### File upload limits
```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_UPLOAD_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
```

### Token blacklist app added
`rest_framework_simplejwt.token_blacklist` added to `INSTALLED_APPS`. This is **required** for `BLACKLIST_AFTER_ROTATION = True` to actually invalidate used refresh tokens. Without it, old refresh tokens remain valid.

> **Action required:** Run `python manage.py migrate` to create the token blacklist tables.

### Structured logging
A `LOGGING` configuration was added that routes Django security events, API app logs, and general Django warnings to the console in a structured format.

---

## 5. Auth Controller — `backend/api/controllers/auth_controller.py`

### `LoginController` — failed login no longer leaks data
**Before:** A failed login returned `response.data` (the raw simplejwt error dict).  
**After:** Returns a generic `"Invalid credentials"` message. The raw error dict could reveal whether a username exists.

Login events (success and failure) are now logged with the client IP for audit.

### `RegisterController` — rate-limited
A custom `AuthRateThrottle` (10 requests/minute per IP) now protects the registration endpoint from bulk account creation.

### `ForgotPasswordController` — origin header spoofing fixed
**Before:** The reset link was built from the `HTTP_ORIGIN` request header, which an attacker can set to any value. A crafted reset link could redirect the victim's reset token to an attacker-controlled domain.  
**After:** The reset link always uses `settings.FRONTEND_URL` — a server-side value loaded from the `.env` file. The `HTTP_ORIGIN` header is ignored.

Rate-limited to 5 requests/hour per IP.

### `ResetPasswordController` — password validation added
**Before:** Any string was accepted as the new password (no minimum length, no complexity check).  
**After:** Django's full password validator chain runs before the password is saved. Weak passwords are rejected with a clear error message.

Also: the error message for an expired/invalid token no longer distinguishes "token not found" from "user not found" (both return the same message) — eliminates a minor information leak.

### `TestEmailController` — restricted to admin/director
**Before:** Any authenticated user (including students) could trigger test emails.  
**After:** `permission_classes = (IsAdminUser,)` — only `admin` and `director` role users can call this endpoint.

Exception details are no longer included in the API response (previously `f"Exception: {exc}"` exposed internal stack info). Errors now log to the server and return a generic message.

---

## 6. Serializers — `backend/users/serializers.py`

### `RegisterSerializer` — password validation enforced
**Before:** `password` field had no validation beyond `write_only=True`.  
**After:**
- `min_length=8` enforced at the serializer level.
- Django's full password validator chain (`validate_password`) is called via `validate_password()`. This runs `MinimumLengthValidator`, `CommonPasswordValidator`, `UserAttributeSimilarityValidator`, and `NumericPasswordValidator`.

---

## 7. File Upload Security — `backend/api/views.py`

`UserDocumentViewSet.perform_create` now calls `_validate_upload()` before saving:

1. **Extension whitelist:** Only `.pdf`, `.jpg`, `.jpeg`, `.png`, `.doc`, `.docx` are accepted.
2. **Size limit:** Files over 10 MB are rejected with a clear error.
3. **Magic-byte check:** For common formats (PDF, JPEG, PNG) the first bytes of the file are read and compared against known file signatures. This prevents an attacker from uploading a `.php` or `.js` file renamed to `.pdf`.

---

## 8. API Utils — `backend/api/utils/responses.py`

The `custom_exception_handler` was added. It wraps DRF's default handler so:
- All error responses use the `{ success, data, message }` envelope.
- Unhandled exceptions are logged server-side and return a generic 500 message — stack traces never reach the client.

---

## 9. What Was NOT Changed (Intentionally)

- **Frontend localStorage for JWT** — This is the standard SPA approach. `httpOnly` cookies are better but require backend cookie management and CORS changes. Acceptable for now; no XSS vectors were found.
- **`email_sender.py`** — Kept as-is; it's production code used for all email delivery.
- **`build.sh`** — Kept; it's the Render/Heroku build hook.
- **`supabase_rls.sql`** — Kept; it's infrastructure documentation.
- **`_redirects.txt`** — Kept; it's the Netlify/Vercel SPA rewrite rule.

---

## 10. ⚠️ Critical Action Items for You (Cannot Be Done by Code)

These require access to your provider dashboards and **must be done immediately**, since the old `.env` values were committed to git history:

1. **Rotate your Django `SECRET_KEY`**  
   Generate a new one: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

2. **Change your Supabase database password** in the Supabase dashboard → Project Settings → Database.

3. **Regenerate your Supabase API keys** (anon key + service role key) in Supabase → Project Settings → API.

4. **Revoke your Gmail App Password** and generate a new one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

5. **Run migrations** after rotating secrets:
   ```bash
   cd backend
   python manage.py migrate
   ```
   This creates the `token_blacklist` tables required for JWT rotation.

6. **Consider purging git history** if the repo is or was ever public. The secrets are embedded in past commits. Use [BFG Repo Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) or `git filter-repo` to scrub them, then force-push.

7. **Set `DEBUG=False`** in your production `.env`. Verify it is `False` on the server.
