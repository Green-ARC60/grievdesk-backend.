from datetime import datetime, timezone
from app.extensions import db


class Society(db.Model):
    """
    Independent residential society ecosystem.
    Every tenant/society has its own isolated complaints, announcements, vendors,
    bylaws, amenities, dues, and resident directory.
    """
    __tablename__ = "societies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    secretary_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="approved")  # "pending", "approved"
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    users = db.relationship("User", backref="society", lazy="dynamic", foreign_keys="User.society_id")
    complaints = db.relationship("Complaint", backref="society", lazy="dynamic", foreign_keys="Complaint.society_id")
    service_requests = db.relationship("ServiceRequest", backref="society", lazy="dynamic", foreign_keys="ServiceRequest.society_id")
    announcements = db.relationship("Announcement", backref="society", lazy="dynamic", foreign_keys="Announcement.society_id")
    dues = db.relationship("Due", backref="society", lazy="dynamic", foreign_keys="Due.society_id")
    amenities = db.relationship("Amenity", backref="society", lazy="dynamic", foreign_keys="Amenity.society_id")
    vendors = db.relationship("Vendor", backref="society", lazy="dynamic", foreign_keys="Vendor.society_id")
    bylaws = db.relationship("BylawsDocument", backref="society", lazy="dynamic", foreign_keys="BylawsDocument.society_id")

    def to_dict(self):
        sec_name = self.secretary_name
        if not sec_name:
            sec = self.users.filter_by(role="secretary").first()
            if sec:
                sec_name = sec.name
        return {
            "id": self.id,
            "name": self.name,
            "society_name": self.name,
            "secretary_name": sec_name or "Pending Secretary",
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
