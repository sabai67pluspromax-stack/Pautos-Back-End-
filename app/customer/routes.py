from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from ..constants import (
    ACTIVE_STATUSES,
    CUSTOMER_CANCELLABLE,
    FILTER_STATUSES,
    OPEN_STATUSES,
    PAGE_SIZE,
    ROLE_CUSTOMER,
    STATUS_CANCELLED,
    STATUS_PENDING,
)
from ..extensions import db
from ..forms import NewRequestForm
from ..models import RequestStatusHistory, ServiceRequest
from ..services import request_points, tracking_payload
from ..utils import role_required

bp = Blueprint("customer", __name__, url_prefix="/customer")


def get_own_request_or_404(request_id):
    req = db.session.get(ServiceRequest, request_id)
    if req is None or req.customer_id != current_user.customer_profile.id:
        abort(404)
    return req


@bp.route("/requests/new", methods=["GET", "POST"])
@role_required(ROLE_CUSTOMER)
def new_request():
    form = NewRequestForm()

    if request.method == "GET" and current_user.customer_profile.default_address:
        form.dropoff_address.data = current_user.customer_profile.default_address

    if form.validate_on_submit():
        category = form.selected_category()
        req = ServiceRequest(
            customer_id=current_user.customer_profile.id,
            category_id=category.id,
            instructions=form.instructions.data.strip(),
            pickup_address=form.pickup_address.data.strip(),
            dropoff_address=form.dropoff_address.data.strip(),
            item_budget=form.item_budget.data,
            service_fee=category.base_fee,
            status=STATUS_PENDING,
            **form.coordinates(),
        )
        req.history.append(
            RequestStatusHistory(status=STATUS_PENDING, changed_by_id=current_user.id, note="Request created")
        )
        db.session.add(req)
        db.session.commit()
        flash("Request submitted. We'll find you a rider.", "success")
        return redirect(url_for("customer.request_detail", request_id=req.id))

    status = 400 if request.method == "POST" else 200
    return render_template("customer/new_request.html", form=form), status


@bp.route("/requests")
@role_required(ROLE_CUSTOMER)
def request_list():
    current_status = request.args.get("status", "")
    if current_status not in FILTER_STATUSES:
        current_status = ""
    stmt = db.select(ServiceRequest).where(ServiceRequest.customer_id == current_user.customer_profile.id)
    if current_status:
        stmt = stmt.where(ServiceRequest.status == current_status)
    stmt = stmt.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
    pagination = db.paginate(stmt, per_page=PAGE_SIZE, error_out=False)
    return render_template(
        "customer/requests.html",
        pagination=pagination,
        statuses=FILTER_STATUSES,
        current_status=current_status,
    )


@bp.route("/requests/<int:request_id>")
@role_required(ROLE_CUSTOMER)
def request_detail(request_id):
    req = get_own_request_or_404(request_id)
    points = request_points(req)
    has_pins = bool(points["pickup"] or points["dropoff"])
    watch = req.status in OPEN_STATUSES
    show_map = req.status in ACTIVE_STATUSES or (req.status == STATUS_PENDING and has_pins)
    return render_template(
        "customer/request_detail.html", req=req, watch=watch, show_map=show_map, points=points
    )


@bp.route("/requests/<int:request_id>/track")
@role_required(ROLE_CUSTOMER)
def track_request(request_id):
    req = get_own_request_or_404(request_id)
    return jsonify(tracking_payload(req))


@bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@role_required(ROLE_CUSTOMER)
def cancel_request(request_id):
    req = get_own_request_or_404(request_id)
    if req.status not in CUSTOMER_CANCELLABLE:
        flash("Only requests that haven't been accepted yet can be cancelled.", "error")
        return redirect(url_for("customer.request_detail", request_id=req.id))

    req.status = STATUS_CANCELLED
    req.history.append(
        RequestStatusHistory(status=STATUS_CANCELLED, changed_by_id=current_user.id, note="Cancelled by customer")
    )
    db.session.commit()
    flash("Request cancelled.", "info")
    return redirect(url_for("customer.request_detail", request_id=req.id))