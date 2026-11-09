from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from ..constants import (
    ACTIVE_STATUSES,
    CUSTOMER_CANCELLABLE,
    OPEN_STATUSES,
    ROLE_CUSTOMER,
    STATUS_CANCELLED,
    STATUS_PENDING,
)
from ..extensions import db
from ..forms import NewRequestForm
from ..models import RequestStatusHistory, ServiceRequest
from ..services import tracking_payload
from ..utils import role_required

bp = Blueprint("customer", __name__, url_prefix="/customer")


def get_own_request_or_404(request_id):
    req = db.session.get(ServiceRequest, request_id)
    # 404 (not 403) so users can't probe which request ids exist
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
            service_fee=category.base_fee,  # always from the database, never from the browser
            status=STATUS_PENDING,
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
    requests_ = (
        ServiceRequest.query.filter_by(customer_id=current_user.customer_profile.id)
        .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .all()
    )
    return render_template("customer/requests.html", requests=requests_)


@bp.route("/requests/<int:request_id>")
@role_required(ROLE_CUSTOMER)
def request_detail(request_id):
    req = get_own_request_or_404(request_id)
    # Keep polling while the request can still change; show the map once a rider has it
    watch = req.status in OPEN_STATUSES
    show_map = req.status in ACTIVE_STATUSES
    return render_template("customer/request_detail.html", req=req, watch=watch, show_map=show_map)


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