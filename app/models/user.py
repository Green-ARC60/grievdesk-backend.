from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Role:
    RESIDENT = "resident"
    COMMITTEE = "committee"
    SECRETARY = "secretary"
    ALL = (RESIDENT, COMMITTEE, SECRETARY)


class ApprovalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    ALL = (PENDING, APPROVED)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    alt_phone = db.Column(db.String(20), nullable=True)
    gmail = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    flat_no = db.Column(db.String(20), nullable=False)
    block_no = db.Column(db.String(20), nullable=False)
    preferred_language = db.Column(db.String(10), nullable=False)  # single-select, e.g. 'en', 'or', 'hi'

    role = db.Column(db.String(20), nullable=False, default=Role.RESIDENT)
    approval_status = db.Column(db.String(20), nullable=False, default=ApprovalStatus.PENDING)
    share_phone = db.Column(db.Boolean, nullable=False, default=False)
    society_id = db.Column(db.Integer, db.ForeignKey("societies.id"), nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Enforces only one Secretary per society
        db.Index(
            "uq_society_secretary",
            "society_id",
            unique=True,
            postgresql_where=(role == Role.SECRETARY),
        ),
    )

    # ---- Password helpers ----
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # ---- Role helpers (used by route decorators later) ----
    def is_secretary(self) -> bool:
        return self.role == Role.SECRETARY

    def is_committee_or_above(self) -> bool:
        return self.role in (Role.COMMITTEE, Role.SECRETARY)

    def is_staff(self) -> bool:
        return self.role in (Role.COMMITTEE, Role.SECRETARY)

    def to_directory_dict(self, viewer) -> dict:
        """
        Resident Directory row. Everyone sees name + flat + block + role; a phone number only if its
        owner chose to share it. Committee/secretary (the viewer) see full contact details.
        """
        staff_view = viewer is not None and viewer.is_staff()
        row = {
            "id": self.id,
            "name": self.name,
            "flat_no": self.flat_no,
            "block_no": self.block_no,
            "role": self.role,
            "phone": self.phone if (self.share_phone or staff_view) else None,
            "alt_phone": self.alt_phone if (self.share_phone or staff_view) else None,
            "alt_phones": [self.alt_phone] if (self.alt_phone and (self.share_phone or staff_view)) else [],
        }
        if staff_view or (viewer is not None and viewer.id == self.id):
            row["gmail"] = self.gmail
            row["preferred_language"] = self.preferred_language
            row["approval_status"] = self.approval_status
        return row

    def to_profile_dict(self) -> dict:
        """The logged-in user's OWN profile — includes their phone even if they chose not to share it, plus society info."""
        soc_name = self.society.name if self.society else "Greenwood Heights Society"
        sec_name = self.society.secretary_name if self.society else "Ramesh Patel"
        return {
            "id": self.id, "name": self.name, "phone": self.phone, "alt_phone": self.alt_phone,
            "gmail": self.gmail, "flat_no": self.flat_no, "block_no": self.block_no,
            "preferred_language": self.preferred_language, "share_phone": self.share_phone,
            "role": self.role, "approval_status": self.approval_status,
            "society_id": self.society_id,
            "society_name": soc_name,
            "secretary_name": sec_name,
        }

    def to_public_dict(self) -> dict:
        """Safe shape for API responses — never includes password_hash."""
        soc_name = self.society.name if self.society else "Greenwood Heights Society"
        sec_name = self.society.secretary_name if self.society else "Ramesh Patel"
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone if self.share_phone else None,
            "alt_phone": self.alt_phone if self.share_phone else None,
            "gmail": self.gmail,
            "flat_no": self.flat_no,
            "block_no": self.block_no,
            "preferred_language": self.preferred_language,
            "role": self.role,
            "approval_status": self.approval_status,
            "society_id": self.society_id,
            "society_name": soc_name,
            "secretary_name": sec_name,
        }
