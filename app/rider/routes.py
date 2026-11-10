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
)
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
)
from ..utils import role_required

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
    declined = db.select(RiderDecline.request_id).where(RiderDecline.rider_id == rider.id)
    stmt = (
        db.select(ServiceRequest)
        .where(ServiceRequest.status == STATUS_PENDING, ServiceRequest.id.not_in(declined))
        .order_by(ServiceRequest.created_at.asc(), ServiceRequest.id.asc())
    )
    pagination = db.paginate(stmt, per_page=PAGE_SIZE, error_out=False)
    return render_template(
        "rider/available.html",
        pagination=pagination,
        approved=rider.verification_status == VERIFICATION_APPROVED,
        offline=rider.availability_status == AVAILABILITY_OFFLINE,
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