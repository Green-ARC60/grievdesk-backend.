import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, decode_token
from email_validator import validate_email, EmailNotValidError

from app.extensions import db
from app.models.user import User, Role, ApprovalStatus
from app.models.password_reset_otp import PasswordResetOTP
from app.services.email import send_password_reset_otp_email, send_registration_received_email

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

REQUIRED_FIELDS = [
    "role", "name", "phone", "flat_no", "block_no",
    "gmail", "preferred_language", "password",
]


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    if not isinstance(data["password"], str) or len(data["password"]) < 8:
        return jsonify({"error": "weak_password", "message": "Password must be at least 8 characters."}), 400

    requested_role = data["role"].strip().lower()
    if requested_role not in ("resident", "admin"):
        return jsonify({"error": "invalid_role", "message": "role must be 'resident' or 'admin'."}), 400

    try:
        validate_email(data["gmail"], check_deliverability=False)
    except EmailNotValidError:
        return jsonify({"error": "invalid_email"}), 400

    if User.query.filter_by(gmail=data["gmail"]).first():
        return jsonify({"error": "email_already_registered"}), 409

    if requested_role == "admin":
        # Only one Secretary may exist for this single society. Enforced here
        # AND at the DB level via the partial unique index on User.role.
        existing_secretary = User.query.filter_by(role=Role.SECRETARY).first()
        if existing_secretary:
            return jsonify({
                "error": "secretary_already_exists",
                "message": "An admin (Secretary) is already registered for this society.",
            }), 409

        new_user = User(
            name=data["name"],
            phone=data["phone"],
            gmail=data["gmail"],
            flat_no=data["flat_no"],
            block_no=data["block_no"],
            preferred_language=data["preferred_language"],
            role=Role.SECRETARY,
            approval_status=ApprovalStatus.APPROVED,  # first-ever Secretary is auto-approved
        )
    else:
        new_user = User(
            name=data["name"],
            phone=data["phone"],
            gmail=data["gmail"],
            flat_no=data["flat_no"],
            block_no=data["block_no"],
            preferred_language=data["preferred_language"],
            role=Role.RESIDENT,
            approval_status=ApprovalStatus.PENDING,  # needs Secretary approval before login works
        )

    new_user.set_password(data["password"])

    db.session.add(new_user)
    db.session.commit()

    if new_user.role == Role.RESIDENT:
        send_registration_received_email(
            to_email=new_user.gmail,
            recipient_name=new_user.name,
            flat_no=new_user.flat_no,
            block_no=new_user.block_no
        )

    message = (
        "Registered as Secretary."
        if new_user.role == Role.SECRETARY
        else "Registered. Your account is pending Secretary approval before you can log in."
    )
    return jsonify({"message": message, "user": new_user.to_public_dict()}), 201


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

