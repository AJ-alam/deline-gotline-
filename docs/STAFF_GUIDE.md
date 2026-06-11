# DGG SFAP — Staff Guide

For SSW staff and admins. Login at `/staff/login` with your staff credentials.

---

## Dashboard Overview

The Staff Dashboard has four main tabs:

| Tab | Purpose |
|-----|---------|
| Applications | Review, approve, deny, request more info on student submissions |
| Students | View all student profiles and submission history |
| Payments | View payment records; dispatch finance reports |
| Reports | Export CSV/Excel/PDF; view audit logs |

---

## Reviewing an Application

1. Click **Applications** → select a submission
2. Read the submitted answers and uploaded documents
3. Choose an action:

### Forward to Director
Sends a tokenized email to the Director. The Director can approve or deny directly from their email — no portal login required. Token expires in 48 hours.

### Request More Info
Student receives a notification with your note. They can upload additional documents and respond. Submission status changes to `more_info_required`.

### Mark as Duplicate
Opens a dialog to enter a review note. Marks the submission flagged for duplicate review. Does not reject — a reviewer must confirm or clear the flag.

---

## Eligibility Check

On any submission: click **Check Eligibility** to run the eligibility service. Results show:
- `eligible_streams`: streams the student qualifies for (PSSSP, UCEPP, DGGR)
- `ineligible_streams`: streams with reason codes

Eligibility is recalculated automatically when a submission is accepted.

---

## Late Applications

If a student applies after the deadline and is approved, the system auto-generates back-pay payments from semester start to today. These appear as individual monthly Payment records in the Finance tab.

---

## Policy Settings

Path: Settings → Policy

- Change living allowance, tuition rates, travel amounts
- Set **effective date** for future-dated rate changes
- **Deactivate** award types temporarily without deleting history

---

## Finance Report

Manual dispatch: Finance tab → Dispatch Report.  
Automatic dispatch: last Friday of each month at 08:00.

The finance email includes an `.xlsx` attachment and a **Confirm Payments Processed** button. When Finance clicks the button, payments are marked as issued.

---

## Deadline Reminders

Configured via `ApplicationDeadline` records in the admin panel. The system sends reminders at 30 days and 7 days before each deadline to students who have not yet submitted.

---

## Entering Data on Behalf of Students

Staff can create and fill out forms on behalf of students. Navigate to the student's profile → New Submission → select the form type. All form fields are editable by staff.

---

## Common Issues

| Symptom | Fix |
|---------|-----|
| Director email link expired | Forward the submission again — creates a new 48-hour token |
| Finance confirm link expired | Re-dispatch the finance report manually |
| Student not receiving emails | Check student email in their profile; check spam folder |
| Calculation shows $0 | Verify student's funding stream is set; check PolicySetting.is_active |
