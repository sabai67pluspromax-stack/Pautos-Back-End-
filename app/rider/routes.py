from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from ..constants import (
    ACTIVE_STATUSES,
    AVAILABILITY_OFFLINE,
    PAGE_SIZE,
    RELEASE_REASONS,
    RIDER_ACTION_LABELS,
    RIDER_RELEASABLE,
    ROLE_RIDER,
    STATUS_COMPLETED,
    STATUS_PENDING,
    VERIFICATION_APPROVED,
    AVAILABILITY_AVAILABLE,
    PAYABLE_STATUSES,
    PAYMENT_METHOD_LABELS, 
    PAYMENT_STATUS_LABELS
)

from ..forms import GcashQrForm
from ..extensions import db, limiter
from ..models import RiderDecline, RiderEarning, ServiceRequest
from ..services import (
    accept_request,
    advance_status,
    decline_request,
    next_statuses,
    release_job,
    request_points,
    save_rider_location,
    set_availability,
    visible_requests_for,
    rider_position,
    confirm_payment, 
    reject_payment
)
from ..utils import role_required
from ..uploads import delete_qr_image, save_qr_image, send_qr_image

bp = Blueprint("rider", __name__, url_prefix="/rider")


def get_own_job_or_404(request_id):
    req = db.session.get(ServiceRequest, request_id)
    if req is None or req.rider_id != current_user.rider_profile.id:
        abort(404)
    return req


@bp.route("/availability", methods=["POST"])
@role_required(ROLE_RIDER)
def update_availability():
    ok, message = set_availability(current_user.rider_profile, request.form.get("availability", ""))
    flash(message, "success" if ok else "error")
    return redirect(url_for("main.rider_dashboard"))


@bp.route("/requests")
@role_required(ROLE_RIDER)
def available_requests():
    rider = current_user.rider_profile
    ids, distances, position = visible_requests_for(rider)
    stmt = (
        db.select(ServiceRequest)
        .where(ServiceRequest.id.in_(ids))
        .order_by(ServiceRequest.created_at.asc(), ServiceRequest.id.asc())
    )
    pagination = db.paginate(stmt, per_page=PAGE_SIZE, error_out=False)
    return render_template(
        "rider/available.html",
        pagination=pagination,
        distances=distances,
        has_position=position is not None,
        approved=rider.verification_status == VERIFICATION_APPROVED,
        offline=rider.availability_status == AVAILABILITY_OFFLINE,
    )

@bp.route("/requests/feed")
@role_required(ROLE_RIDER)
@limiter.limit("40 per minute")
def requests_feed():
    rider = current_user.rider_profile
    if (
        rider.verification_status != VERIFICATION_APPROVED
        or rider.availability_status != AVAILABILITY_AVAILABLE
    ):
        return jsonify(active=False, requests=[])

    ids, distances, position = visible_requests_for(rider)
    rows = (
        ServiceRequest.query.filter(ServiceRequest.id.in_(ids))
        .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        active=True,
        has_position=position is not None,
        requests=[
            {
                "id": r.id,
                "category": r.category.name,
                "instructions": (r.instructions or "")[:140],
                "pickup": r.pickup_address,
                "dropoff": r.dropoff_address,
                "fee": float(r.service_fee),
                "budget": float(r.item_budget) if r.item_budget is not None else None,
                "distance_km": round(distances[r.id], 1) if distances.get(r.id) is not None else None,
            }
            for r in rows
        ],
    )

@bp.route("/requests/<int:request_id>/accept", methods=["POST"])
@role_required(ROLE_RIDER)
def accept(request_id):
    ok, message = accept_request(request_id, current_user.rider_profile)
    flash(message, "success" if ok else "error")
    if ok:
        return redirect(url_for("rider.job_detail", request_id=request_id))
    return redirect(url_for("rider.available_requests"))


@bp.route("/requests/<int:request_id>/decline", methods=["POST"])
@role_required(ROLE_RIDER)
def decline(request_id):
    ok, message = decline_request(request_id, current_user.rider_profile)
    flash(message, "info" if ok else "error")
    return redirect(url_for("rider.available_requests"))


@bp.route("/jobs")
@role_required(ROLE_RIDER)
def my_jobs():
    rider = current_user.rider_profile
    active = (
        ServiceRequest.query.filter(
            ServiceRequest.rider_id == rider.id, ServiceRequest.status.in_(ACTIVE_STATUSES)
        )
        .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .all()
    )
    completed = (
        db.select(ServiceRequest)
        .where(ServiceRequest.rider_id == rider.id, ServiceRequest.status == STATUS_COMPLETED)
        .order_by(ServiceRequest.completed_at.desc(), ServiceRequest.id.desc())
    )
    pagination = db.paginate(completed, per_page=PAGE_SIZE, error_out=False)
    earnings = (
        db.session.query(func.coalesce(func.sum(RiderEarning.amount), 0))
        .filter(RiderEarning.rider_id == rider.id)
        .scalar()
    )
    return render_template("rider/jobs.html", active=active, pagination=pagination, earnings=earnings)


@bp.route("/jobs/<int:request_id>")
@role_required(ROLE_RIDER)
def job_detail(request_id):
    req = get_own_job_or_404(request_id)
    return render_template(
        "rider/job_detail.html",
        req=req,
        next_statuses=next_statuses(req),
        labels=RIDER_ACTION_LABELS,
        is_active=req.status in ACTIVE_STATUSES,
        can_release=req.status in RIDER_RELEASABLE,
        release_reasons=RELEASE_REASONS,
        points=request_points(req),
        show_payment=req.status in PAYABLE_STATUSES,
        method_labels=PAYMENT_METHOD_LABELS,
        payment_labels=PAYMENT_STATUS_LABELS,
    )


@bp.route("/jobs/<int:request_id>/status", methods=["POST"])
@role_required(ROLE_RIDER)
def update_status(request_id):
    req = get_own_job_or_404(request_id)
    ok, message = advance_status(req, current_user.rider_profile, request.form.get("status", ""))
    flash(message, "success" if ok else "error")
    return redirect(url_for("rider.job_detail", request_id=request_id))


@bp.route("/jobs/<int:request_id>/release", methods=["POST"])
@role_required(ROLE_RIDER)
def release(request_id):
    req = get_own_job_or_404(request_id)
    ok, message = release_job(req, current_user.rider_profile, request.form.get("reason", ""))
    flash(message, "info" if ok else "error")
    if ok:
        return redirect(url_for("rider.available_requests"))
    return redirect(url_for("rider.job_detail", request_id=request_id))


@bp.route("/location", methods=["POST"])
@role_required(ROLE_RIDER)
@limiter.limit("30 per minute")
def update_location():
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="lat and lng must be numbers"), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify(error="coordinates out of range"), 400

    ok, message = save_rider_location(current_user.rider_profile, lat, lng)
    if not ok:
        return jsonify(error=message), 409
    return jsonify(ok=True)

@bp.route("/gcash", methods=["GET", "POST"])
@role_required(ROLE_RIDER)
def gcash_settings():
    rider = current_user.rider_profile
    form = GcashQrForm(gcash_name=rider.gcash_name)
    if form.validate_on_submit():
        upload = form.qr_image.data
        if upload and upload.filename:
            filename, error = save_qr_image(upload)
            if error:
                form.qr_image.errors.append(error)
                return render_template("rider/gcash.html", form=form, rider=rider), 400
            delete_qr_image(rider.gcash_qr_file)
            rider.gcash_qr_file = filename
        rider.gcash_name = (form.gcash_name.data or "").strip() or None
        db.session.commit()
        flash("GCash details saved.", "success")
        return redirect(url_for("rider.gcash_settings"))

    status = 400 if request.method == "POST" else 200
    return render_template("rider/gcash.html", form=form, rider=rider), status


@bp.route("/gcash/qr")
@role_required(ROLE_RIDER)
def gcash_qr_image():
    rider = current_user.rider_profile
    if not rider.gcash_qr_file:
        abort(404)
    return send_qr_image(rider.gcash_qr_file)


@bp.route("/gcash/remove", methods=["POST"])
@role_required(ROLE_RIDER)
def gcash_remove():
    rider = current_user.rider_profile
    delete_qr_image(rider.gcash_qr_file)
    rider.gcash_qr_file = None
    db.session.commit()
    flash("GCash QR removed.", "info")
    return redirect(url_for("rider.gcash_settings"))


@bp.route("/jobs/<int:request_id>/payment", methods=["POST"])
@role_required(ROLE_RIDER)
def update_payment(request_id):
    req = get_own_job_or_404(request_id)
    action = request.form.get("action", "")
    if action == "confirm":
        ok, message = confirm_payment(req, current_user.rider_profile)
    elif action == "not_received":
        ok, message = reject_payment(req, current_user.rider_profile)
    else:
        abort(400)
    flash(message, "success" if ok else "error")
    return redirect(url_for("rider.job_detail", request_id=request_id))