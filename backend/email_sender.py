"""
DGG Post-Secondary Funding Platform — Email Sender
===================================================
Single file for ALL outbound emails.
Credentials are loaded exclusively from .env — never hardcoded.

Functions
---------
send_email()                   — base SMTP sender (all others call this)
send_finance_report()          — 1. Finance dept CSV report (manual trigger)
send_application_received()    — 2. Student: application received
send_application_decision()    — 3. Student: approved or rejected
send_funding_processed()       — 4. Student: funding processed / paid
send_password_reset()          — 5. Student: forgot-password reset link
"""

import os
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Load .env (python-dotenv); silently skip if not installed
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass


def _cfg(key: str, default: str = "") -> str:
    """Read a value from environment / .env."""
    return os.environ.get(key, default).strip()


# ---------------------------------------------------------------------------
# BASE SEND FUNCTION
# ---------------------------------------------------------------------------

def send_email(
    to: str,
    subject: str,
    html_body: str,
    plain_body: str = "",
    attachment_bytes: bytes = None,
    attachment_filename: str = None,
    attachment_mimetype: str = "application/octet-stream",
) -> bool:
    """
    Core SMTP sender.  All other functions call this.

    Returns True on success, False on any failure.
    Credentials come from .env:  SENDER_EMAIL  /  SENDER_PASSWORD
    """
    sender   = _cfg("SENDER_EMAIL")
    password = _cfg("SENDER_PASSWORD")

    if not sender or not password:
        print("[email_sender] ERROR: SENDER_EMAIL or SENDER_PASSWORD not set in .env")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"]    = f"DGG Education Department <{sender}>"
        msg["To"]      = to

        # Attach text parts
        alt = MIMEMultipart("alternative")
        if plain_body:
            alt.attach(MIMEText(plain_body, "plain", "utf-8"))
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)

        # Optional file attachment
        if attachment_bytes and attachment_filename:
            mime_main, mime_sub = (attachment_mimetype + "/octet-stream").split("/", 1)[:2]
            part = MIMEBase(mime_main, mime_sub)
            part.set_payload(attachment_bytes)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{attachment_filename}"',
            )
            msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, [to], msg.as_string())

        print(f"[email_sender] OK  subject={subject!r}  to={to}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[email_sender] ERROR: Gmail auth failed — check SENDER_EMAIL / SENDER_PASSWORD in .env")
        return False
    except smtplib.SMTPException as exc:
        print(f"[email_sender] SMTP error sending to {to}: {exc}")
        return False
    except Exception as exc:
        print(f"[email_sender] Unexpected error sending to {to}: {exc}")
        return False


def _async(to, subject, html, plain="", att_bytes=None, att_name=None, att_mime="application/octet-stream"):
    """Fire-and-forget wrapper — sends in a background daemon thread."""
    t = threading.Thread(
        target=send_email,
        args=(to, subject, html, plain, att_bytes, att_name, att_mime),
        daemon=True,
    )
    t.start()


# ---------------------------------------------------------------------------
# HTML TEMPLATE
# ---------------------------------------------------------------------------

def _wrap(content: str) -> str:
    """Wrap inner HTML content in the standard DGG email shell."""
    return (
        "<!DOCTYPE html><html><body style='margin:0;padding:0;"
        "background:#f1f5f9;font-family:Arial,sans-serif;'>"
        "<table width='100%' cellpadding='0' cellspacing='0' "
        "style='background:#f1f5f9;padding:32px 0;'>"
        "<tr><td align='center'>"
        "<table width='600' cellpadding='0' cellspacing='0' "
        "style='background:#ffffff;border-radius:12px;overflow:hidden;"
        "box-shadow:0 2px 12px rgba(0,0,0,0.08);'>"
        # header
        "<tr><td style='background:#1e293b;padding:28px 36px;'>"
        "<h1 style='margin:0;color:#e5a662;font-size:20px;'>"
        "D&#233;l&#x12A;&#x328;&#x1E45;&#x119; Got&#x2019;&#x12A;&#x328;&#x1E45;&#x119; Government</h1>"
        "<p style='margin:6px 0 0;color:rgba(255,255,255,0.55);font-size:12px;'>"
        "Education &amp; Training Department &mdash; Student Funding</p>"
        "</td></tr>"
        # body
        "<tr><td style='padding:36px;'>" + content + "</td></tr>"
        # footer
        "<tr><td style='background:#f8fafc;padding:18px 36px;"
        "border-top:1px solid #e2e8f0;'>"
        "<p style='margin:0;font-size:11px;color:#94a3b8;'>"
        "This is an automated message from the DGG Student Funding Portal. "
        "For queries contact "
        "<a href='mailto:ajalam149@gmail.com' style='color:#3b82f6;'>"
        "ajalam149@gmail.com</a>.</p>"
        "</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def _row(label: str, value: str) -> str:
    return (
        f"<tr>"
        f"<td style='padding:6px 0;color:#64748b;width:180px;font-size:13px;'>{label}</td>"
        f"<td style='padding:6px 0;font-weight:600;font-size:13px;'>{value}</td>"
        f"</tr>"
    )


# ---------------------------------------------------------------------------
# 1. FINANCE DEPARTMENT EMAIL  (manual trigger)
# ---------------------------------------------------------------------------

def send_finance_report(
    csv_bytes: bytes,
    total_students: int,
    triggered_by: str = "",
) -> bool:
    """
    Send the full student-applications CSV to the Finance Department.

    Parameters
    ----------
    csv_bytes       : raw bytes of the CSV file
    total_students  : number of student rows in the CSV
    triggered_by    : name / email of the staff member who triggered the export
    """
    finance_email = _cfg("FINANCE_EMAIL")
    if not finance_email:
        print("[email_sender] ERROR: FINANCE_EMAIL not set in .env")
        return False

    now_str  = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject  = f"DGG Post-Secondary Funding \u2014 Student Applications Report [{date_str}]"

    plain = (
        f"DGG Post-Secondary Funding - Student Applications Report\n"
        f"Generated: {now_str}\n"
        f"Total students: {total_students}\n"
        f"Triggered by: {triggered_by or 'DGG Staff'}\n\n"
        f"Please see the attached CSV file for the full breakdown."
    )

    html_content = (
        f"<h2 style='color:#1e293b;margin-top:0;'>Student Applications Report</h2>"
        f"<p>Please find the full student applications export attached to this email.</p>"
        f"<table style='width:100%;border-collapse:collapse;margin:24px 0;'>"
        + _row("Generated on", now_str)
        + _row("Total students", str(total_students))
        + _row("Triggered by", triggered_by or "DGG Education Staff")
        + _row("Attachment", "student_applications_report.csv")
        + "</table>"
        f"<p style='color:#64748b;font-size:13px;'>"
        f"The attached CSV contains the full breakdown of all student applications "
        f"including funding details, statuses, and contact information.</p>"
    )

    return send_email(
        to=finance_email,
        subject=subject,
        html_body=_wrap(html_content),
        plain_body=plain,
        attachment_bytes=csv_bytes,
        attachment_filename=f"student_applications_{date_str}.csv",
        attachment_mimetype="text/csv",
    )


# ---------------------------------------------------------------------------
# 2. STUDENT — APPLICATION RECEIVED
# ---------------------------------------------------------------------------

def send_application_received(
    student_email: str,
    student_name: str,
    reference_number: str,
    program_name: str,
    submitted_at: datetime = None,
) -> bool:
    """
    Sent automatically when a student submits an application.

    Parameters
    ----------
    student_email    : student's registered email
    student_name     : student's full name
    reference_number : e.g. "FS-0042"
    program_name     : form / program title
    submitted_at     : datetime of submission (defaults to now)
    """
    if submitted_at is None:
        submitted_at = datetime.now()

    submitted_str = submitted_at.strftime("%B %d, %Y at %I:%M %p")
    subject = "Your DGG Funding Application Has Been Received"

    plain = (
        f"Dear {student_name},\n\n"
        f"Your application has been received.\n"
        f"Reference #: {reference_number}\n"
        f"Program: {program_name}\n"
        f"Submitted: {submitted_str}\n\n"
        f"Your application is under review. You will be notified once a decision is made.\n"
        f"For queries: ajalam149@gmail.com"
    )

    html_content = (
        f"<h2 style='color:#1e293b;margin-top:0;'>Application Received</h2>"
        f"<p>Dear <strong>{student_name}</strong>,</p>"
        f"<p>Your application has been successfully submitted and is now under review "
        f"by the DGG Education &amp; Training Department.</p>"
        f"<table style='width:100%;border-collapse:collapse;margin:24px 0;"
        f"background:#f8fafc;border-radius:8px;padding:16px;'>"
        + _row("Reference #", reference_number)
        + _row("Program", program_name)
        + _row("Submitted", submitted_str)
        + _row("Status", "Under Review")
        + "</table>"
        f"<p>You will receive an email notification once a decision has been made. "
        f"You can also track your application status by logging into the student portal.</p>"
        f"<p style='color:#64748b;font-size:13px;'>Estimated review time: 5&ndash;10 business days.</p>"
        f"<p style='color:#64748b;font-size:13px;'>For any queries, contact us at "
        f"<a href='mailto:ajalam149@gmail.com' style='color:#3b82f6;'>ajalam149@gmail.com</a>.</p>"
    )

    return send_email(
        to=student_email,
        subject=subject,
        html_body=_wrap(html_content),
        plain_body=plain,
    )


# ---------------------------------------------------------------------------
# 3. STUDENT — APPLICATION APPROVED / REJECTED
# ---------------------------------------------------------------------------

def send_application_decision(
    student_email: str,
    student_name: str,
    reference_number: str,
    program_name: str,
    approved: bool,
    # --- approved fields ---
    semester: str = "",
    year: str = "",
    funding_breakdown: list = None,   # list of {"name": str, "amount": float}
    total_amount: float = 0.0,
    processing_timeline: str = "3-5 business days",
    # --- rejected fields ---
    rejection_reason: str = "",
) -> bool:
    """
    Sent automatically when staff approves or rejects an application.

    Parameters
    ----------
    approved           : True = approved, False = rejected
    funding_breakdown  : [{"name": "Tuition Bursary", "amount": 2500.00}, ...]
    rejection_reason   : plain-text reason shown to student
    """
    if approved:
        subject = "Your DGG Funding Application Has Been Approved \u2705"

        breakdown_rows = ""
        if funding_breakdown:
            for item in funding_breakdown:
                breakdown_rows += _row(item.get("name", "Bursary"), f"${float(item.get('amount', 0)):,.2f}")
        breakdown_rows += _row("<strong>Total Approved</strong>", f"<strong>${total_amount:,.2f}</strong>")

        plain = (
            f"Dear {student_name},\n\n"
            f"Congratulations! Your application has been APPROVED.\n"
            f"Reference #: {reference_number}\n"
            f"Program: {program_name}\n"
            f"Semester: {semester} {year}\n"
            f"Total Approved: ${total_amount:,.2f}\n"
            f"Processing timeline: {processing_timeline}\n\n"
            f"For queries: ajalam149@gmail.com"
        )

        html_content = (
            f"<h2 style='color:#166534;margin-top:0;'>Congratulations &mdash; Application Approved! \u2705</h2>"
            f"<p>Dear <strong>{student_name}</strong>,</p>"
            f"<p>We are pleased to inform you that your application for "
            f"<strong>{program_name}</strong> has been <strong style='color:#166534;'>approved</strong>.</p>"
            f"<table style='width:100%;border-collapse:collapse;margin:24px 0;'>"
            + _row("Reference #", reference_number)
            + _row("Program", program_name)
            + _row("Semester", f"{semester} {year}".strip())
            + "</table>"
            f"<h3 style='color:#1e293b;margin:24px 0 12px;'>Funding Breakdown</h3>"
            f"<table style='width:100%;border-collapse:collapse;background:#f0fdf4;"
            f"border-radius:8px;padding:16px;'>"
            + breakdown_rows
            + "</table>"
            f"<p style='margin-top:20px;'>Your funding will be processed within "
            f"<strong>{processing_timeline}</strong>. You will receive a separate "
            f"notification once payment has been issued.</p>"
            f"<p style='color:#64748b;font-size:13px;'>For queries contact "
            f"<a href='mailto:ajalam149@gmail.com' style='color:#3b82f6;'>ajalam149@gmail.com</a>.</p>"
        )

    else:
        subject = "Update on Your DGG Funding Application \u274c"

        reason_block = ""
        if rejection_reason:
            reason_block = (
                f"<div style='background:#fef2f2;border:1px solid #fecaca;"
                f"border-radius:8px;padding:16px;margin:20px 0;'>"
                f"<p style='margin:0;font-size:13px;color:#991b1b;'>"
                f"<strong>Reason:</strong> {rejection_reason}</p></div>"
            )

        plain = (
            f"Dear {student_name},\n\n"
            f"After careful review, your application (Ref: {reference_number}) "
            f"for {program_name} was not approved at this time.\n"
            + (f"Reason: {rejection_reason}\n" if rejection_reason else "")
            + f"\nYou may contact the Education Department to discuss your application "
            f"or to reapply: ajalam149@gmail.com"
        )

        html_content = (
            f"<h2 style='color:#b91c1c;margin-top:0;'>Update on Your Application</h2>"
            f"<p>Dear <strong>{student_name}</strong>,</p>"
            f"<p>After careful review, we regret to inform you that your application for "
            f"<strong>{program_name}</strong> (Ref: <strong>{reference_number}</strong>) "
            f"has not been approved at this time.</p>"
            + reason_block
            + f"<p>If you believe this decision is in error, or if you would like to "
            f"discuss your application or reapply, please contact the Education Department:</p>"
            f"<p><a href='mailto:ajalam149@gmail.com' style='color:#3b82f6;font-weight:600;'>"
            f"ajalam149@gmail.com</a></p>"
            f"<p style='color:#64748b;font-size:13px;'>You may also submit a formal appeal "
            f"through the student portal within 30 days of this notice.</p>"
        )

    return send_email(
        to=student_email,
        subject=subject,
        html_body=_wrap(html_content),
        plain_body=plain,
    )


# ---------------------------------------------------------------------------
# 4. STUDENT — FUNDING PROCESSED
# ---------------------------------------------------------------------------

def send_funding_processed(
    student_email: str,
    student_name: str,
    program_name: str,
    semester: str,
    year: str,
    total_amount: float,
    funding_breakdown: list = None,   # list of {"name": str, "amount": float}
) -> bool:
    """
    Sent automatically when finance marks funding as processed / paid.

    Parameters
    ----------
    funding_breakdown : [{"name": "Tuition Bursary", "amount": 2500.00}, ...]
    """
    subject = "Your DGG Funding Has Been Processed \U0001f4b0"

    breakdown_rows = ""
    if funding_breakdown:
        for item in funding_breakdown:
            breakdown_rows += _row(item.get("name", "Bursary"), f"${float(item.get('amount', 0)):,.2f}")
    breakdown_rows += _row("<strong>Total Processed</strong>", f"<strong>${total_amount:,.2f}</strong>")

    plain = (
        f"Dear {student_name},\n\n"
        f"Your DGG funding for {program_name} ({semester} {year}) "
        f"has been processed.\n"
        f"Total: ${total_amount:,.2f}\n\n"
        f"Please allow 3-5 business days for funds to reflect in your account.\n"
        f"For queries: ajalam149@gmail.com"
    )

    html_content = (
        f"<h2 style='color:#166534;margin-top:0;'>Funding Processed \U0001f4b0</h2>"
        f"<p>Dear <strong>{student_name}</strong>,</p>"
        f"<p>Your DGG funding for <strong>{program_name}</strong> "
        f"({semester} {year}) has been processed and is on its way.</p>"
        f"<h3 style='color:#1e293b;margin:24px 0 12px;'>Payment Breakdown</h3>"
        f"<table style='width:100%;border-collapse:collapse;background:#f0fdf4;"
        f"border-radius:8px;padding:16px;'>"
        + breakdown_rows
        + "</table>"
        f"<div style='background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;"
        f"padding:16px;margin:24px 0;'>"
        f"<p style='margin:0;font-size:13px;color:#92400e;'>"
        f"<strong>Please allow 3&ndash;5 business days</strong> for the funds to "
        f"reflect in your account. If you do not receive your payment after 5 business "
        f"days, please contact us immediately.</p></div>"
        f"<p style='color:#64748b;font-size:13px;'>For queries contact "
        f"<a href='mailto:ajalam149@gmail.com' style='color:#3b82f6;'>ajalam149@gmail.com</a>.</p>"
    )

    return send_email(
        to=student_email,
        subject=subject,
        html_body=_wrap(html_content),
        plain_body=plain,
    )


# ---------------------------------------------------------------------------
# 5. FORGOT PASSWORD — RESET LINK
# ---------------------------------------------------------------------------

def send_password_reset(
    student_email: str,
    student_name: str,
    reset_link: str,
) -> bool:
    """
    Sent when a student requests a password reset.

    Parameters
    ----------
    reset_link : full HTTPS URL containing the secure token (expires in 30 min)
    """
    subject = "Reset Your DGG Portal Password"

    plain = (
        f"Dear {student_name},\n\n"
        f"We received a request to reset the password for your DGG Student Portal account.\n\n"
        f"Click the link below to reset your password (expires in 30 minutes):\n"
        f"{reset_link}\n\n"
        f"If you did not request this, please ignore this email and contact "
        f"ajalam149@gmail.com immediately.\n\n"
        f"Do NOT share this link with anyone."
    )

    html_content = (
        f"<h2 style='color:#1e293b;margin-top:0;'>Password Reset Request</h2>"
        f"<p>Dear <strong>{student_name}</strong>,</p>"
        f"<p>We received a request to reset the password for your DGG Student Portal account. "
        f"Click the button below to set a new password.</p>"
        f"<div style='text-align:center;margin:32px 0;'>"
        f"<a href='{reset_link}' style='background:#3b82f6;color:#ffffff;padding:14px 32px;"
        f"border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;display:inline-block;'>"
        f"Reset My Password</a></div>"
        f"<p style='font-size:13px;color:#64748b;'>Or copy and paste this link into your browser:</p>"
        f"<p style='font-size:12px;color:#3b82f6;word-break:break-all;'>{reset_link}</p>"
        f"<div style='background:#fef2f2;border:1px solid #fecaca;border-radius:8px;"
        f"padding:16px;margin:24px 0;'>"
        f"<p style='margin:0;font-size:13px;color:#991b1b;'>"
        f"<strong>This link expires in 30 minutes.</strong> "
        f"If you did not request a password reset, please ignore this email and contact "
        f"<a href='mailto:ajalam149@gmail.com' style='color:#991b1b;'>ajalam149@gmail.com</a> "
        f"immediately. Do NOT share this link with anyone.</p></div>"
    )

    return send_email(
        to=student_email,
        subject=subject,
        html_body=_wrap(html_content),
        plain_body=plain,
    )
