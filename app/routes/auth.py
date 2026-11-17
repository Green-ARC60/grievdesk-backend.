import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, current_app, render_template_string
from flask_jwt_extended import create_access_token, decode_token
from email_validator import validate_email, EmailNotValidError

from app.extensions import db
from app.models.society import Society
from app.models.user import User, Role, ApprovalStatus
from app.models.password_reset_otp import PasswordResetOTP
from app.models.society_settings import SocietySettings
from app.services.email import (
    send_password_reset_otp_email,
    send_registration_received_email,
    send_secretary_registration_to_developer_email,
    send_secretary_approved_acknowledgement_email,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

REQUIRED_FIELDS = [
    "role", "name", "phone", "flat_no", "block_no",
    "gmail", "preferred_language", "password", "society_name",
]


@auth_bp.get("/societies")
def list_societies():
    """
    List all approved active societies for the registration dropdown/selector.
    """
    q = (request.args.get("q") or "").strip().lower()
    query = Society.query.filter_by(status="approved")
    if q:
        query = query.filter(Society.name.ilike(f"%{q}%"))
    societies = query.order_by(Society.name.asc()).all()
    return jsonify({
        "societies": [
            {
                "id": s.id,
                "name": s.name,
                "society_name": s.name,
                "secretary_name": s.secretary_name or "Assigned",
                "status": s.status,
            }
            for s in societies
        ]
    }), 200


@auth_bp.get("/verify-society")
def verify_society():
    """
    Real-time verification of society name during registration.
    Checks whether the society exists in the database and whether it already has an assigned Secretary.
    """
    query = (request.args.get("name") or "").strip()
    if not query:
        return jsonify({"error": "missing_name", "message": "Provide society name to verify"}), 400

    soc = Society.query.filter(db.func.lower(Society.name) == query.lower()).first()
    if not soc:
        soc = Society.query.filter(Society.name.ilike(f"%{query}%")).first()

    if soc:
        sec = User.query.filter_by(society_id=soc.id, role=Role.SECRETARY).first()
        has_sec = sec is not None
        sec_name = sec.name if sec else (soc.secretary_name or None)
        return jsonify({
            "exists": True,
            "society_id": soc.id,
            "society_name": soc.name,
            "has_secretary": has_sec,
            "secretary_name": sec_name,
            "secretary_status": sec.approval_status if sec else None,
            "society_status": soc.status,
        }), 200

    return jsonify({
        "exists": False,
        "society_name": query,
        "has_secretary": False,
        "secretary_name": None,
    }), 200


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    if not isinstance(data["password"], str) or len(data["password"]) < 8:
        return jsonify({"error": "weak_password", "message": "Password must be at least 8 characters."}), 400

    requested_role = data["role"].strip().lower()
    if requested_role not in ("resident", "admin", "committee"):
        return jsonify({"error": "invalid_role", "message": "role must be 'resident', 'committee', or 'admin'."}), 400

    try:
        validate_email(data["gmail"], check_deliverability=False)
    except EmailNotValidError:
        return jsonify({"error": "invalid_email"}), 400

    if User.query.filter_by(gmail=data["gmail"].strip().lower()).first():
        return jsonify({"error": "email_already_registered"}), 409

    soc_name = data["society_name"].strip()
    is_new_society = bool(data.get("is_new_society"))

    # Case 1: Registering a brand-new society ecosystem
    if is_new_society or (requested_role == "admin" and not data.get("society_id")):
        # If user explicitly registered for a new society or chose admin for a society name that doesn't exist
        existing_soc = Society.query.filter(db.func.lower(Society.name) == soc_name.lower()).first()
        if existing_soc:
            return jsonify({
                "error": "society_already_exists",
                "message": f"A society named '{existing_soc.name}' already exists. Please choose a unique society name or join as a resident.",
            }), 409

        new_soc = Society(
            name=soc_name,
            secretary_name=data["name"].strip(),
            status="pending",  # Requires Developer Onboarding Approval
        )
        db.session.add(new_soc)
        db.session.flush()

        new_user = User(
            society_id=new_soc.id,
            name=data["name"].strip(),
            phone=data["phone"].strip(),
            alt_phone=(data.get("alt_phone") or "").strip() or None,
            gmail=data["gmail"].strip().lower(),
            flat_no=data.get("flat_no", "Sec-Office").strip(),
            block_no=data.get("block_no", "Main").strip(),
            preferred_language=data.get("preferred_language", "en"),
            role=Role.SECRETARY,
            approval_status=ApprovalStatus.PENDING,  # Secretary requires Developer onboarding approval!
        )
        new_user.set_password(data["password"])
        db.session.add(new_user)
        db.session.commit()

        # Build developer approval URL with secure HMAC token
        dev_secret = current_app.config.get("DEVELOPER_APPROVAL_SECRET", "grievdesk-dev-master-approval-key-2026")
        dev_email = current_app.config.get("DEVELOPER_EMAIL", "ayushcharchi7@gmail.com")
        token_src = f"approve:{new_user.id}:{new_user.gmail}"
        approval_token = hmac.new(dev_secret.encode(), token_src.encode(), hashlib.sha256).hexdigest()
        backend_url = current_app.config.get("BACKEND_URL", "http://127.0.0.1:5000")
        approval_url = f"{backend_url}/api/auth/developer/approve-secretary?email={new_user.gmail}&token={approval_token}"

        # Build Mobile-friendly LAN URL (e.g. for approving from phone on the same Wi-Fi)
        mobile_approval_url = None
        try:
            import socket
            lan_ips = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")]
            if lan_ips:
                mobile_approval_url = f"http://{lan_ips[0]}:5000/api/auth/developer/approve-secretary?email={new_user.gmail}&token={approval_token}"
        except Exception:
            pass

        # Forward full credentials & password to developer mail for verification
        send_secretary_registration_to_developer_email(
            developer_email=dev_email,
            society_name=new_soc.name,
            secretary_name=new_user.name,
            secretary_email=new_user.gmail,
            secretary_phone=new_user.phone,
            flat_no=new_user.flat_no,
            block_no=new_user.block_no,
            raw_password=data["password"],
            approval_url=approval_url,
            mobile_approval_url=mobile_approval_url,
        )

        message = (
            f"Registered as Founding Secretary for '{new_soc.name}'. Your society ecosystem and account are pending Developer onboarding approval. "
            "Your registration details have been forwarded to the platform developer."
        )
        return jsonify({"message": message, "user": new_user.to_public_dict()}), 201

    # Case 2: Joining an existing society as resident / committee
    soc = None
    if data.get("society_id"):
        soc = db.session.get(Society, data["society_id"])
    elif soc_name:
        soc = Society.query.filter(db.func.lower(Society.name) == soc_name.lower()).first()

    if not soc:
        return jsonify({
            "error": "society_not_found",
            "message": f"Society '{soc_name}' was not found. Please choose an existing society or create a new society ecosystem.",
        }), 404

    if soc.status != "approved":
        return jsonify({
            "error": "society_pending",
            "message": f"Society '{soc.name}' is currently pending developer onboarding approval.",
        }), 400

    if requested_role == "admin":
        existing_secretary = User.query.filter_by(society_id=soc.id, role=Role.SECRETARY).first()
        if existing_secretary:
            return jsonify({
                "error": "secretary_already_exists",
                "message": f"A Secretary ({existing_secretary.name}) is already assigned for '{soc.name}'.",
            }), 409
        role_to_assign = Role.SECRETARY
        status_to_assign = ApprovalStatus.PENDING
    elif requested_role == "committee":
        role_to_assign = Role.COMMITTEE
        status_to_assign = ApprovalStatus.PENDING
    else:
        role_to_assign = Role.RESIDENT
        status_to_assign = ApprovalStatus.PENDING

    new_user = User(
        society_id=soc.id,
        name=data["name"].strip(),
        phone=data["phone"].strip(),
        alt_phone=(data.get("alt_phone") or "").strip() or None,
        gmail=data["gmail"].strip().lower(),
        flat_no=data["flat_no"].strip(),
        block_no=data["block_no"].strip(),
        preferred_language=data["preferred_language"],
        role=role_to_assign,
        approval_status=status_to_assign,  # needs Secretary approval before login works
    )
    new_user.set_password(data["password"])
    db.session.add(new_user)
    db.session.commit()

    send_registration_received_email(
        to_email=new_user.gmail,
        recipient_name=new_user.name,
        flat_no=new_user.flat_no,
        block_no=new_user.block_no
    )

    message = f"Registered for '{soc.name}'. Your account is pending Secretary approval before you can log in."
    return jsonify({"message": message, "user": new_user.to_public_dict()}), 201


@auth_bp.route("/developer/approve-secretary", methods=["GET", "POST"])
def developer_approve_secretary():
    """
    Developer only: Approve and activate a pending Secretary account.
    Works via GET (clickable link in developer email) and POST (API call).
    Upon approval, sends an official acknowledgment email to the Secretary via Resend.
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or request.args.get("email") or "").strip().lower()
        token = payload.get("token") or request.args.get("token") or ""
        secret = payload.get("secret") or ""
    else:
        email = (request.args.get("email") or "").strip().lower()
        token = request.args.get("token") or ""
        secret = request.args.get("secret") or ""

    if not email:
        return jsonify({"error": "missing_email", "message": "Secretary email is required"}), 400

    user = User.query.filter_by(gmail=email, role=Role.SECRETARY).first()
    if not user:
        return jsonify({"error": "not_found", "message": f"No Secretary found with email {email}"}), 404

    dev_secret = current_app.config.get("DEVELOPER_APPROVAL_SECRET", "grievdesk-dev-master-approval-key-2026")
    token_src = f"approve:{user.id}:{user.gmail}"
    expected_token = hmac.new(dev_secret.encode(), token_src.encode(), hashlib.sha256).hexdigest()

    is_valid = (token and hmac.compare_digest(token, expected_token)) or (secret and hmac.compare_digest(secret, dev_secret))
    if not is_valid:
        return jsonify({"error": "unauthorized", "message": "Invalid developer approval token or secret."}), 403

    from app.models.society_settings import SocietySettings
    settings = SocietySettings.get_settings()

    user.approval_status = ApprovalStatus.APPROVED
    if user.society:
        user.society.status = "approved"
        user.society.secretary_name = user.name
    if settings:
        settings.secretary_name = user.name
        settings.updated_by = user.id
    db.session.commit()

    soc_name = user.society.name if user.society else (settings.society_name if settings else "Society")
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
    login_url = f"{frontend_url}/login"

    # Send official acknowledgment email via Resend to the Secretary
    send_secretary_approved_acknowledgement_email(
        secretary_email=user.gmail,
        secretary_name=user.name,
        society_name=soc_name,
        login_url=login_url,
    )

    if request.method == "GET":
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Secretary Approved - GrievDesk</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0F172A; color: #F8FAFC; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
    .card {{ background: #1E293B; border: 1.5px solid #334155; border-radius: 16px; padding: 36px; max-width: 520px; width: 100%; text-align: center; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
    .badge {{ background: #065F46; color: #34D399; font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 9999px; display: inline-block; margin-bottom: 20px; border: 1px solid #059669; }}
    h1 {{ font-size: 24px; margin: 0 0 10px 0; color: #FFFFFF; }}
    p {{ color: #94A3B8; font-size: 14px; line-height: 1.6; margin: 0 0 24px 0; }}
    .details {{ background: #0F172A; border-radius: 10px; padding: 16px; margin: 20px 0; text-align: left; font-size: 13px; border: 1px solid #334155; }}
    .details div {{ margin-bottom: 6px; }}
    .details strong {{ color: #E2E8F0; }}
    .btn {{ display: inline-block; background: #0F52BA; color: #FFFFFF; font-weight: 700; font-size: 14px; padding: 12px 28px; border-radius: 8px; text-decoration: none; transition: background 0.2s; }}
    .btn:hover {{ background: #1D4ED8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">&#x2713; Developer Approval Successful</div>
    <h1>Secretary Activated!</h1>
    <p>
      The Secretary account for <strong>{user.name}</strong> at <strong>{soc_name}</strong> is now approved and fully active in the database.
    </p>
    <div class="details">
      <div><strong>Society:</strong> {soc_name}</div>
      <div><strong>Secretary:</strong> {user.name}</div>
      <div><strong>Gmail:</strong> {user.gmail}</div>
      <div><strong>Phone:</strong> {user.phone}</div>
      <div><strong>Status:</strong> <span style="color: #34D399; font-weight: 700;">Approved</span></div>
    </div>
    <p style="font-size: 13px; color: #38BDF8;">
      &#x2709;&#xFE0F; An official welcome &amp; acknowledgment email has been delivered to <strong>{user.gmail}</strong> via Resend.
    </p>
    <a href="{login_url}" class="btn">Go to GrievDesk Portal</a>
  </div>
</body>
</html>"""
        return render_template_string(html), 200

    return jsonify({
        "message": f"Secretary {user.name} approved successfully for {soc_name}. Acknowledgment email sent via Resend.",
        "user": user.to_public_dict(),
    }), 200


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    gmail = data.get("gmail")
    password = data.get("password")

    if not gmail or not password:
        return jsonify({"error": "missing_fields", "fields": ["gmail", "password"]}), 400

    user = User.query.filter_by(gmail=gmail).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid_credentials"}), 401

    if user.approval_status != ApprovalStatus.APPROVED:
        if user.role == Role.SECRETARY:
            return jsonify({
                "error": "pending_developer_approval",
                "message": "Your Secretary registration is awaiting Developer onboarding verification. You will receive an email as soon as your account is activated.",
            }), 403
        return jsonify({"error": "pending_approval", "message": "Your account is awaiting Secretary approval."}), 403

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )
    return jsonify({"access_token": access_token, "user": user.to_public_dict()}), 200


@auth_bp.post("/forgot-password/send-otp")
def send_forgot_password_otp():
    """
    Step 1: User enters registered Gmail. Generates a 6-digit OTP,
    sends acknowledgment email, and stores in database with 10-min expiry.
    """
    data = request.get_json(silent=True) or {}
    gmail = (data.get("gmail") or "").strip().lower()

    if not gmail:
        return jsonify({"error": "missing_gmail", "message": "Please enter your Gmail address."}), 400

    user = User.query.filter(db.func.lower(User.gmail) == gmail).first()
    if not user:
        return jsonify({"error": "user_not_found", "message": "No resident or staff account found with this Gmail address."}), 404

    # Generate 6-digit secure numeric OTP (e.g. 100000 - 999999)
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    # Invalidate previous unused OTPs for this user
    PasswordResetOTP.query.filter_by(user_id=user.id, is_used=False).update({"is_used": True})

    otp_record = PasswordResetOTP(
        user_id=user.id,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False
    )
    db.session.add(otp_record)
    db.session.commit()

    # Send acknowledgment email with OTP
    send_password_reset_otp_email(to_email=user.gmail, recipient_name=user.name, otp_code=otp_code)

    return jsonify({
        "message": f"A 6-digit verification code has been sent to {user.gmail}.",
        "gmail": user.gmail
    }), 200


@auth_bp.post("/forgot-password/verify-otp")
def verify_forgot_password_otp():
    """
    Step 2: User submits Gmail and the 6-digit OTP.
    If valid and unexpired, returns a 15-minute reset_token.
    """
    data = request.get_json(silent=True) or {}
    gmail = (data.get("gmail") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    if not gmail or not otp:
        return jsonify({"error": "missing_fields", "message": "Gmail and verification code are required."}), 400

    user = User.query.filter(db.func.lower(User.gmail) == gmail).first()
    if not user:
        return jsonify({"error": "user_not_found", "message": "User not found."}), 404

    otp_record = PasswordResetOTP.query.filter_by(
        user_id=user.id,
        is_used=False
    ).order_by(PasswordResetOTP.created_at.desc()).first()

    if not otp_record or not otp_record.is_valid(otp):
        return jsonify({
            "error": "invalid_or_expired_otp",
            "message": "Invalid or expired verification code. Please check your email or request a new code."
        }), 400

    # Mark OTP as consumed
    otp_record.is_used = True
    db.session.commit()

    # Issue temporary 15-minute reset token
    reset_token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(minutes=15),
        additional_claims={"purpose": "password_reset"}
    )

    return jsonify({
        "message": "Verification code confirmed successfully.",
        "reset_token": reset_token
    }), 200


@auth_bp.post("/forgot-password/reset-password")
def reset_forgotten_password():
    """
    Step 3: User submits reset_token and new password.
    Validates token and updates user password_hash in DB.
    """
    data = request.get_json(silent=True) or {}
    reset_token = data.get("reset_token")
    new_password = data.get("new_password")

    if not reset_token or not new_password:
        return jsonify({"error": "missing_fields", "message": "Reset token and new password are required."}), 400

    if not isinstance(new_password, str) or len(new_password) < 8:
        return jsonify({"error": "weak_password", "message": "Password must be at least 8 characters long."}), 400

    try:
        claims = decode_token(reset_token)
    except Exception as e:
        return jsonify({"error": "invalid_token", "message": "Reset session expired or invalid. Please request a new code."}), 400

    if claims.get("purpose") != "password_reset":
        return jsonify({"error": "unauthorized_token", "message": "Invalid token purpose."}), 403

    user_id = int(claims["sub"])
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "user_not_found", "message": "User account no longer exists."}), 404

    user.set_password(new_password)
    db.session.commit()

    return jsonify({
        "message": "Password successfully reset! You can now log in with your new password."
    }), 200

