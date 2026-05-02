import logging
import threading
from .models import Notification

logger = logging.getLogger(__name__)


def create_notification(user, title, message, link=None):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link
    )


def send_email_notification(recipient_email: str, subject: str, html_body: str, plain_body: str = '') -> bool:
    """Send email notification via email_sender (smtplib/Gmail) in a background thread."""
    try:
        from email_sender import send_email as _send
    except ImportError:
        logger.error("email_sender module not found — email not sent to %s", recipient_email)
        return False

    def _bg():
        ok = _send(
            to=recipient_email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body or '',
        )
        if ok:
            logger.info("Email sent to %s: %s", recipient_email, subject)
        else:
            logger.error("Email failed to %s: %s", recipient_email, subject)

    threading.Thread(target=_bg, daemon=True).start()
    return True


# ── EMAIL TEMPLATES (Task 9.2) ──

def _base_template(content: str) -> str:
    return f"""
    <html><body style="font-family: Arial, sans-serif; background: #f5f0ea; padding: 32px;">
    <div style="max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
      <div style="background: #1e293b; padding: 24px 32px;">
        <h1 style="color: #e5a662; margin: 0; font-size: 20px;">Deline Gotlı̨né Gots'ę́</h1>
        <p style="color: rgba(255,255,255,0.6); margin: 4px 0 0; font-size: 12px;">Student Funding Administration</p>
      </div>
      <div style="padding: 32px;">
        {content}
      </div>
      <div style="background: #f8fafc; padding: 16px 32px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8;">
        This is an automated message from the DGG Student Funding Application portal. Do not reply to this email.
      </div>
    </div>
    </body></html>
    """


def email_form_b_registrar(
    registrar_email: str,
    student_name: str,
    student_dob: str,
    student_id: str,
    institution: str,
    program: str,
    sem_start: str,
    sem_end: str,
    submission_id: int,
):
    """Form B — Enrollment Verification request sent to institution registrar on Form A submission."""
    body = f"""
    <h2 style="color: #1e293b;">Enrollment Verification Request — Form B</h2>
    <p>Dear Registrar,</p>
    <p>The <strong>Deline Got'ı̨nę Government (DGG) Student Funding Program</strong> is requesting enrollment
    verification for the following student who has applied for educational funding support.</p>

    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin: 24px 0;">
      <p style="margin: 0 0 12px; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Student Information</p>
      <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
        <tr><td style="padding: 6px 0; color: #64748b; width: 160px;">Full Name</td><td style="padding: 6px 0; font-weight: 600;">{student_name}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Date of Birth</td><td style="padding: 6px 0; font-weight: 600;">{student_dob or 'On file'}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Student ID</td><td style="padding: 6px 0; font-weight: 600;">{student_id or 'To be confirmed'}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Institution</td><td style="padding: 6px 0; font-weight: 600;">{institution}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Program</td><td style="padding: 6px 0; font-weight: 600;">{program}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Semester Start</td><td style="padding: 6px 0; font-weight: 600;">{sem_start}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Semester End</td><td style="padding: 6px 0; font-weight: 600;">{sem_end}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">Reference #</td><td style="padding: 6px 0; font-weight: 600;">DGG-{submission_id:04d}</td></tr>
      </table>
    </div>

    <p style="font-weight: 600; color: #1e293b;">Please confirm the following by replying to this email within <u>14 calendar days</u>:</p>
    <ol style="font-size: 13px; color: #374151; line-height: 2;">
      <li>Is the student currently enrolled in good standing?</li>
      <li>Confirm the program name and credential level</li>
      <li>Confirm enrollment status (Full-time / Part-time) and course load percentage</li>
      <li>Confirm semester start and end dates</li>
      <li>Provide official tuition amount for the semester</li>
    </ol>

    <div style="background: #fffbeb; border: 1px solid #fcd34d; border-radius: 6px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0; font-size: 12px; color: #92400e;">
        <strong>Important:</strong> Funding disbursement to this student is contingent on receipt of this verification.
        Please reply to <strong>education@deline.ca</strong> or contact your DGG Student Support Worker directly.
        Reference number <strong>DGG-{submission_id:04d}</strong> must appear in all correspondence.
      </p>
    </div>

    <p style="font-size: 13px; color: #64748b;">
      Thank you for your prompt attention to this matter. The DGG Education Department is committed to
      supporting Indigenous students in their academic journey.
    </p>
    """
    return send_email_notification(
        recipient_email=registrar_email,
        subject=f"Enrollment Verification Request — {student_name} (Ref: DGG-{submission_id:04d})",
        html_body=_base_template(body),
        plain_body=f"Enrollment Verification Request for {student_name}. Reference: DGG-{submission_id:04d}. Please confirm enrollment at {institution} for {program} ({sem_start} to {sem_end}). Reply to education@deline.ca within 14 days.",
    )


def email_application_received(student_email: str, student_name: str, form_title: str, submission_id: int = 0, submitted_at=None):
    """Application received — delegates to email_sender for real SMTP delivery."""
    try:
        from email_sender import send_application_received
        from datetime import datetime
        dt = submitted_at if submitted_at else datetime.now()
        return send_application_received(
            student_email=student_email,
            student_name=student_name,
            reference_number=f"FS-{submission_id:04d}" if submission_id else "FS-????",
            program_name=form_title,
            submitted_at=dt,
        )
    except Exception as exc:
        logger.error("email_application_received failed: %s", exc)
        return False


def email_application_approved(student_email: str, student_name: str, form_title: str, amount: float,
                                submission_id: int = 0, semester: str = "", year: str = "",
                                funding_breakdown: list = None):
    """Application approved — delegates to email_sender."""
    try:
        from email_sender import send_application_decision
        return send_application_decision(
            student_email=student_email,
            student_name=student_name,
            reference_number=f"FS-{submission_id:04d}" if submission_id else "FS-????",
            program_name=form_title,
            approved=True,
            semester=semester,
            year=year,
            funding_breakdown=funding_breakdown or [{"name": "Approved Funding", "amount": amount}],
            total_amount=amount,
        )
    except Exception as exc:
        logger.error("email_application_approved failed: %s", exc)
        return False


def email_application_rejected(student_email: str, student_name: str, form_title: str, reason: str = '',
                                submission_id: int = 0):
    """Application rejected — delegates to email_sender."""
    try:
        from email_sender import send_application_decision
        return send_application_decision(
            student_email=student_email,
            student_name=student_name,
            reference_number=f"FS-{submission_id:04d}" if submission_id else "FS-????",
            program_name=form_title,
            approved=False,
            rejection_reason=reason,
        )
    except Exception as exc:
        logger.error("email_application_rejected failed: %s", exc)
        return False


def email_payment_processed(student_email: str, student_name: str, amount: float, payment_type: str,
                             program_name: str = "", semester: str = "", year: str = "",
                             funding_breakdown: list = None):
    """Payment processed — delegates to email_sender."""
    try:
        from email_sender import send_funding_processed
        return send_funding_processed(
            student_email=student_email,
            student_name=student_name,
            program_name=program_name or payment_type,
            semester=semester,
            year=year,
            total_amount=amount,
            funding_breakdown=funding_breakdown or [{"name": payment_type, "amount": amount}],
        )
    except Exception as exc:
        logger.error("email_payment_processed failed: %s", exc)
        return False


def email_more_info_requested(student_email: str, student_name: str, form_title: str, notes: str = ''):
    """Notify student that staff has requested more information."""
    notes_section = f'<div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:6px;padding:16px;margin:24px 0;"><p style="margin:0;font-size:13px;color:#92400e;"><strong>Information Requested:</strong> {notes}</p></div>' if notes else ''
    body = f"""
    <h2 style="color: #1e293b;">Action Required — Additional Information Needed</h2>
    <p>Dear {student_name},</p>
    <p>Your Student Support Worker has reviewed your application for <strong>{form_title}</strong> and requires additional information before it can be processed.</p>
    {notes_section}
    <p>Please log in to the student portal to view the details and submit the requested information at your earliest convenience.</p>
    <p style="margin-top: 24px; color: #64748b;">If you have any questions, please contact your Student Support Worker directly.</p>
    """
    return send_email_notification(
        recipient_email=student_email,
        subject="Action Required: Additional Information Needed — DGG Student Funding",
        html_body=_base_template(body),
        plain_body=f"Your application for {form_title} requires additional information. Notes: {notes}. Please log in to the portal.",
    )


def email_director_approval_request(director_email: str, student_name: str, form_title: str, amount: float, submission_id: int):
    """Task 9.7: Director approval request notification"""
    body = f"""
    <h2 style="color: #1e293b;">Application Awaiting Your Approval</h2>
    <p>A new application has been reviewed by the SSW team and forwarded for your decision.</p>
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0 0 8px; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Submission Details</p>
      <p style="margin: 4px 0;"><strong>Student:</strong> {student_name}</p>
      <p style="margin: 4px 0;"><strong>Program:</strong> {form_title}</p>
      <p style="margin: 4px 0;"><strong>Calculated Funding:</strong> ${amount:,.2f}</p>
      <p style="margin: 4px 0;"><strong>Reference #:</strong> {submission_id}</p>
    </div>
    <p>Please log in to the Director portal to review and make a final decision.</p>
    """
    return send_email_notification(
        recipient_email=director_email,
        subject=f"Approval Required: #{submission_id} — {student_name}",
        html_body=_base_template(body),
    )


def email_finance_payment_details(
    finance_email: str,
    student_name: str,
    amount: float,
    payment_type: str,
    funding_stream: str,
    bank_name: str = '',
    account_number: str = '',
    transit_number: str = '',
    submission_id: int = 0,
):
    """Task 9.8 / Task 11: Finance payment details notification"""
    banking_section = ''
    if bank_name or account_number:
        banking_section = f"""
        <div style="background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 8px; padding: 16px; margin: 24px 0;">
          <p style="margin: 0 0 8px; font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase;">Banking Information</p>
          {'<p style="margin: 4px 0;"><strong>Bank:</strong> ' + bank_name + '</p>' if bank_name else ''}
          {'<p style="margin: 4px 0;"><strong>Account #:</strong> ' + account_number + '</p>' if account_number else ''}
          {'<p style="margin: 4px 0;"><strong>Transit #:</strong> ' + transit_number + '</p>' if transit_number else ''}
        </div>
        """
    body = f"""
    <h2 style="color: #1e293b;">Payment Authorization Required</h2>
    <p>The following payment has been approved and requires processing by the Finance Department.</p>
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0 0 8px; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Payment Details</p>
      <p style="margin: 4px 0;"><strong>Student:</strong> {student_name}</p>
      <p style="margin: 4px 0;"><strong>Amount:</strong> ${amount:,.2f}</p>
      <p style="margin: 4px 0;"><strong>Payment Type:</strong> {payment_type}</p>
      <p style="margin: 4px 0;"><strong>Funding Stream:</strong> {funding_stream}</p>
      <p style="margin: 4px 0;"><strong>Reference #:</strong> {submission_id}</p>
    </div>
    {banking_section}
    """
    return send_email_notification(
        recipient_email=finance_email,
        subject=f"Payment Authorization #{submission_id} — {student_name} (${amount:,.2f})",
        html_body=_base_template(body),
    )

def email_new_submission_staff(staff_emails: list, student_name: str, form_title: str, submission_id: int, answers_summary: str):
    """Notify staff and directors of a new application submission."""
    body = f"""
    <h2 style="color: #1e293b;">New Application Received</h2>
    <p>A new application has been submitted and is awaiting review.</p>
    
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0 0 8px; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Submission Details</p>
      <p style="margin: 4px 0;"><strong>Student:</strong> {student_name}</p>
      <p style="margin: 4px 0;"><strong>Form:</strong> {form_title}</p>
      <p style="margin: 4px 0;"><strong>Reference #:</strong> {submission_id}</p>
    </div>

    <div style="background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0 0 8px; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Form Content Summary</p>
      <div style="font-size: 13px; line-height: 1.6; color: #374151;">
        {answers_summary}
      </div>
    </div>

    <p>Please log in to the Staff Dashboard to review this application.</p>
    """
    for email in staff_emails:
        send_email_notification(
            recipient_email=email,
            subject=f"New Submission: #{submission_id} — {student_name}",
            html_body=_base_template(body),
        )
