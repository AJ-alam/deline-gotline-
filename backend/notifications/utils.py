from .models import Notification
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def create_notification(user, title, message, link=None):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link
    )


def send_email_notification(recipient_email: str, subject: str, html_body: str, plain_body: str = '') -> bool:
    """Send email notification. Returns True on success, False on failure."""
    if not getattr(settings, 'EMAIL_HOST_USER', ''):
        logger.warning("EMAIL_HOST_USER not configured — email not sent to %s", recipient_email)
        return False
    try:
        send_mail(
            subject=subject,
            message=plain_body or html_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_body,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipient_email, exc)
        return False


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


def email_application_received(student_email: str, student_name: str, form_title: str):
    """Task 9.3: Application received notification"""
    body = f"""
    <h2 style="color: #1e293b;">Application Received</h2>
    <p>Dear {student_name},</p>
    <p>Your application for <strong>{form_title}</strong> has been successfully submitted and is now under review by our Student Support Workers.</p>
    <p>You will receive further updates as your application is processed. You can track the status of your application by logging into the student portal.</p>
    <p style="margin-top: 24px; color: #64748b;">Estimated review time: 5–10 business days.</p>
    """
    return send_email_notification(
        recipient_email=student_email,
        subject="Application Received — DGG Student Funding",
        html_body=_base_template(body),
    )


def email_application_approved(student_email: str, student_name: str, form_title: str, amount: float):
    """Task 9.4: Application approved notification"""
    body = f"""
    <h2 style="color: #1a6b3a;">Congratulations — Application Approved!</h2>
    <p>Dear {student_name},</p>
    <p>We are pleased to inform you that your application for <strong>{form_title}</strong> has been <strong style="color: #1a6b3a;">approved</strong>.</p>
    <div style="background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0; font-size: 13px; color: #64748b;">Approved Funding Amount</p>
      <p style="margin: 8px 0 0; font-size: 28px; font-weight: 900; color: #166534;">${amount:,.2f}</p>
    </div>
    <p>Your funding will be processed and disbursed to your account on file. You will receive a separate notification once payment has been issued.</p>
    """
    return send_email_notification(
        recipient_email=student_email,
        subject="Application Approved — DGG Student Funding",
        html_body=_base_template(body),
    )


def email_application_rejected(student_email: str, student_name: str, form_title: str, reason: str = ''):
    """Task 9.5: Application rejected notification"""
    reason_section = f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''
    body = f"""
    <h2 style="color: #b91c1c;">Application Update</h2>
    <p>Dear {student_name},</p>
    <p>After careful review, we regret to inform you that your application for <strong>{form_title}</strong> has not been approved at this time.</p>
    {reason_section}
    <p>If you believe this decision is in error, you may submit an appeal through the student portal within 30 days of this notice.</p>
    <p style="margin-top: 24px; color: #64748b;">Please contact your Student Support Worker if you have any questions.</p>
    """
    return send_email_notification(
        recipient_email=student_email,
        subject="Application Update — DGG Student Funding",
        html_body=_base_template(body),
    )


def email_payment_processed(student_email: str, student_name: str, amount: float, payment_type: str):
    """Task 9.6: Payment processed notification"""
    body = f"""
    <h2 style="color: #1e293b;">Payment Processed</h2>
    <p>Dear {student_name},</p>
    <p>A payment of <strong style="color: #166534;">${amount:,.2f}</strong> ({payment_type}) has been processed and will be deposited to your account on file within 3–5 business days.</p>
    <div style="background: #f0fdf4; border: 1px solid #dcfce7; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="margin: 0; font-size: 13px; color: #64748b;">Payment Amount</p>
      <p style="margin: 8px 0 0; font-size: 28px; font-weight: 900; color: #166534;">${amount:,.2f}</p>
    </div>
    """
    return send_email_notification(
        recipient_email=student_email,
        subject="Payment Processed — DGG Student Funding",
        html_body=_base_template(body),
    )


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
