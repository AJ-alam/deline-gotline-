
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from email_sender import send_email

# Test parameters
to = "alamjabbar571@gmail.com"
subject = "Test Email from DGG Portal"
html_body = "<h1>Test</h1><p>This is a test email to verify SMTP settings.</p>"
plain_body = "This is a test email to verify SMTP settings."

print(f"Attempting to send test email to {to}...")
success = send_email(to, subject, html_body, plain_body)

if success:
    print("Email sent successfully!")
else:
    print("Failed to send email. Check console output for errors.")
