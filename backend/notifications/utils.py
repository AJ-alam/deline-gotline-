import logging
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
    """Send an email notification. Returns whether it was actually delivered.

    This used to hand the send to a daemon thread and return True immediately.
    That is unsafe on serverless: the platform freezes or reclaims the process
    once the response is returned, so the thread often never ran and the mail was
    silently dropped — while every caller had already been told it succeeded.
    Approval and denial notices were being lost this way with no error anywhere.

    Sending inline costs request latency (bounded by the SMTP timeout in
    email_sender), which is the correct trade against losing the mail outright.
    The durable fix is an outbox table drained by a cron worker; until that
    exists, callers get the truth.
    """
    try:
        from email_sender import send_email as _send
    except ImportError:
        logger.error("email_sender module not found — email not sent to %s", recipient_email)
        return False

    try:
        ok = _send(
            to=recipient_email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body or '',
        )
    except Exception:
        logger.exception("Email raised while sending to %s: %s", recipient_email, subject)
        return False

    if ok:
        logger.info("Email sent to %s: %s", recipient_email, subject)
    else:
        logger.error("Email failed to %s: %s", recipient_email, subject)
    return bool(ok)


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


def email_form_b_registrar_with_link(
    registrar_email: str,
    student_name: str,
    student_dob: str,
    student_id: str,
    institution: str,
    program: str,
    sem_start: str,
    sem_end: str,
    submission_id: int,
    form_b_link: str,
):
    """
    Form B — Enrollment Verification request with an online form link.
    Registrar clicks the link, fills in the form, and submits it back.
    """
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

    <p style="font-weight: 600; color: #1e293b;">Please complete the online verification form using the button below:</p>

    <div style="text-align: center; margin: 32px 0;">
      <a href="{form_b_link}"
         style="background: #1e293b; color: #e5a662; padding: 16px 36px; border-radius: 8px;
                text-decoration: none; font-weight: 800; font-size: 15px; display: inline-block;">
        Complete Enrollment Verification →
      </a>
    </div>

    <p style="font-size: 13px; color: #64748b;">Or copy and paste this link into your browser:</p>
    <p style="font-size: 12px; color: #3b82f6; word-break: break-all;">{form_b_link}</p>

    <div style="background: #fffbeb; border: 1px solid #fcd34d; border-radius: 6px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0; font-size: 12px; color: #92400e;">
        <strong>Important:</strong> This link expires in <strong>21 days</strong>.
        Funding disbursement to this student is contingent on receipt of this verification.
        Reference number <strong>DGG-{submission_id:04d}</strong> must appear in all correspondence.
      </p>
    </div>

    <p style="font-size: 13px; color: #64748b;">
      Thank you for your prompt attention. The DGG Education Department is committed to
      supporting Indigenous students in their academic journey.
    </p>
    """
    return send_email_notification(
        recipient_email=registrar_email,
        subject=f"Enrollment Verification Request — {student_name} (Ref: DGG-{submission_id:04d})",
        html_body=_base_template(body),
        plain_body=(
            f"Enrollment Verification Request for {student_name}. "
            f"Reference: DGG-{submission_id:04d}. "
            f"Please complete the online form at: {form_b_link} "
            f"(expires in 21 days)."
        ),
    )


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
    """Legacy wrapper — kept for backwards compatibility."""
    return email_form_b_registrar_with_link(
        registrar_email=registrar_email,
        student_name=student_name,
        student_dob=student_dob,
        student_id=student_id,
        institution=institution,
        program=program,
        sem_start=sem_start,
        sem_end=sem_end,
        submission_id=submission_id,
        form_b_link='(link not available — please contact education@deline.ca)',
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


def email_director_approval_request(
    director_email: str,
    student_name: str,
    form_title: str,
    amount: float,
    submission_id: int,
    approve_url: str = '',
    deny_url: str = '',
):
    """§3.1.D / §2: Director approval request — includes one-click approve/deny links."""
    action_buttons = ''
    if approve_url and deny_url:
        action_buttons = f"""
    <div style="margin: 32px 0; text-align: center;">
      <a href="{approve_url}"
         style="display:inline-block; background:#16a34a; color:#fff; font-weight:700;
                padding:14px 32px; border-radius:8px; text-decoration:none; font-size:15px; margin-right:12px;">
         ✅ Approve
      </a>
      <a href="{deny_url}"
         style="display:inline-block; background:#dc2626; color:#fff; font-weight:700;
                padding:14px 32px; border-radius:8px; text-decoration:none; font-size:15px;">
         ❌ Deny
      </a>
    </div>
    <p style="font-size:12px; color:#94a3b8; text-align:center;">
      These links are single-use and expire in 48 hours. No login required.
    </p>
    """
    else:
        action_buttons = '<p>Please log in to the Director portal to review and make a final decision.</p>'

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
    {action_buttons}
    """
    return send_email_notification(
        recipient_email=director_email,
        subject=f"Action Required — #{submission_id}: {student_name} ({form_title})",
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
