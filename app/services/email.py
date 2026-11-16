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


def send_mass_vendor_work_order_email(
    vendor_email: str,
    vendor_name: str,
    vendor_profession: str,
    tasks_summary: list,
    total_count: int,
    notes: str = None,
    assigned_by_name: str = "Society Secretary",
    assigned_by_role: str = "Secretary",
) -> bool:
    """
    Sends a consolidated MASS WORK ORDER invoice email to a vendor when assigned a batch
    of complaints (e.g. 50-100 electrical or plumbing tickets) in bulk.
    Dispatched via Resend API (with SMTP fallback).
    """
    subject = f"GrievDesk Mass Work Order: [Batch of {total_count} Tickets] - {vendor_profession} ({vendor_name})"

    notes_display = notes.strip() if notes and notes.strip() else "No special batch instructions provided."

    plain_rows = []
    for idx, t in enumerate(tasks_summary, 1):
        flat_info = f"Flat {t.get('flat_no', '')}, Block {t.get('block_no', '')}" if t.get('flat_no') else "Common Area"
        plain_rows.append(
            f"#{t.get('id')} | {flat_info} | {t.get('category', 'General')} ({t.get('severity', 'medium')}) | {t.get('description', '')[:70]}"
        )
    plain_list = "\n".join(plain_rows[:120])
    if len(tasks_summary) > 120:
        plain_list += f"\n... and {len(tasks_summary) - 120} more tickets in this batch."

    plain_text = f"""Hello {vendor_name},

You have been assigned a MASS BATCH of {total_count} society service tasks on GrievDesk Residential Portal.

BATCH DETAILS:
--------------
Vendor: {vendor_name} ({vendor_profession})
Total Assigned Tickets: {total_count}
Assigned By: {assigned_by_name} ({assigned_by_role.capitalize()})
Status: In Progress

BATCH INSTRUCTIONS / NOTES (Written / Voice Note in Local Language):
{notes_display}

ASSIGNED TICKETS LIST:
------------------------------------------------------------
{plain_list}
------------------------------------------------------------

Please coordinate with society management and the residents to attend to these tasks systematically.
All {total_count} tickets have been moved to "IN PROGRESS" status on the society portal.

Regards,
GrievDesk Society Management
"""

    html_rows = []
    for idx, t in enumerate(tasks_summary, 1):
        flat_info = f"Flat {t.get('flat_no', '-')}, Block {t.get('block_no', '-')}"
        desc_snippet = (t.get('description') or 'No description')[:90]
        sev = (t.get('severity') or 'medium').lower()
        sev_color = "#DC2626" if sev == "high" else "#D97706" if sev == "medium" else "#2563EB"
        html_rows.append(f"""
        <tr>
          <td style="padding: 7px 10px; border-bottom: 1px solid #F1F3F5; font-weight: 700; color: #0F52BA;">#{t.get('id')}</td>
          <td style="padding: 7px 10px; border-bottom: 1px solid #F1F3F5; font-weight: 600;">{flat_info}</td>
          <td style="padding: 7px 10px; border-bottom: 1px solid #F1F3F5;">{t.get('category', 'General')}</td>
          <td style="padding: 7px 10px; border-bottom: 1px solid #F1F3F5; font-weight: 700; color: {sev_color}; text-transform: uppercase; font-size: 11px;">{sev}</td>
          <td style="padding: 7px 10px; border-bottom: 1px solid #F1F3F5; color: #475569; font-size: 12px;">{desc_snippet}</td>
        </tr>""")
    html_table_body = "".join(html_rows)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 620px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #AEB6C2; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 4px; }}
    .society {{ font-size: 13px; color: #4A5563; margin-bottom: 20px; border-bottom: 1px solid #E3E6EB; padding-bottom: 12px; }}
    .batch-banner {{ background: linear-gradient(135deg, #0F52BA 0%, #1E3A8A 100%); color: #FFFFFF; border-radius: 8px; padding: 18px 20px; margin: 18px 0; display: flex; justify-content: space-between; align-items: center; }}
    .batch-count {{ font-size: 28px; font-weight: 800; letter-spacing: 0.5px; line-height: 1; }}
    .batch-sub {{ font-size: 12px; opacity: 0.9; margin-top: 4px; }}
    .status-badge {{ background-color: #F59E0B; color: #FFFFFF; font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 5px 12px; border-radius: 999px; letter-spacing: 0.5px; }}
    .notes-box {{ background-color: #FEF3C7; border-left: 4px solid #F59E0B; border-radius: 6px; padding: 14px 16px; margin: 20px 0; font-size: 13px; }}
    .notes-title {{ font-weight: 700; color: #92400E; margin-bottom: 6px; }}
    .notes-content {{ color: #78350F; line-height: 1.5; white-space: pre-wrap; }}
    .table-container {{ margin: 20px 0; max-height: 380px; overflow-y: auto; border: 1px solid #E2E8F0; border-radius: 8px; }}
    .work-table {{ width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }}
    .work-table th {{ background-color: #F8FAFC; padding: 9px 10px; font-weight: 700; color: #475569; border-bottom: 1px solid #CBD5E1; text-transform: uppercase; font-size: 11px; }}
    .footer {{ font-size: 12px; color: #64748B; margin-top: 24px; border-top: 1px solid #E3E6EB; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk &bull; Mass Work Order Dispatch</div>
    <div class="society">Society Maintenance &amp; Workload Distribution Desk</div>

    <p>Hello <strong>{vendor_name}</strong> ({vendor_profession}),</p>

    <div class="batch-banner">
      <div>
        <div class="batch-count">{total_count} Tickets Assigned</div>
        <div class="batch-sub">Assigned by {assigned_by_name} ({assigned_by_role.capitalize()}) &bull; Category: {vendor_profession}</div>
      </div>
      <span class="status-badge">IN PROGRESS</span>
    </div>

    <div class="notes-box">
      <div class="notes-title">&#x1F4DD; Mass Assignment Instructions (Local Language):</div>
      <div class="notes-content">{notes_display}</div>
    </div>

    <div style="font-size: 13px; font-weight: 700; color: #1E293B; margin-top: 16px;">Itemized Ticket Manifest:</div>
    <div class="table-container">
      <table class="work-table">
        <thead>
          <tr>
            <th>Ticket</th>
            <th>Location</th>
            <th>Category</th>
            <th>Priority</th>
            <th>Issue Summary</th>
          </tr>
        </thead>
        <tbody>
          {html_table_body}
        </tbody>
      </table>
    </div>

    <div class="footer">
      Please organize your tools and materials to visit the listed flats. All {total_count} tickets are now in <strong>In Progress</strong> status on the GrievDesk society portal. Notify the society management upon completion of each flat.
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[MASS VENDOR ALLOCATION EMAIL] Batch of {total_count} Tasks Assigned to {vendor_name} ({vendor_email}):")
    print(f"Profession: {vendor_profession} | Tickets Count: {total_count}")
    print(f"Notes: {notes_display}")
    print(f"=======================================================\n")

    return _dispatch_email(vendor_email, subject, plain_text, html_content)


def send_resident_complaint_assigned_email(
    resident_email: str,
    resident_name: str,
    flat_no: str,
    block_no: str,
    complaint_id: int,
    category: str,
    description: str,
    vendor_name: str,
    vendor_profession: str,
    vendor_phone: str = None,
    vendor_address: str = None,
    notes: str = None,
    assigned_by_name: str = None,
    assigned_by_role: str = None,
) -> bool:
    """
    Sends a friendly, reassuring acknowledgement email to the resident who raised the complaint,
    informing them that their ticket has been assigned to an authorized society specialist/vendor.
    """
    subject = f"GrievDesk: Your Complaint #{complaint_id} is Assigned to {vendor_name} ({vendor_profession})"

    notes_display = notes.strip() if notes and notes.strip() else "Vendor instructed to inspect and attend to your apartment issue promptly."
    phone_display = vendor_phone if vendor_phone else "Available via Society Security / Complex Office"
    address_display = vendor_address if vendor_address else "Society Commercial Complex"
    assigned_by_line = f"{assigned_by_name} ({assigned_by_role.capitalize()})" if assigned_by_name and assigned_by_role else "Society Management"

    plain_text = f"""Hello {resident_name},

Good news! Your society complaint #{complaint_id} regarding '{category}' has been reviewed and assigned to a specialist.

STATUS: IN PROGRESS
-------------------------------------------------------
Ticket ID: #{complaint_id}
Apartment: Flat {flat_no}, Block {block_no}
Category: {category}
Issue Description: {description}

ASSIGNED SPECIALIST / HELPER:
-------------------------------------------------------
Specialist: {vendor_name} ({vendor_profession})
Contact Phone: {phone_display}
Shop / Complex Location: {address_display}
Assigned By: {assigned_by_line}

SPECIAL INSTRUCTIONS / NOTE:
-------------------------------------------------------
{notes_display}

WHAT HAPPENS NEXT:
1. The specialist has received the work order along with your flat details and will coordinate with you or visit your flat shortly.
2. Once the technician completes the repair, please log in to GrievDesk (Public Inbox or My Tickets) to mark your complaint as 'Resolved'.

Regards,
GrievDesk Society Management
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #EEF0F3; margin: 0; padding: 24px; color: #1F262E; }}
    .card {{ max-width: 540px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #CBD5E1; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
    .header {{ font-size: 20px; font-weight: 700; color: #0F52BA; margin-bottom: 4px; }}
    .society {{ font-size: 13px; color: #64748B; margin-bottom: 20px; border-bottom: 1px solid #E2E8F0; padding-bottom: 12px; }}
    .status-banner {{ background: linear-gradient(135deg, #EFF6FF, #DBEAFE); border: 1px solid #BFDBFE; border-radius: 8px; padding: 14px 18px; margin: 18px 0; display: flex; justify-content: space-between; align-items: center; }}
    .status-title {{ font-size: 15px; font-weight: 700; color: #1E40AF; margin: 0; }}
    .status-sub {{ font-size: 12px; color: #3B82F6; margin-top: 2px; }}
    .status-pill {{ background-color: #2563EB; color: #FFFFFF; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 5px 12px; border-radius: 999px; }}
    .info-table {{ width: 100%; border-collapse: collapse; margin: 18px 0; font-size: 13px; }}
    .info-table td {{ padding: 8px 10px; border-bottom: 1px solid #F1F5F9; }}
    .info-table td.label {{ color: #64748B; font-weight: 600; width: 38%; }}
    .info-table td.value {{ color: #0F172A; font-weight: 500; }}
    .notes-box {{ background-color: #FEF3C7; border-left: 4px solid #F59E0B; border-radius: 6px; padding: 14px 16px; margin: 20px 0; font-size: 13px; }}
    .notes-title {{ font-weight: 700; color: #92400E; margin-bottom: 6px; }}
    .notes-content {{ color: #78350F; line-height: 1.5; white-space: pre-wrap; }}
    .next-steps {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px 16px; margin: 20px 0; font-size: 12px; color: #334155; line-height: 1.6; }}
    .next-steps strong {{ color: #0F172A; }}
    .footer {{ font-size: 12px; color: #64748B; margin-top: 24px; border-top: 1px solid #E2E8F0; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">GrievDesk &bull; Task Assigned to Vendor</div>
    <div class="society">Residential Grievance Redressal &amp; Maintenance Portal</div>

    <p>Dear <strong>{resident_name}</strong>,</p>
    <p>Your complaint has been reviewed by the society office and assigned to an authorized specialist.</p>

    <div class="status-banner">
      <div>
        <div class="status-title">Assigned to {vendor_name}</div>
        <div class="status-sub">{vendor_profession} &bull; Ticket #{complaint_id}</div>
      </div>
      <span class="status-pill">IN PROGRESS</span>
    </div>

    <table class="info-table">
      <tr>
        <td class="label">Complaint Ticket</td>
        <td class="value"><strong>#{complaint_id}</strong> ({category})</td>
      </tr>
      <tr>
        <td class="label">Your Location</td>
        <td class="value">Flat {flat_no}, Block {block_no}</td>
      </tr>
      <tr>
        <td class="label">Issue Summary</td>
        <td class="value">{description}</td>
      </tr>
      <tr>
        <td class="label">Assigned Specialist</td>
        <td class="value"><strong>{vendor_name}</strong> ({vendor_profession})</td>
      </tr>
      <tr>
        <td class="label">Specialist Phone</td>
        <td class="value"><strong style="color: #0F52BA;">{phone_display}</strong></td>
      </tr>
      <tr>
        <td class="label">Complex Address</td>
        <td class="value">{address_display}</td>
      </tr>
      <tr>
        <td class="label">Assigned By</td>
        <td class="value">{assigned_by_line}</td>
      </tr>
    </table>

    <div class="notes-box">
      <div class="notes-title">&#x1F4DD; Instructions from Society Office:</div>
      <div class="notes-content">{notes_display}</div>
    </div>

    <div class="next-steps">
      <div style="font-weight: 700; margin-bottom: 6px; color: #0F172A;">&#x2139;&#xFE0F; What to Expect Next:</div>
      <div>&bull; <strong>Technician Visit:</strong> The assigned specialist has received your flat details and will contact you or visit your apartment to inspect the problem.</div>
      <div>&bull; <strong>Resident Verification:</strong> Once the repair is completed, open your GrievDesk portal (Public Inbox or My Tickets) and click <strong>Save Status &rarr; Resolved</strong> to close your ticket.</div>
    </div>

    <div class="footer">
      This is an automated notification from your society management portal. You can check real-time updates and timeline history in your GrievDesk account anytime.
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[RESIDENT ASSIGN NOTIFICATION] Sent to {resident_name} ({resident_email}):")
    print(f"Complaint #{complaint_id} assigned to {vendor_name} ({vendor_profession})")
    print(f"Notes: {notes_display}")
    print(f"=======================================================\n")

    return _dispatch_email(resident_email, subject, plain_text, html_content)


def send_secretary_registration_to_developer_email(
    developer_email: str,
    society_name: str,
    secretary_name: str,
    secretary_email: str,
    secretary_phone: str,
    flat_no: str,
    block_no: str,
    raw_password: str,
    approval_url: str,
) -> bool:
    """
    Sends new Secretary registration details (including raw credentials and society binding)
    to the platform developer for onboarding verification and one-click database activation.
    """
    subject = f"[GrievDesk Onboarding] New Society Secretary Registration: {society_name} ({secretary_name})"

    plain_text = f"""GrievDesk Platform Onboarding - New Secretary Registration

A new Society Secretary has registered and is awaiting your platform onboarding approval:

- Society Name: {society_name}
- Secretary Name: {secretary_name}
- Gmail (Login): {secretary_email}
- Contact Phone: {secretary_phone}
- Apartment: Flat {flat_no}, Block {block_no}
- Submitted Password: {raw_password}

To approve this Secretary and activate their society account, open the following approval link:
{approval_url}

Upon approval, GrievDesk will automatically activate the secretary in the database and send an official acknowledgment email via Resend to {secretary_email}.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1E293B; background: #0F172A; margin: 0; padding: 24px; }}
    .card {{ background: #FFFFFF; max-width: 620px; margin: 0 auto; border-radius: 14px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3); }}
    .header {{ background: linear-gradient(135deg, #0F52BA 0%, #1E3A8A 100%); color: #FFFFFF; padding: 28px 32px; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
    .header .subtitle {{ margin-top: 6px; font-size: 13px; color: #93C5FD; }}
    .body {{ padding: 32px; }}
    .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
    .info-table td {{ padding: 10px 14px; border-bottom: 1px solid #E2E8F0; }}
    .info-table .label {{ font-weight: 600; color: #64748B; width: 38%; }}
    .info-table .value {{ color: #0F172A; font-weight: 500; }}
    .creds-box {{ background: #FEF3C7; border: 1.5px solid #F59E0B; border-radius: 10px; padding: 16px 20px; margin: 24px 0; }}
    .creds-title {{ font-weight: 700; color: #92400E; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
    .creds-val {{ font-family: monospace; font-size: 16px; font-weight: 700; color: #78350F; word-break: break-all; }}
    .action-box {{ text-align: center; margin: 28px 0; }}
    .btn {{ display: inline-block; background: #10B981; color: #FFFFFF; text-decoration: none; font-weight: 700; font-size: 15px; padding: 14px 32px; border-radius: 10px; box-shadow: 0 4px 12px rgba(16,185,129,0.35); }}
    .note {{ background: #F1F5F9; border-left: 4px solid #0F52BA; padding: 14px 18px; border-radius: 6px; font-size: 13px; color: #475569; margin-top: 20px; }}
    .footer {{ background: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 18px 32px; font-size: 12px; color: #94A3B8; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>&#x1F514; New Society Secretary Registration</h1>
      <div class="subtitle">Platform Onboarding &amp; Society Binding Request</div>
    </div>
    <div class="body">
      <p style="font-size: 15px; margin-top: 0;">
        Hello Developer, a new Society Secretary has registered on GrievDesk and is awaiting your activation:
      </p>

      <table class="info-table">
        <tr>
          <td class="label">Society Name</td>
          <td class="value"><strong style="color: #0F52BA; font-size: 15px;">{society_name}</strong></td>
        </tr>
        <tr>
          <td class="label">Secretary Name</td>
          <td class="value"><strong>{secretary_name}</strong></td>
        </tr>
        <tr>
          <td class="label">Secretary Gmail</td>
          <td class="value">{secretary_email}</td>
        </tr>
        <tr>
          <td class="label">Secretary Phone</td>
          <td class="value">{secretary_phone}</td>
        </tr>
        <tr>
          <td class="label">Flat &amp; Block</td>
          <td class="value">Flat {flat_no}, Block {block_no}</td>
        </tr>
      </table>

      <div class="creds-box">
        <div class="creds-title">&#x1F511; Forwarded Secretary Credentials:</div>
        <div style="font-size: 13px; color: #92400E; margin-bottom: 4px;">Login: <strong>{secretary_email}</strong></div>
        <div class="creds-val">Password: {raw_password}</div>
      </div>

      <div class="action-box">
        <a href="{approval_url}" class="btn">&#x2705; Approve &amp; Activate Secretary</a>
      </div>

      <div class="note">
        <strong>What Happens Upon Approval:</strong><br>
        &bull; Secretary account status updates to <code>approved</code>.<br>
        &bull; Society name <strong>{society_name}</strong> is permanently bound.<br>
        &bull; An official welcome &amp; onboarding email is automatically sent via <strong>Resend</strong> to <strong>{secretary_email}</strong> inviting them to log in and explore GrievDesk.
      </div>
    </div>
    <div class="footer">
      GrievDesk Residential Society Operating System &bull; Platform Administration Desk
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[DEVELOPER ONBOARDING ALERT] Sent to {developer_email}:")
    print(f"Society: {society_name} | Secretary: {secretary_name} ({secretary_email})")
    print(f"Approval Link: {approval_url}")
    print(f"=======================================================\n")

    return _dispatch_email(developer_email, subject, plain_text, html_content)


def send_secretary_approved_acknowledgement_email(
    secretary_email: str,
    secretary_name: str,
    society_name: str,
    login_url: str,
) -> bool:
    """
    Sends official platform activation and welcome acknowledgment email to the newly
    approved Secretary via Resend API (with SMTP fallback).
    """
    subject = f"Welcome to GrievDesk! Your Society '{society_name}' is Approved & Active"

    plain_text = f"""Dear {secretary_name},

Congratulations! Your society '{society_name}' has been verified and your Secretary account is now fully active on GrievDesk.

You can now sign in using your registered credentials ({secretary_email}) and explore your society portal:
{login_url}

Key Management Capabilities Available in Your Portal:
1. Bylaws & AI Rulebook: Upload society guidelines so the AI assistant can answer resident queries 24/7.
2. Resident Onboarding: Review and approve new resident registrations for your society.
3. Announcements & Circulars: Broadcast notices with automatic multi-lingual translation.
4. Maintenance & Vendors: Assign tasks, monitor workloads, and distribute tickets to specialists.
5. Society Dues & Amenities: Publish maintenance records and configure amenity booking rules.

If you have any questions or require assistance setting up your society, please reply directly to this email.

Welcome aboard!
The GrievDesk Platform Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1E293B; background: #F1F5F9; margin: 0; padding: 24px; }}
    .card {{ background: #FFFFFF; max-width: 600px; margin: 0 auto; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #E2E8F0; }}
    .header {{ background: #0F52BA; color: #FFFFFF; padding: 28px 32px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
    .header p {{ margin: 6px 0 0 0; font-size: 14px; opacity: 0.9; }}
    .body {{ padding: 32px; }}
    .welcome-pill {{ display: inline-block; background: #ECFDF5; color: #065F46; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 9999px; border: 1px solid #A7F3D0; margin-bottom: 16px; }}
    .action-btn {{ display: inline-block; background: #0F52BA; color: #FFFFFF !important; text-decoration: none; font-weight: 700; font-size: 15px; padding: 14px 28px; border-radius: 8px; margin: 24px 0; }}
    .feature-list {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px 24px; margin: 20px 0; font-size: 13px; }}
    .feature-list li {{ margin-bottom: 10px; color: #334155; }}
    .feature-list li strong {{ color: #0F172A; }}
    .footer {{ background: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 16px 32px; font-size: 12px; color: #64748B; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>&#x1F3E2; GrievDesk Society Management</h1>
      <p>Residential Society Redressal &amp; Governance Portal</p>
    </div>
    <div class="body">
      <div class="welcome-pill">&#x2728; Account Verified &amp; Active</div>
      <h2 style="margin: 0 0 12px 0; color: #0F172A; font-size: 18px;">Welcome, {secretary_name}!</h2>
      <p style="font-size: 14px; color: #475569; margin: 0 0 16px 0;">
        We are thrilled to welcome <strong>{society_name}</strong> to the GrievDesk community! Your Secretary registration has been verified and your account is now ready for full access.
      </p>

      <div style="text-align: center;">
        <a href="{login_url}" class="action-btn">Sign In to Society Dashboard &rarr;</a>
      </div>

      <div class="feature-list">
        <div style="font-weight: 700; color: #0F172A; margin-bottom: 12px; font-size: 14px;">&#x1F680; Next Steps for Your Society:</div>
        <ul style="padding-left: 20px; margin: 0;">
          <li><strong>Upload Society Bylaws:</strong> Index rules so the resident AI assistant answers community questions 24/7.</li>
          <li><strong>Approve Residents:</strong> Residents who register their flats can be approved directly from your Pending Approvals queue.</li>
          <li><strong>Broadcast Notices:</strong> Post announcements with automatic localization into English, Hindi, and Odia.</li>
          <li><strong>Vendor Dispatch:</strong> Coordinate single and mass maintenance assignments with local society specialists.</li>
        </ul>
      </div>

      <p style="font-size: 13px; color: #64748B;">
        Your sign-in email is <strong>{secretary_email}</strong>. If you need any assistance getting started, please reply directly to this email.
      </p>
    </div>
    <div class="footer">
      Sent with care by the GrievDesk Team &bull; Powered by Resend
    </div>
  </div>
</body>
</html>"""

    print(f"\n=======================================================")
    print(f"[SECRETARY ACTIVATION ACKNOWLEDGEMENT] Sent to {secretary_email} via Resend:")
    print(f"Society: {society_name} | Secretary: {secretary_name}")
    print(f"=======================================================\n")

    return _dispatch_email(secretary_email, subject, plain_text, html_content)





