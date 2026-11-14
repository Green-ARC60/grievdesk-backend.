import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv


def send_password_reset_otp_email(to_email: str, recipient_name: str, otp_code: str) -> bool:
    """
    Sends an OTP verification email to the user for resetting their password.
    If SMTP credentials are configured, sends via SMTP (TLS).
    Always logs the OTP to the console for development and local testing.
    """
    subject = f"GrievDesk - Password Reset OTP: {otp_code}"
    
    plain_text = f"""Hello {recipient_name},

We received a request to reset your password for your GrievDesk Society account.

Your 6-digit verification code (OTP) is:
{otp_code}

This verification code is valid for 10 minutes.

If you did not request a password reset, please ignore this email or alert your Society Secretary.

Regards,
GrievDesk Society Management
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 480px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #AEB6C2; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 8px; }}
    .society {{ font-size: 13px; color: #4A5563; margin-bottom: 24px; border-bottom: 1px solid #E3E6EB; padding-bottom: 12px; }}
    .otp-box {{ background-color: #E5EFF7; border: 1px dashed #0F52BA; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0; }}
    .otp-code {{ font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #0F52BA; font-family: 'Courier New', monospace; margin: 0; }}
    .expiry {{ font-size: 12px; color: #B04A12; margin-top: 8px; font-weight: 600; }}
    .footer {{ font-size: 12px; color: #6B7280; margin-top: 24px; line-height: 1.5; border-top: 1px solid #E3E6EB; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk Portal</div>
    <div class="society">Residential Society Management System</div>
    <p>Hello <strong>{recipient_name}</strong>,</p>
    <p>We received a request to reset the password for your GrievDesk account registered to <strong>{to_email}</strong>.</p>
    
    <div class="otp-box">
      <div class="otp-code">{otp_code}</div>
      <div class="expiry">Expires in 10 minutes</div>
    </div>
    
    <p>Enter this verification code in the application to choose a new password.</p>
    
    <div class="footer">
      If you did not request this verification code, please ignore this email. Your current password remains unchanged.
    </div>
  </div>
</body>
</html>"""

    # Always log to stdout so developers/testers can verify without checking inbox
    print(f"\n=======================================================")
    print(f"[AUTH EMAIL] Password Reset OTP for {to_email} ({recipient_name}):")
    print(f"OTP CODE: {otp_code} (Valid for 10 minutes)")
    print(f"=======================================================\n")

    load_dotenv(override=True)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "noreply@grievdesk.org")

    if not smtp_host or not smtp_user or not smtp_pass:
        print(f"[AUTH EMAIL] SMTP not configured. Logged OTP to console only.")
        return True

    try:
        print(f"[AUTH EMAIL] Connecting to {smtp_host}:{smtp_port} as {smtp_user}...")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"GrievDesk Support <{from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                server.ehlo()
                if os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"):
                    server.starttls()
                    server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, [to_email], msg.as_string())

        print(f"[AUTH EMAIL SUCCESS] Real email delivered to {to_email} via Gmail SMTP!")
        return True
    except Exception as e:
        print(f"[AUTH EMAIL ERROR] Could not send email via SMTP: {e}")
        return True

