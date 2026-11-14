from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.extensions import db
from app.utils.decorators import login_required, current_user
from app.models.vendor import Vendor, VendorProfession, VendorTask
from app.models.complaint import Complaint, ComplaintStatus
from app.models.ticket_event import TicketType, TicketAction
from app.services.complaint_status import set_complaint_status
from app.services.tickets import add_event
from app.services.email import send_vendor_task_assigned_email

vendors_bp = Blueprint("vendors", __name__, url_prefix="/api/vendors")


@vendors_bp.get("")
@login_required
def list_vendors():
    """
    List all society vendors/helpers.
    Permitted to all authenticated members (Residents, Committee, Secretary).
    Supports ?profession= and ?search=
    """
    query = Vendor.query

    profession = request.args.get("profession")
    if profession and profession.strip() and profession.lower() != "all":
        query = query.filter(Vendor.profession == profession.strip())

    search = request.args.get("search")
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Vendor.name.ilike(term),
                Vendor.profession.ilike(term),
                Vendor.phone.ilike(term),
                Vendor.email.ilike(term),
                Vendor.address.ilike(term),
            )
        )

    vendors = query.order_by(Vendor.name.asc()).all()
    return jsonify([v.to_dict() for v in vendors]), 200


@vendors_bp.get("/professions")
@login_required
def list_professions():
    """
    Returns list of standard helper/vendor professions.
    """
    return jsonify(list(VendorProfession.ALL)), 200


@vendors_bp.get("/<int:vendor_id>")
@login_required
def get_vendor(vendor_id):
    vendor = db.session.get(Vendor, vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404
    return jsonify(vendor.to_dict(include_tasks=True)), 200


@vendors_bp.post("")
@login_required
def create_vendor():
    """
    Add a new helper / vendor to the society roster.
    Permitted to society members.
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    profession = (data.get("profession") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    notes = (data.get("notes") or "").strip() or None

    if not name or not profession or not email or not phone or not address:
        return jsonify({
            "error": "Missing required fields",
            "message": "Name, profession, email, phone number, and address are required."
        }), 400

    vendor = Vendor(
        name=name,
        profession=profession,
        email=email,
        phone=phone,
        address=address,
        notes=notes,
    )
    db.session.add(vendor)
    db.session.commit()

    return jsonify({
        "message": "Vendor created successfully",
        "vendor": vendor.to_dict()
    }), 201


@vendors_bp.patch("/<int:vendor_id>")
@login_required
def update_vendor(vendor_id):
    """
    Edit vendor record.
    Permitted to society members as requested.
    """
    vendor = db.session.get(Vendor, vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data and str(data["name"]).strip():
        vendor.name = str(data["name"]).strip()
    if "profession" in data and str(data["profession"]).strip():
        vendor.profession = str(data["profession"]).strip()
    if "email" in data and str(data["email"]).strip():
        vendor.email = str(data["email"]).strip()
    if "phone" in data and str(data["phone"]).strip():
        vendor.phone = str(data["phone"]).strip()
    if "address" in data and str(data["address"]).strip():
        vendor.address = str(data["address"]).strip()
    if "notes" in data:
        vendor.notes = str(data["notes"]).strip() if data["notes"] else None

    db.session.commit()
    return jsonify({
        "message": "Vendor updated successfully",
        "vendor": vendor.to_dict()
    }), 200


@vendors_bp.delete("/<int:vendor_id>")
@login_required
def delete_vendor(vendor_id):
    vendor = db.session.get(Vendor, vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    db.session.delete(vendor)
    db.session.commit()
    return jsonify({"message": f"Vendor {vendor.name} deleted successfully"}), 200


@vendors_bp.post("/<int:vendor_id>/assign")
@login_required
def assign_vendor_task(vendor_id):
    """
    Assign a public inbox complaint to a vendor.
    1. Records the VendorTask.
    2. Automatically changes complaint status to 'in_progress' in Public Inbox.
    3. Adds a timeline TicketEvent.
    4. Sends a work order email carrying complaint details + local language note to the vendor via Resend/SMTP.
    """
    user = current_user()
    vendor = db.session.get(Vendor, vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    data = request.get_json(silent=True) or {}
    complaint_id = data.get("complaint_id")
    notes = (data.get("notes") or "").strip()

    if not complaint_id:
        return jsonify({"error": "complaint_id is required"}), 400

    complaint = db.session.get(Complaint, complaint_id)
    if not complaint:
        return jsonify({"error": "Complaint not found"}), 404

    # 1. Create the VendorTask
    task = VendorTask(
        vendor_id=vendor.id,
        complaint_id=complaint.id,
        assigned_by=user.id,
        notes=notes or None,
        status="in_progress"
    )
    db.session.add(task)

    # 2. Automatically update complaint status to in_progress if not already resolved
    old_status = complaint.status
    if complaint.status != ComplaintStatus.IN_PROGRESS:
        set_complaint_status(
            complaint=complaint,
            new_status=ComplaintStatus.IN_PROGRESS,
            actor=user,
            event_note=f"Assigned to vendor {vendor.name} ({vendor.profession})"
        )
    else:
        # Add assignment timeline event directly
        add_event(
            ticket_type=TicketType.COMPLAINT,
            ticket_id=complaint.id,
            action=TicketAction.ASSIGNED,
            detail=f"Vendor: {vendor.name} ({vendor.profession})",
            note=notes or f"Assigned to {vendor.name}",
            actor=user
        )

    db.session.commit()

    # 3. Dispatch email to vendor using Resend API / SMTP engine
    email_dispatched = False
    try:
        resident_name = complaint.user.name if complaint.user else "Resident Member"
        flat_no = complaint.user.flat_no if complaint.user else ""
        block_no = complaint.user.block_no if complaint.user else ""

        email_dispatched = send_vendor_task_assigned_email(
            vendor_email=vendor.email,
            vendor_name=vendor.name,
            vendor_profession=vendor.profession,
            complaint_id=complaint.id,
            category=complaint.category or "Maintenance",
            severity=complaint.severity or "Medium",
            description=complaint.translated_text or complaint.raw_text or "No description",
            flat_no=flat_no,
            block_no=block_no,
            resident_name=resident_name,
            notes=notes,
            assigned_by_name=user.name,
            assigned_by_role=user.role,
        )
    except Exception as e:
        print(f"[VENDOR ASSIGN EMAIL ERROR] Failed to send email to vendor: {e}")

    return jsonify({
        "message": f"Task #{complaint.id} successfully assigned to {vendor.name}",
        "vendor_task": task.to_dict(),
        "complaint_status": complaint.status,
        "email_sent": email_dispatched,
    }), 200
