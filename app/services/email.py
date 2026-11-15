import os
import json
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv


def _dispatch_email(to_email: str, subject: str, plain_text: str, html_content: str) -> bool:
    """
    Unified email delivery dispatcher.
    Priority 1: Resend REST API (if RESEND_API_KEY is configured in .env).
    Priority 2: Standard SMTP / Gmail (if SMTP_USER and SMTP_PASSWORD are configured in .env).
    Fallback: Logs full email to server console for testing/development.
    """
    load_dotenv(override=True)

    # 1. Try Resend API (HTTP POST to https://api.resend.com/emails)
    resend_key = os.environ.get("RESEND_API_KEY")
    if resend_key and resend_key.strip():
        from_addr = os.environ.get("RESEND_FROM_EMAIL") or os.environ.get("SMTP_FROM_EMAIL") or "GrievDesk <onboarding@resend.dev>"
        payload = json.dumps({
            "from": from_addr,
            "to": [to_email],
            "subject": subject,
            "text": plain_text,
            "html": html_content
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {resend_key.strip()}",
                "Content-Type": "application/json",
                "User-Agent": "GrievDesk/1.0"
            },
            method="POST"
        )
        try:
            print(f"[AUTH EMAIL] Sending email to {to_email} via Resend API...")
            with urllib.request.urlopen(req, timeout=12) as response:
                print(f"[AUTH EMAIL SUCCESS] Delivered to {to_email} via Resend API! (Status {response.status})")
                return True
        except Exception as e:
            print(f"[AUTH EMAIL WARNING] Resend API failed: {e}. Attempting SMTP fallback...")

    # 2. Try Standard SMTP (e.g. Gmail SMTP)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "noreply@grievdesk.org")

    if smtp_host and smtp_user and smtp_pass:
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
            return False

    print(f"[AUTH EMAIL NOTICE] Neither Resend nor SMTP is configured. Email logged to console only.")
    return True


def send_password_reset_otp_email(to_email: str, recipient_name: str, otp_code: str) -> bool:
    """
    Sends an OTP verification email to the user for resetting their password.
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

    print(f"\n=======================================================")
    print(f"[AUTH EMAIL] Password Reset OTP for {to_email} ({recipient_name}):")
    print(f"OTP CODE: {otp_code} (Valid for 10 minutes)")
    print(f"=======================================================\n")

    return _dispatch_email(to_email, subject, plain_text, html_content)


def send_resident_approved_email(to_email: str, recipient_name: str, flat_no: str, block_no: str) -> bool:
    """
    Sends an acknowledgment and welcome email to a new resident once approved by the Secretary.
    """
    subject = "GrievDesk - Registration Approved! Welcome to the Society Portal"
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    login_url = f"{frontend_url}/login"

    plain_text = f"""Hello {recipient_name},

Great news! The Society Secretary has approved your account registration for Flat {flat_no}, Block {block_no}.

Your resident account is now active. You can sign in to:
- Submit and track maintenance complaints
- View society notices and circulars
- Check and pay maintenance dues
- Book society amenities
- Access the resident directory

Sign in here: {login_url}

Regards,
GrievDesk Society Management
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 500px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #AEB6C2; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 4px; }}
    .society {{ font-size: 13px; color: #4A5563; margin-bottom: 24px; border-bottom: 1px solid #E3E6EB; padding-bottom: 12px; }}
    .badge-box {{ background-color: #E8F5E9; border: 1px solid #4CAF50; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center; }}
    .status-text {{ font-size: 18px; font-weight: 700; color: #2E7D32; margin: 0; }}
    .flat-info {{ font-size: 14px; color: #1B5E20; margin-top: 4px; font-family: monospace; }}
    .btn {{ display: inline-block; background-color: #0F52BA; color: #FFFFFF !important; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 16px; }}
    .features {{ margin: 16px 0; padding-left: 20px; font-size: 13px; line-height: 1.6; color: #374151; }}
    .footer {{ font-size: 12px; color: #6B7280; margin-top: 24px; border-top: 1px solid #E3E6EB; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk Portal</div>
    <div class="society">Residential Society Management System</div>
    <p>Dear <strong>{recipient_name}</strong>,</p>
    
    <div class="badge-box">
      <div class="status-text">Registration Approved &#x2705;</div>
      <div class="flat-info">Flat {flat_no} &bull; Block {block_no}</div>
    </div>
    
    <p>The Society Secretary has reviewed and approved your resident registration. Your portal account is now active.</p>
    
    <ul class="features">
      <li>Submit and track maintenance complaints with AI voice assistance</li>
      <li>View society-wide circulars and announcements</li>
      <li>Track monthly maintenance dues and payment receipts</li>
      <li>Book amenities like Clubhouse, Gym, and Tennis Court</li>
      <li>Search the resident and committee contact directory</li>
    </ul>
    
    <div style="text-align: center; margin: 24px 0;">
      <a href="{login_url}" class="btn">Sign In to GrievDesk</a>
    </div>
    
    <div class="footer">
      Welcome to the community! If you need assistance, contact your Society Secretary or Committee members.
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[AUTH EMAIL] Resident Approval Notification sent to {to_email} ({recipient_name}):")
    print(f"Status: APPROVED for Flat {flat_no}, Block {block_no}")
    print(f"=======================================================\n")

    return _dispatch_email(to_email, subject, plain_text, html_content)


def send_registration_received_email(to_email: str, recipient_name: str, flat_no: str, block_no: str) -> bool:
    """
    Sends an acknowledgment email to a resident upon registration, letting them know
    their flat approval request has been forwarded to the Secretary.
    """
    subject = "GrievDesk - Registration Submitted for Secretary Approval"
    
    plain_text = f"""Hello {recipient_name},

Thank you for registering your flat with GrievDesk Society Management!

Registration Details:
- Resident Name: {recipient_name}
- Flat: {flat_no}, Block {block_no}
- Registered Email: {to_email}

Your registration has been forwarded to the Society Secretary for approval.
You will receive an automated email confirmation as soon as your account is approved.

Regards,
GrievDesk Society Management
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 500px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #AEB6C2; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 4px; }}
    .society {{ font-size: 13px; color: #4A5563; margin-bottom: 24px; border-bottom: 1px solid #E3E6EB; padding-bottom: 12px; }}
    .badge-box {{ background-color: #FFF8E1; border: 1px solid #FFA000; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center; }}
    .status-text {{ font-size: 16px; font-weight: 700; color: #E65100; margin: 0; }}
    .flat-info {{ font-size: 13px; color: #795548; margin-top: 4px; font-family: monospace; }}
    .footer {{ font-size: 12px; color: #6B7280; margin-top: 24px; border-top: 1px solid #E3E6EB; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk Portal</div>
    <div class="society">Residential Society Management System</div>
    <p>Dear <strong>{recipient_name}</strong>,</p>
    
    <div class="badge-box">
      <div class="status-text">Registration Awaiting Approval &#x23F3;</div>
      <div class="flat-info">Flat {flat_no} &bull; Block {block_no}</div>
    </div>
    
    <p>Thank you for creating an account with GrievDesk. Your registration has been submitted and is currently in the queue for the Society Secretary to verify.</p>
    
    <p>As soon as the Secretary reviews and approves your residency, you will receive an approval email notification and will be able to log in.</p>
    
    <div class="footer">
      This is an automated acknowledgment. Please do not reply directly to this email.
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[AUTH EMAIL] Registration Acknowledgment sent to {to_email} ({recipient_name}):")
    print(f"Status: PENDING Secretary Approval for Flat {flat_no}, Block {block_no}")
    print(f"=======================================================\n")

    return _dispatch_email(to_email, subject, plain_text, html_content)


def send_vendor_task_assigned_email(
    vendor_email: str,
    vendor_name: str,
    vendor_profession: str,
    complaint_id: int,
    category: str,
    severity: str,
    description: str,
    flat_no: str,
    block_no: str,
    resident_name: str,
    notes: str,
    assigned_by_name: str,
    assigned_by_role: str,
) -> bool:
    """
    Sends an assignment work order email directly to the designated vendor/helper.
    Dispatched via Resend API (HTTP POST https://api.resend.com/emails) with SMTP fallback.
    Carries full ticket details and any written or transcribed voice notes in their local language.
    """
    subject = f"GrievDesk Task Assigned [Ticket #{complaint_id}] - {category or 'Society Maintenance'} ({vendor_profession})"
    
    flat_info = f"Flat {flat_no}, Block {block_no}" if flat_no and block_no else (flat_no or block_no or "Society Common Area")
    severity_str = (severity or "Medium").capitalize()
    notes_display = notes.strip() if notes and notes.strip() else "No special instructions provided."

    plain_text = f"""Hello {vendor_name},

A new society service task has been assigned to you on GrievDesk Residential Portal.

ASSIGNMENT DETAILS:
-------------------
Vendor: {vendor_name} ({vendor_profession})
Task Status: In Progress
Assigned By: {assigned_by_name} ({assigned_by_role.capitalize()})
Ticket ID: #{complaint_id}
Category: {category or 'General Maintenance'}
Priority: {severity_str}
Location: {flat_info}
Resident: {resident_name or 'Resident Member'}

ISSUE SUMMARY:
{description}

INSTRUCTIONS / NOTES (Written / Voice Note in Local Language):
{notes_display}

Please reach out to the resident or visit the society premises to attend to this task promptly.

Regards,
GrievDesk Society Management
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 540px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #AEB6C2; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 4px; }}
    .society {{ font-size: 13px; color: #4A5563; margin-bottom: 20px; border-bottom: 1px solid #E3E6EB; padding-bottom: 12px; }}
    .badge-box {{ background-color: #EFF6FF; border: 1px solid #93C5FD; border-radius: 8px; padding: 14px 18px; margin: 18px 0; display: flex; justify-content: space-between; align-items: center; }}
    .badge-title {{ font-size: 15px; font-weight: 700; color: #1E40AF; margin: 0; }}
    .status-pill {{ background-color: #2563EB; color: #FFFFFF; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 4px 10px; border-radius: 999px; }}
    .info-grid {{ width: 100%; border-collapse: collapse; margin: 18px 0; font-size: 13px; }}
    .info-grid td {{ padding: 8px 10px; border-bottom: 1px solid #F1F3F5; }}
    .info-grid td.label {{ color: #64748B; font-weight: 600; width: 36%; }}
    .info-grid td.value {{ color: #0F172A; font-weight: 500; }}
    .notes-box {{ background-color: #FEF3C7; border-left: 4px solid #F59E0B; border-radius: 6px; padding: 14px 16px; margin: 20px 0; font-size: 13px; }}
    .notes-title {{ font-weight: 700; color: #92400E; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }}
    .notes-content {{ color: #78350F; line-height: 1.5; white-space: pre-wrap; }}
    .desc-box {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px 14px; margin: 16px 0; font-size: 13px; color: #334155; line-height: 1.5; }}
    .footer {{ font-size: 12px; color: #64748B; margin-top: 24px; border-top: 1px solid #E3E6EB; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk &bull; Vendor Work Order</div>
    <div class="society">Society Maintenance &amp; Helper Allocation Desk</div>
    
    <p>Hello <strong>{vendor_name}</strong> ({vendor_profession}),</p>
    
    <div class="badge-box">
      <div>
        <div class="badge-title">Task Assigned &bull; #{complaint_id}</div>
        <div style="font-size: 12px; color: #3B82F6; margin-top: 2px;">Assigned by {assigned_by_name} ({assigned_by_role.capitalize()})</div>
      </div>
      <span class="status-pill">IN PROGRESS</span>
    </div>

    <table class="info-grid">
      <tr>
        <td class="label">Profession / Category</td>
        <td class="value"><strong>{vendor_profession}</strong></td>
      </tr>
      <tr>
        <td class="label">Location / Flat</td>
        <td class="value"><strong>{flat_info}</strong></td>
      </tr>
      <tr>
        <td class="label">Resident Contact</td>
        <td class="value">{resident_name or 'Resident Member'}</td>
      </tr>
      <tr>
        <td class="label">Priority / Severity</td>
        <td class="value">{severity_str}</td>
      </tr>
    </table>

    <div style="font-size: 12px; font-weight: 700; color: #475569; margin-top: 14px; text-transform: uppercase;">Resident Complaint Description:</div>
    <div class="desc-box">
      {description}
    </div>

    <div class="notes-box">
      <div class="notes-title">&#x1F4DD; Instructions / Voice Note (Local Language):</div>
      <div class="notes-content">{notes_display}</div>
    </div>

    <div class="footer">
      Please coordinate with the resident or society management to complete the work. When finished, notify the society committee to mark this ticket resolved.
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[VENDOR ALLOCATION EMAIL] Task #{complaint_id} Assigned to {vendor_name} ({vendor_email}):")
    print(f"Profession: {vendor_profession} | Location: {flat_info}")
    print(f"Local Language Note: {notes_display}")
    print(f"=======================================================\n")

    return _dispatch_email(vendor_email, subject, plain_text, html_content)


def send_due_notice_email(
    to_email: str,
    resident_name: str,
    flat_no: str,
    block_no: str,
    month: str,
    amount: str,
    due_date: str,
    notes: str = None,
    created_by_name: str = None,
) -> bool:
    """
    Sends an official society maintenance due bill & invoice email directly to the resident's Gmail.
    Dispatched via Resend API (HTTP POST https://api.resend.com/emails) with Gmail SMTP fallback.
    Carries full billing breakdown and custom notes/instructions from Secretary/Committee.
    """
    subject = f"GrievDesk Maintenance Due Notice: {month} - Flat {flat_no}, Block {block_no} (₹{amount})"

    notes_display = notes.strip() if notes and notes.strip() else "No special payment notes provided."
    by_line = f"Generated by {created_by_name}" if created_by_name else "Generated by Society Management"

    plain_text = f"""Hello {resident_name},

This is an official maintenance due notification from GrievDesk Residential Society for your apartment.

BILLING DETAILS:
----------------
Resident Name: {resident_name}
Flat / Block: Flat {flat_no}, Block {block_no}
Billing Month: {month}
Payable Amount: ₹{amount}
Payment Due Date: {due_date}
Status: Unpaid / Pending
Issued By: {by_line}

INSTRUCTIONS / NOTES FROM SOCIETY OFFICE:
{notes_display}

Please clear your society maintenance dues on or before {due_date} to ensure uninterrupted society amenities, water supply, security, and maintenance operations.

Regards,
GrievDesk Society Management
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 520px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #AEB6C2; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 4px; }}
    .society {{ font-size: 13px; color: #4A5563; margin-bottom: 20px; border-bottom: 1px solid #E3E6EB; padding-bottom: 12px; }}
    .invoice-badge {{ background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 14px 18px; margin: 18px 0; display: flex; justify-content: space-between; align-items: center; }}
    .invoice-amount {{ font-size: 24px; font-weight: 800; color: #DC2626; margin: 0; }}
    .status-pill {{ background-color: #EF4444; color: #FFFFFF; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 4px 10px; border-radius: 999px; }}
    .info-table {{ width: 100%; border-collapse: collapse; margin: 18px 0; font-size: 13px; }}
    .info-table td {{ padding: 8px 10px; border-bottom: 1px solid #F1F3F5; }}
    .info-table td.label {{ color: #64748B; font-weight: 600; width: 38%; }}
    .info-table td.value {{ color: #0F172A; font-weight: 500; }}
    .notes-box {{ background-color: #FEF3C7; border-left: 4px solid #F59E0B; border-radius: 6px; padding: 14px 16px; margin: 20px 0; font-size: 13px; }}
    .notes-title {{ font-weight: 700; color: #92400E; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }}
    .notes-content {{ color: #78350F; line-height: 1.5; white-space: pre-wrap; }}
    .footer {{ font-size: 12px; color: #64748B; margin-top: 24px; border-top: 1px solid #E3E6EB; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk &bull; Maintenance Bill</div>
    <div class="society">Residential Society Management Portal</div>
    
    <p>Dear <strong>{resident_name}</strong>,</p>
    <p>This is your official maintenance invoice for <strong>Flat {flat_no}, Block {block_no}</strong>.</p>

    <div class="invoice-badge">
      <div>
        <div style="font-size: 12px; color: #991B1B; font-weight: 600; text-transform: uppercase;">Amount Due for {month}</div>
        <div class="invoice-amount">&#x20B9;{amount}</div>
      </div>
      <span class="status-pill">PENDING PAYMENT</span>
    </div>

    <table class="info-table">
      <tr>
        <td class="label">Resident Name</td>
        <td class="value"><strong>{resident_name}</strong></td>
      </tr>
      <tr>
        <td class="label">Apartment</td>
        <td class="value">Flat {flat_no}, Block {block_no}</td>
      </tr>
      <tr>
        <td class="label">Billing Period</td>
        <td class="value">{month}</td>
      </tr>
      <tr>
        <td class="label">Payment Due Date</td>
        <td class="value"><strong style="color: #DC2626;">{due_date}</strong></td>
      </tr>
      <tr>
        <td class="label">Issued By</td>
        <td class="value">{by_line}</td>
      </tr>
    </table>

    <div class="notes-box">
      <div class="notes-title">&#x1F4DD; Payment Instructions &amp; Note:</div>
      <div class="notes-content">{notes_display}</div>
    </div>

    <div class="footer">
      Please settle your maintenance payment on or before the due date. Once payment is made, notify the society committee or secretary to get your official receipt updated on GrievDesk.
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[DUES NOTICE EMAIL] Sent to {resident_name} ({to_email}):")
    print(f"Month: {month} | Amount: ₹{amount} | Flat {flat_no}, Block {block_no}")
    print(f"Notes: {notes_display}")
    print(f"=======================================================\n")

    return _dispatch_email(to_email, subject, plain_text, html_content)


