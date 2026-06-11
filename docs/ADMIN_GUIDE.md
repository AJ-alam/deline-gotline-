# DGG SFAP — Admin Guide

Admins (role: `admin`, `director`, `ssw`, `finance`) access the system at `/staff/login`.

---

## Roles

| Role | Capabilities |
|------|-------------|
| `director` | Full access. One-click approve/deny via tokenized email link. Can view banking details. |
| `admin` / `ssw` | Review submissions, flag duplicates, request more info, escalate appeals. Cannot view banking. |
| `finance` | Receives monthly master list. Confirms payments via tokenized email link. |

---

## Policy Settings

Path: Staff Dashboard → Policy Settings

- **Edit award amounts** by category (PSSSP Living, UCEPP Tuition, DGGR Extra Tuition, etc.)
- **Effective date**: set a future date to apply new rates to submissions from that date forward. Prior submissions retain old rates.
- **Deactivate award types** (is_active = false) without deleting history.
- **Bulk update**: POST `/api/policy/bulk_update/` with a list of `{id, value, effective_date}` objects.

---

## Reviewing Submissions

1. Staff Dashboard → Applications tab
2. Click a submission to open the review panel
3. Actions:
   - **Forward to Director** — triggers tokenized approve/deny email
   - **Request More Info** — student receives notification, can upload additional documents
   - **Flag as Duplicate** — marks submission; requires duplicate review note
4. Director can approve/deny directly from email link — no portal login required.

---

## Duplicate Detection

Submissions are hashed using: `SHA-256(date_of_birth | beneficiary_number | indian_status)`.  
This detects the same person applying under different email addresses.

To review flagged submissions: Staff Dashboard → Duplicates tab.

---

## Appeals

Students can file an appeal (Form H). Appeal escalation levels:
1. Director
2. DGGR Official
3. CEO

To escalate: PUT `/api/appeals/{id}/escalate/` with `{notes: "reason"}`.

---

## Reports & Exports

- **CSV export**: Staff Dashboard → Reports → Export CSV (filterable by student name, semester, year, award type)
- **Excel export**: Staff Dashboard → Reports → Export Excel (`.xlsx`)
- **PDF export**: Staff Dashboard → Reports → Export PDF (landscape A4)
- **Manual finance dispatch**: Staff Dashboard → Finance → Dispatch Report

Monthly finance reports are sent automatically on the last Friday of each month.

---

## Staff User Management

Path: Staff Dashboard → Settings → Staff Users

- Create staff accounts with roles: `admin`, `ssw`, `director`, `finance`
- Deactivate accounts without deleting history
- Passwords can be reset from this panel

---

## Policy History

Full audit trail: Staff Dashboard → Policy → History.  
Every policy change records: who changed it, old value, new value, effective date.

---

## Audit Logs

Every significant action (approvals, denials, policy changes, duplicate reviews, finance confirmations) is logged in the AuditLog table. Accessible via `/api/audit-logs/`.
