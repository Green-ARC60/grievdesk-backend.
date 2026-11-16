from datetime import datetime, timezone
from app.extensions import db


class SocietySettings(db.Model):
    """
    Global settings for the residential society, including official society name
    and secretary title/name.
    """
    __tablename__ = "society_settings"

    id = db.Column(db.Integer, primary_key=True, default=1)
    society_name = db.Column(db.String(255), nullable=False, default="GrievDesk Residency")
    secretary_name = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    @classmethod
    def get_settings(cls):
        """Retrieve the singleton society settings row, creating it if absent."""
        row = cls.query.filter_by(id=1).first()
        if not row:
            from app.models.user import User, Role
            sec = User.query.filter_by(role=Role.SECRETARY).first()
            sec_name = sec.name if sec else "Ramesh Patel"
            row = cls(id=1, society_name="GrievDesk Residency", secretary_name=sec_name)
            db.session.add(row)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                row = cls.query.filter_by(id=1).first()
        return row

    def to_dict(self):
        sec_name = self.secretary_name
        if not sec_name:
            from app.models.user import User, Role
            sec = User.query.filter_by(role=Role.SECRETARY).first()
            if sec:
                sec_name = sec.name
        return {
            "society_name": self.society_name or "GrievDesk Residency",
            "secretary_name": sec_name or "Ramesh Patel",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
