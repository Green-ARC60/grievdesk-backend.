from flask import Blueprint, jsonify, request

from app.extensions import db
from app.utils.decorators import login_required, committee_or_secretary_required, current_user
from app.models.service_request import ServiceRequest, ServiceRequestStatus
from app.models.ticket_event import TicketType, TicketAction
from app.services.tickets import add_event, timeline, notify_owner_of_status
from app.services.translation import localize_groups

service_requests_bp = Blueprint("service_requests", __name__, url_prefix="/api/service-requests")


@service_requests_bp.get("")
@login_required
def list_service_requests():
    """Residents see only their own; committee/secretary see everyone's in their society."""
    viewer = current_user()
    query = ServiceRequest.query.filter(ServiceRequest.society_id == viewer.society_id)
    if not viewer.is_staff():
        query = query.filter_by(user_id=viewer.id)
    rows = [r.to_public_dict() for r in query.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc()).all()]
    meta = localize_groups(viewer, (rows, ["description"]))
    return jsonify({"service_requests": rows, **meta}), 200


@service_requests_bp.post("")
@login_required
def create_service_request():
    """
    Directly create a household service request for a flat.
    Permitted for all authenticated members.
    """
    user = current_user()
    data = request.get_json(silent=True) or {}

    service_type = (data.get("service_type") or "other").strip()[:30]
    raw_text = (data.get("description") or data.get("raw_text") or "").strip()
    preferred_slot = (data.get("preferred_slot") or data.get("preferred_time") or "").strip()

    if not raw_text:
        return jsonify({"error": "description is required"}), 400

    full_description = raw_text
    if preferred_slot:
        full_description = f"{raw_text} (Preferred Slot: {preferred_slot})"

    new_request = ServiceRequest(
        user_id=user.id,
        society_id=user.society_id,
        service_type=service_type,
        raw_text=full_description,
        translated_text=full_description,
        status=ServiceRequestStatus.NEW,
    )
    db.session.add(new_request)
    db.session.commit()

    add_event(
        ticket_type=TicketType.SERVICE_REQUEST,
        ticket_id=new_request.id,
        action=TicketAction.CREATED,
        detail=f"Service: {service_type}",
        note=f"Booked by Flat {user.flat_no or '-'}, Block {user.block_no or '-'}",
        actor=user,
    )
    db.session.commit()

    return jsonify({
        "message": "Service request created successfully.",
        "service_request": new_request.to_public_dict(),
    }), 201


@service_requests_bp.get("/<int:request_id>")
@login_required
def get_service_request(request_id):
    viewer = current_user()
    row = db.session.get(ServiceRequest, request_id)
    # A resident asking for someone else's request gets the same answer as for a missing one.
    if row is None or row.society_id != viewer.society_id or not (viewer.is_staff() or row.user_id == viewer.id):
        return jsonify({"error": "service_request_not_found"}), 404
    body = row.to_public_dict()
    body["timeline"] = timeline(TicketType.SERVICE_REQUEST, row.id)
    meta = localize_groups(viewer, ([body], ["description"]), (body["timeline"], ["note"]))
    return jsonify({**body, **meta}), 200


@service_requests_bp.patch("/<int:request_id>/status")
@committee_or_secretary_required
def update_status(request_id):
    actor = current_user()
    row = db.session.get(ServiceRequest, request_id)
    if row is None or row.society_id != actor.society_id:
        return jsonify({"error": "service_request_not_found"}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ServiceRequestStatus.ALL:
        return jsonify({"error": "invalid_status", "allowed": list(ServiceRequestStatus.ALL)}), 400
    if new_status == row.status:
        return jsonify({"message": "Status unchanged.", "service_request": row.to_public_dict()}), 200

    row.status = new_status
    add_event(TicketType.SERVICE_REQUEST, row.id, TicketAction.STATUS_CHANGED, detail=new_status, actor=actor)
    notify_owner_of_status(TicketType.SERVICE_REQUEST, row, row.user_id, actor, new_status)
    db.session.commit()
    return jsonify({"message": "Status updated.", "service_request": row.to_public_dict()}), 200


@service_requests_bp.delete("/<int:request_id>")
@login_required
def delete_service_request(request_id):
    """
    Delete a service request:
    Allowed for author or staff within the same society.
    """
    viewer = current_user()
    row = db.session.get(ServiceRequest, request_id)
    if row is None or row.society_id != viewer.society_id:
        return jsonify({"error": "service_request_not_found"}), 404
    if not (viewer.is_staff() or row.user_id == viewer.id):
        return jsonify({"error": "forbidden", "message": "You can only delete your own service requests."}), 403

    from datetime import datetime, timezone
    row.is_deleted = True
    row.deleted_at = datetime.now(timezone.utc)
    row.status = "deleted"
    db.session.commit()
    return jsonify({"message": "Service request deleted successfully.", "id": request_id}), 200
