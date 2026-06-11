# DGG SFAP — Traceability Matrix
**Audit date:** 2026-06-11  **Status key:** PASS | FAIL | PARTIAL | MISSING | DEFERRED

---

## Module 1 — Authentication & Access (§3.1.A, §7.1)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 1.1 | Student signup, login, logout, session expiry | `auth_controller.py` RegisterController, LoginController | PARTIAL | Login/register work. Logout: frontend clears localStorage (no server-side blacklist — see 1.2). Session expiry: 60 min access token. |
| 1.2 | JWT rotation & blacklist | `settings.py` SIMPLE_JWT | FAIL | CHANGES.md says ROTATE_REFRESH_TOKENS=True was applied; actual settings.py has `False`. Token blacklist app not in INSTALLED_APPS. |
| 1.3 | Password reset (email link, 30-min token, single-use) | `auth_controller.py` ForgotPasswordController | PASS | Cache-backed token, single-use via `cache.delete()`. |
| 1.4 | Form B registrar — no account required | `FormBPublic.tsx`, `forms/models.py` FormBResponse | PARTIAL | Public route `/form-b/:token` exists; FormBResponse model exists. Token expiry on model. Resend not tested. |
| 1.5 | Director one-click email approve/deny (single-use, signed, no login) | — | MISSING | Not implemented. Director must log into portal to approve. |
| 1.6 | Finance email confirmation — no login | — | MISSING | No finance email confirmation flow found. |
| 1.7 | Role-based access: student sees only own data | `api/views.py` get_queryset() per role | PASS | `filter(student=user)` applied for students. |
| 1.8 | Finance role: banking details + amounts + codes only; NOT full student files | `api/views.py` `_build_full_csv` | FAIL | No Finance role exists. Banking details in full CSV accessible to all `admin` staff. |
| 1.9 | Banking details Director-only (§6.4) | `users/serializers.py`, `api/views.py` | FAIL | `_is_staff()` returns True for `admin` + `director` — admin staff can view banking. |
| 1.10 | Staff deactivation: data fully retained | `api/controllers/auth_controller.py` StaffUserDetailController | PASS | `is_active=False` keeps all FK-linked data. SET_NULL on audit/payment FKs. |
| 1.11 | SSW role in model | `users/models.py` ROLE_CHOICES | FAIL | `ssw` not in ROLE_CHOICES. Frontend allows `ssw` in ProtectedRoute. |

---

## Module 2 — Student Application Forms (§3.1.A, §5, §7.4)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 2.1 | Form A (new student) | `src/pages/Forms/FormA.tsx` | PARTIAL | Form exists. Duplicate guard in submit. No autosave. |
| 2.2 | Form C (continuing — pre-fill from prior) | `src/pages/Forms/FormC.tsx` | PARTIAL | Form exists. Pre-fill from prior submission not verified. |
| 2.3 | Form D (change of information) | `src/pages/Forms/FormD.tsx` | PARTIAL | Form exists. Trivially easy update flow not fully verified. |
| 2.4 | Form E (travel reimbursement + receipt uploads) | `src/pages/Forms/FormE.tsx` | PARTIAL | Form exists. File upload supported via FormField type=file. |
| 2.5 | Form F (employer, no account) | `src/pages/Forms/FormF.tsx` | PARTIAL | Standalone route `/forms/practicum` exists. No employer-specific token flow. |
| 2.6 | Form G (graduation award) | `src/pages/Forms/FormG.tsx` | PARTIAL | Form exists. |
| 2.7 | Form H (appeal) | `src/pages/Forms/FormH.tsx` | PARTIAL | FormH exists but App.tsx routes `/forms/appeal` to FormD, not FormH. Bug. |
| 2.8 | Academic Achievement Scholarship | `src/pages/Forms/AcademicScholarship.tsx` | PARTIAL | Form exists. |
| 2.9 | Hardship Bursary | `src/pages/Forms/HardshipBursary.tsx` | PARTIAL | Form exists. |
| 2.10 | Form B (institution, no account) via tokenized link | `src/pages/FormBPublic.tsx` | PARTIAL | Route and model exist. Token expiry needs verified. |
| 2.11 | Required-field validation + inline errors | frontend forms | PARTIAL | Not audited per form — needs UI testing. |
| 2.12 | File uploads: HEIC/JPG/PNG/PDF, size+type validation | `api/views.py` `_validate_upload` | PARTIAL | Magic-byte check only in UserDocumentViewSet, not in FormController file uploads. |
| 2.13 | Autosave/draft recovery — zero data loss on kill | — | MISSING | No autosave/draft mechanism in frontend or backend. §7.4 critical requirement. |
| 2.14 | Deadline enforcement + Director exception flow for late | `forms/models.py` ApplicationDeadline, FormSubmission.submitted_after_deadline | PARTIAL | Model fields exist. Enforcement logic in form_controller needs verification. |
| 2.15 | Submission confirmation + specific "what's missing" notification | `email_sender.py` send_application_received | PARTIAL | Confirmation email sent. Missing-docs specificity not verified. |
| 2.16 | Multi-step progress indicator, back nav without data loss, review-before-submit | `components/Forms/FormWizard.tsx` | PARTIAL | FormWizard exists; needs UI testing. |

---

## Module 3 — Eligibility & Funding Calculation (§4) — HIGH RISK

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 3.1 | Three streams: PSSSP, UCEPP, DGGR | `eligibility_service.py` | PARTIAL | Checks exist but incomplete (see below). |
| 3.2 | SFA restriction blocks C-DFN (PSSSP+UCEPP), never DGGR | `eligibility_service.py` _check_psssp/ucepp | PASS | SFA check present for PSSSP and UCEPP; DGGR check has no SFA block. |
| 3.3 | Stacking: C-DFN + DGGR additive | `calculation_service.py` | FAIL | `_calculate_funding` routes to ONE stream only; no stacking logic. |
| 3.4 | FT/PT from Form B (authoritative), disability threshold (40%) | `eligibility_rules` PolicySetting seeded | PARTIAL | Policy seeded. Calculation uses student.enrollment_status fallback. Form B authoritative data not enforced. |
| 3.5 | Tuition: PSSSP ≤$5000, UCEPP ≤$2000, DGGR FT $1500/PT $900 | `calculation_service.py`, seed_policies.py | PASS | Policy-driven, correct values seeded. |
| 3.6 | DGGR Extra Tuition: 25%, $4k/sem cap, $12k/year, inclusive of regular bursary | `calculation_service.py` line 362-373 | FAIL | Math bug: `extra_amount = min(requested * pct, cap) - final_tuition` is wrong. Should be `max(0, min(tuition * 25%, 4000) - regular_dggr_tuition)`. |
| 3.7 | DGGR Extra Tuition: $36k annual pool across all students | `dggr_extra_tuition` PolicySetting | FAIL | Pool cap seeded but NOT enforced in CalculationService. No pool check before awarding extra. |
| 3.8 | Monthly living allowances: 12-cell matrix | `calculation_service.py`, seed_policies.py | PASS | All 12 cells seeded and used in calculation. |
| 3.9 | Travel bursary: FT, in-person, >200km, no SFA; $2k/$3.5k caps, 2 trips/year | `_calculate_travel`, seed_policies.py | PARTIAL | Caps seeded. Distance/FT/SFA checks not enforced programmatically — manual review. |
| 3.10 | Graduation Travel: ≥2yr programs, up to $5k | `psssp_graduation_travel` section | PARTIAL | Policy seeded. Duration check not enforced. |
| 3.11 | Graduation Bursary tiers ($500–$5000) | `_calculate_graduation_bursary`, seed_policies.py | PASS | All 12 credential tiers seeded and mapped. |
| 3.12 | Achievement Scholarship: GPA ≥80%=$1000, 70–79.99%=$500 | `_calculate_scholarship` | PASS | Policy-driven thresholds. Boundary test 79.99/80.00 works correctly (strict `>=`). |
| 3.13 | Staff override flagged for Director review | `forms/models.py` office_use_data | PARTIAL | Office use data field exists. Flag-for-director on override not auto-triggered. |
| 3.14 | Mid-semester recalculation + proration + overpayment to Director/Finance | `forms/models.py` MidSemesterChange | PARTIAL | Model exists. Automatic recalculation not verified. |
| 3.15 | Late approval back-pay from semester start | — | MISSING | No back-pay logic in calculation service. |
| 3.16 | No hardcoded amounts | `calculation_service.py`, all services | PASS | All amounts read from PolicySetting. Grep confirms no literal dollar amounts in service code. |

---

## Module 4 — Staff Dashboard (§3.1.B)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 4.1 | All staff see every application + history | `api/views.py` ApplicationViewSet.get_queryset() | PARTIAL | `admin` role sees all; `director` filtered to pending/approved/denied. SSW role missing. |
| 4.2 | Review, notes, calculate/adjust funding, send-to-director | `form_controller.py`, StaffDashboard.tsx | PARTIAL | Exists. Override not auto-flagged for Director. |
| 4.3 | Manual entry on behalf of paper-form students | `form_controller.py` | PARTIAL | Any admin can submit on behalf of student. |
| 4.4 | Search/filter with volume (200+ apps) | StaffDashboard.tsx | PARTIAL | Pagination exists (PAGE_SIZE=50). DB indexes on submissions. |
| 4.5 | New-application notifications to shared mailbox | `notifications/utils.py` | PARTIAL | In-app notifications created. Email to shared mailbox not implemented. |

---

## Module 5 — Director Approval (§3.1.D, §4.7)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 5.1 | Approve/deny with full audit trail | `form_controller.py`, AuditLog | PASS | AuditLog.create() on every decision. |
| 5.2 | Exception approvals (late applications) with reason | `FormSubmission.late_application_approved_by` | PARTIAL | Model fields exist. Exception reason capture not verified. |
| 5.3 | Email-based one-click approval without sign-in | — | MISSING | Not implemented. |
| 5.4 | Appeals: student → Director → escalation (DGGR/C-DFN) | `api/models.py` Appeal | PARTIAL | Appeal model exists. Escalation flow not implemented. |

---

## Module 6 — Finance Module (§3.1.E, §7.3)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 6.1 | Approved payment list auto-delivered: banking + amounts + accounting codes | `api/views.py` dispatch_report | PARTIAL | CSV with banking sent. No accounting codes field exists. |
| 6.2 | Month-end master list last Friday before month | — | MISSING | No scheduler/cron implemented. |
| 6.3 | Click-in-email payment confirmation, no login | — | MISSING | Not implemented. |
| 6.4 | Payment timing: tuition within 1 month, living on 1st, one-time within 15 biz days | `seed_policies.py` payment_schedule | PARTIAL | Policy values seeded. Enforcement in scheduler not implemented. |
| 6.5 | No advance payments | — | MISSING | No guard preventing advance payments. |

---

## Module 7 — Automated Notifications (§3.1.F)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 7.1 | Application received email | `email_sender.py` send_application_received | PASS | Triggered on submission. |
| 7.2 | Documents missing email (specific missing docs named) | — | MISSING | Generic "more info required" message sent; specific document names not included. |
| 7.3 | Approved/denied email with editable letter | `email_sender.py` send_application_decision | PARTIAL | Email sent. Letter not editable by Director before send. |
| 7.4 | Payment issued notification | `email_sender.py` send_funding_processed | PASS | Triggered on dispatch_report. |
| 7.5 | Pre-deadline reminders | — | MISSING | No scheduler for reminders. |
| 7.6 | No sensitive identifier in any email | `email_sender.py` | PASS | No UPI/beneficiary in email templates visible from code. |

---

## Module 8 — Policy Management (§3.1.G, §7.5)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 8.1 | Change rates without developer | `api/controllers/policy_controller.py`, PolicySetting | PASS | Director/Admin can update via API. |
| 8.2 | Effective date: prior semester at old rates, new semester at new | PolicyHistory.effective_date | PARTIAL | History recorded. Calculation engine does NOT check effective dates — always uses current value. |
| 8.3 | Deactivated awards disappear from new apps; history intact | — | MISSING | No award activation/deactivation flag in PolicySetting. |
| 8.4 | Full version history of policy changes | `api/models.py` PolicyHistory | PASS | History recorded on every change. |
| 8.5 | No hardcoded amounts | `calculation_service.py` | PASS | All from PolicySetting. |
| 8.6 | Fiscal year Apr 1–Mar 31 handled | — | PARTIAL | Fiscal year not explicitly modeled; reports use calendar year. |

---

## Module 9 — Reporting (§3.1.H)

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 9.1 | Quarterly + annual DGGR reports (fiscal Apr 1–Mar 31) | StaffDashboard.tsx reporting section | PARTIAL | Dashboard has reporting UI. Fiscal year date logic not verified. |
| 9.2 | Federal C-DFN annual reports | StaffDashboard.tsx | PARTIAL | Exists. C-DFN specific columns not verified. |
| 9.3 | Ad-hoc reports filtered by program/semester/year/student/award | `api/views.py` export_csv | PARTIAL | Filters by funding_type and date range. Program/semester/student filters missing. |
| 9.4 | PDF and Excel/CSV export | `api/views.py` export_csv | PARTIAL | CSV only. No PDF export for reports. Excel/XLSX not implemented. |
| 9.5 | §6.3 identifier absent from all reports | `_build_full_csv` | FAIL | `UPI` column in CSV export. |

---

## Module 10 — Duplicate Detection & Privacy (§3.1.I, §6) — SECURITY CRITICAL

| # | Requirement | Code location | Status | Notes |
|---|-------------|---------------|--------|-------|
| 10.1 | Unique identifier hashed/irreversible before storage | `duplicate_detection_service.py` SHA-256 | PARTIAL | Hash uses email in compound — email changes break detection. UPI field in CustomUser is stored plaintext. |
| 10.2 | Plaintext identifier unrecoverable after duplicate check | `duplicate_detection_service.py` | PARTIAL | Hash does not store plaintext. But `users.upi` stores plaintext UPI on CustomUser. |
| 10.3 | Identifier in zero logs/errors/exports/API/UI | `api/views.py` `_build_full_csv` | FAIL | UPI column in CSV. `duplicate_detection_service.py` uses `print()` for errors. |
| 10.4 | Banking encrypted at rest | Supabase (PG row-level encryption unclear) | DEFERRED | Depends on Supabase config. App-level encryption not implemented. |
| 10.5 | Banking masked in UI | StaffDashboard.tsx | PARTIAL | Not verified. |
| 10.6 | Uploaded files not URL-guessable | Supabase Storage + signed URLs | PARTIAL | Depends on bucket policy. Needs verification. |
| 10.7 | SQLi, XSS, CSRF, IDOR protection | DRF ORM, CSRF middleware | PARTIAL | ORM prevents SQLi. CSRF configured. IDOR: ApplicationViewSet.get_queryset filters by user for students. Staff endpoints don't restrict student ID cross-access via query params. |
| 10.8 | Rate limiting on auth endpoints | `settings.py` throttle | PASS | 10/min on auth, 5/hr on reset. |
| 10.9 | Secrets not committed to repo | `.gitignore` | PASS | .env excluded. CHANGES.md notes prior secrets in git history — recommend purge. |
| 10.10 | Audit trail immutable | `api/models.py` AuditLog — no update/delete endpoints | PASS | ReadOnlyModelViewSet for AuditLog. No delete action. |

---

## Summary (as of audit start)

| Status | Count |
|--------|-------|
| PASS | 15 |
| PARTIAL | 34 |
| FAIL | 10 |
| MISSING | 11 |
| DEFERRED | 1 |
| **Total requirements** | **71** |

**Requirements PASS gate: 0 of 71 at PASS with no FAIL/MISSING blockers**

---

*This file is updated as fixes are applied.*
