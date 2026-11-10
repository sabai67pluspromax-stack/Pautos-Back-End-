"""Business rules for requests. Routes call these so the rules live in one place.

The rider arguments are RiderProfile rows (the `rider` table), not User rows.
"""
from datetime import timezone
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .constants import (
    ACTIVE_STATUSES,
    ADMIN_CANCELLABLE,
    ADMIN_REOPENABLE,
    AVAILABILITY_AVAILABLE,
    AVAILABILITY_BUSY,
    AVAILABILITY_OFFLINE,
    FINAL_STATUS,
    RELEASE_REASONS,
    RIDER_FLOW,
    RIDER_RELEASABLE,
    RIDER_SELECTABLE_AVAILABILITY,
    STATUS_ACCEPTED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DECLINED,
    STATUS_PENDING,
    VERIFICATION_APPROVED,
)
from .extensions import db
from .models import (
    RequestStatusHistory,
    RiderDecline,
    RiderEarning,
    RiderLocation,
    ServiceRequest,
    utcnow,
)


def _aware(dt):
    """SQLite and MySQL hand back naive datetimes; treat them as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _record(request_id, status, user_id, note=None):
    db.session.add(
        RequestStatusHistory(request_id=request_id, status=status, changed_by_id=user_id, note=note)
    )


def next_statuses(req):
    """The only statuses a rider may move this request to from where it is now (see RIDER_FLOW)."""
    return list(RIDER_FLOW.get(req.status, []))


def active_job_for(rider):
    return ServiceRequest.query.filter(
        ServiceRequest.rider_id == rider.id, ServiceRequest.status.in_(ACTIVE_STATUSES)
    ).first()


def set_availability(rider, new_value):
    """Rider goes online or offline. Returns (ok, message)."""
    if new_value not in RIDER_SELECTABLE_AVAILABILITY:
        return False, "Invalid availability."
    if active_job_for(rider):
        return False, "Finish your current job first."
    rider.availability_status = new_value
    db.session.commit()
    if new_value == AVAILABILITY_AVAILABLE:
        return True, "You're online. You can accept requests now."
    return True, "You're offline."


def accept_request(request_id, rider):
    """Claim a pending request. Returns (ok, message)."""
    if rider.verification_status != VERIFICATION_APPROVED:
        return False, "Your rider account is still waiting for approval."
    if rider.availability_status == AVAILABILITY_OFFLINE:
        return False, "You're offline. Go online from your dashboard first."
    if active_job_for(rider):
        return False, "Finish your current job before accepting another one."
    if RiderDecline.query.filter_by(request_id=request_id, rider_id=rider.id).first():
        return False, "You declined or released this request earlier."

    # One atomic UPDATE: it only succeeds if the request is still pending AND unclaimed.
    # If two riders tap Accept at the same moment, the database lets exactly one win.
    result = db.session.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == request_id,
            ServiceRequest.status == STATUS_PENDING,
            ServiceRequest.rider_id.is_(None),
        )
        .values(rider_id=rider.id, status=STATUS_ACCEPTED)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False, "Sorry, that request is no longer available."

    rider.availability_status = AVAILABILITY_BUSY
    _record(request_id, STATUS_ACCEPTED, rider.user_id, "Accepted by rider")
    db.session.commit()
    return True, "Request accepted. Head over when you're ready."


def decline_request(request_id, rider):
    req = db.session.get(ServiceRequest, request_id)
    if req is None or req.status != STATUS_PENDING:
        return False, "That request is no longer available."
    db.session.add(RiderDecline(request_id=request_id, rider_id=rider.id))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # already declined earlier, nothing to do
    return True, "Request declined. It won't show up for you again."


def advance_status(req, rider, new_status):
    """Move a rider's own job one step forward. Returns (ok, message)."""
    if req.rider_id != rider.id:
        return False, "This isn't your job."
    if new_status not in next_statuses(req):
        return False, "That status change isn't allowed right now."

    values = {"status": new_status}
    if new_status == STATUS_COMPLETED:
        values["completed_at"] = utcnow()

    # Conditional UPDATE so a double-click can't apply the same step twice
    result = db.session.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req.id,
            ServiceRequest.rider_id == rider.id,
            ServiceRequest.status == req.status,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False, "This job was already updated. Refresh the page."

    _record(req.id, new_status, rider.user_id)
    if new_status == FINAL_STATUS:
        db.session.add(RiderEarning(rider_id=rider.id, request_id=req.id, amount=req.service_fee))
        rider.availability_status = AVAILABILITY_AVAILABLE
    db.session.commit()
    return True, "Status updated."


def release_job(req, rider, reason_code):
    """A rider gives an accepted job back. It returns to Pending for other riders. Returns (ok, message)."""
    if req.rider_id != rider.id:
        return False, "This isn't your job."
    if req.status not in RIDER_RELEASABLE:
        return False, "This job can't be given back anymore. Please contact support."
    reasons = dict(RELEASE_REASONS)
    if reason_code not in reasons:
        return False, "Please choose a reason."

    # Conditional UPDATE, like every other status change, so a double-click can't apply it twice
    result = db.session.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req.id,
            ServiceRequest.rider_id == rider.id,
            ServiceRequest.status == req.status,
        )
        .values(rider_id=None, status=STATUS_PENDING)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False, "This job was already updated. Refresh the page."

    _record(req.id, STATUS_DECLINED, rider.user_id, f"Released by rider: {reasons[reason_code]}")
    _record(req.id, STATUS_PENDING, None, "Looking for another rider")
    # Don't offer it back to the same rider
    if not RiderDecline.query.filter_by(request_id=req.id, rider_id=rider.id).first():
        db.session.add(RiderDecline(request_id=req.id, rider_id=rider.id))
    rider.availability_status = AVAILABILITY_AVAILABLE
    db.session.commit()
    return True, "Job given back. It's now available to other riders."


def save_rider_location(rider, lat, lng):
    """Add a position row for the rider. Only allowed while they have an active job."""
    if not active_job_for(rider):
        return False, "You don't have an active job."
    db.session.add(
        RiderLocation(
            rider_id=rider.id,
            lat=Decimal(str(round(lat, 7))),
            lng=Decimal(str(round(lng, 7))),
            updated_at=utcnow(),
        )
    )
    db.session.commit()
    return True, "ok"


def _accepted_at(req):
    row = (
        RequestStatusHistory.query.filter_by(request_id=req.id, status=STATUS_ACCEPTED)
        .order_by(RequestStatusHistory.id.desc())
        .first()
    )
    return row.created_at if row else None


def tracking_payload(req):
    """What the customer's tracking page is allowed to see about this request."""
    active = req.status in ACTIVE_STATUSES
    payload = {
        "status": req.status,
        "status_label": req.status.replace("_", " ").title(),
        "active": active,
        "rider": None,
    }
    if not (active and req.rider_id):
        return payload

    rider = {"name": req.rider.full_name, "lat": None, "lng": None, "seconds_ago": None}
    loc = (
        RiderLocation.query.filter_by(rider_id=req.rider_id)
        .order_by(RiderLocation.updated_at.desc(), RiderLocation.id.desc())
        .first()
    )
    accepted_at = _accepted_at(req)
    # Ignore a position from before this job started (left over from an earlier job)
    if loc and accepted_at and _aware(loc.updated_at) >= _aware(accepted_at):
        rider["lat"] = float(loc.lat)
        rider["lng"] = float(loc.lng)
        rider["seconds_ago"] = max(0, int((utcnow() - _aware(loc.updated_at)).total_seconds()))
    payload["rider"] = rider
    return payload

def _with_note(text, note):
    return f"{text}: {note}" if note else text


def admin_cancel_request(req, admin_user, note):
    if req.status not in ADMIN_CANCELLABLE:
        return False, "This request can't be cancelled anymore."

    rider = req.rider
    previous = req.status
    result = db.session.execute(
        update(ServiceRequest)
        .where(ServiceRequest.id == req.id, ServiceRequest.status == previous)
        .values(status=STATUS_CANCELLED)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False, "This request was already updated. Refresh the page."

    _record(req.id, STATUS_CANCELLED, admin_user.id, _with_note("Cancelled by admin", note))
    if rider is not None and previous in ACTIVE_STATUSES:
        rider.availability_status = AVAILABILITY_AVAILABLE
    db.session.commit()
    return True, "Request cancelled."


def admin_reopen_request(req, admin_user, note):
    if req.status not in ADMIN_REOPENABLE:
        return False, "Only requests a rider is working on can be returned to the pool."

    rider = req.rider
    previous = req.status
    result = db.session.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req.id,
            ServiceRequest.status == previous,
            ServiceRequest.rider_id == req.rider_id,
        )
        .values(rider_id=None, status=STATUS_PENDING)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False, "This request was already updated. Refresh the page."

    _record(req.id, STATUS_PENDING, admin_user.id, _with_note("Returned to the pool by admin", note))
    if rider is not None:
        if not RiderDecline.query.filter_by(request_id=req.id, rider_id=rider.id).first():
            db.session.add(RiderDecline(request_id=req.id, rider_id=rider.id))
        rider.availability_status = AVAILABILITY_AVAILABLE
    db.session.commit()
    return True, "Request returned to the pool. Other riders can accept it now."
def request_points(req):
       def pair(lat, lng):
           if lat is None or lng is None:
               return None
           return {"lat": float(lat), "lng": float(lng)}

       return {
           "pickup": pair(req.pickup_lat, req.pickup_lng),
           "dropoff": pair(req.dropoff_lat, req.dropoff_lng),
       }