from datetime import datetime, timezone
from app.extensions import db


class VendorProfession:
    PLUMBER = "Plumber"
    ELECTRICIAN = "Electrician"
    LINE_ELECTRICIAN = "Line Electrician (Society Mains)"
    AC_REPAIR = "AC Repairer"
    ELECTRONICS_REPAIR = "Electronics Repairer"
    BARBER = "Barber"
    SECURITY_GUARD = "Security Guard"
    WATER_TANK = "Water Tank Supplier"
    GROCERY_SHOP = "Grocery Shop (Society Complex)"
    OTHER_SHOP = "Complex Shop / Retail"
    OTHER = "Other Helper / Vendor"

    ALL = (
        PLUMBER,
        ELECTRICIAN,
        LINE_ELECTRICIAN,
        AC_REPAIR,
        ELECTRONICS_REPAIR,
        BARBER,
        SECURITY_GUARD,
        WATER_TANK,
        GROCERY_SHOP,
        OTHER_SHOP,
        OTHER,
    )


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(db.Integer, db.ForeignKey("societies.id"), nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    profession = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tasks = db.relationship("VendorTask", back_populates="vendor", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self, include_tasks=False) -> dict:
        assigned_tasks_count = self.tasks.count()
        data = {
            "id": self.id,
            "name": self.name,
            "profession": self.profession,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "notes": self.notes,
            "tasks_count": assigned_tasks_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_tasks:
            data["tasks"] = [task.to_dict() for task in self.tasks.order_by(VendorTask.created_at.desc()).all()]
        return data


class VendorTask(db.Model):
    __tablename__ = "vendor_tasks"

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # written note or voice note transcription in local language
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    vendor = db.relationship("Vendor", back_populates="tasks")
    complaint = db.relationship("Complaint", foreign_keys=[complaint_id])
    assigner = db.relationship("User", foreign_keys=[assigned_by])

    __table_args__ = (
        db.Index("ix_vendor_tasks_vendor_id", "vendor_id"),
        db.Index("ix_vendor_tasks_complaint_id", "complaint_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "complaint_id": self.complaint_id,
            "notes": self.notes,
            "status": self.status,
            "assigned_by": self.assigner.name if self.assigner else "Unknown",
            "assigned_by_id": self.assigned_by,
            "complaint_summary": self.complaint.translated_text if self.complaint else None,
            "complaint_category": self.complaint.category if self.complaint else None,
            "complaint_status": self.complaint.status if self.complaint else None,
            "flat_no": self.complaint.user.flat_no if (self.complaint and self.complaint.user) else None,
            "block_no": self.complaint.user.block_no if (self.complaint and self.complaint.user) else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
