from datetime import datetime, timezone
from app.extensions import db


class PasswordResetOTP(db.Model):
    __tablename__ = "password_reset_otps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    otp_code = db.Column(db.String(10), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("password_reset_otps", lazy="dynamic", cascade="all, delete-orphan"))

    def is_valid(self, code: str) -> bool:
        if self.is_used:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return self.otp_code.strip() == code.strip()

