from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..constants import (
    ADMIN_CANCELLABLE,
    ADMIN_REOPENABLE,
    OPEN_STATUSES,
    ROLE_ADMIN,
    VERIFICATION_APPROVED,
    VERIFICATION_ORDER,
    VERIFICATION_PENDING,
    VERIFICATION_REJECTED,
)
from ..extensions import db
from ..forms import CategoryForm
from ..models import RiderProfile, ServiceCategory, ServiceRequest
from ..services import admin_cancel_request, admin_reopen_request
from ..utils import role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@role_required(ROLE_ADMIN)
def dashboard():
    stats = {
        "pending_riders": RiderProfile.query.filter_by(verification_status=VERIFICATION_PENDING).count(),
        "total_requests": ServiceRequest.query.count(),
        "open_requests": ServiceRequest.query.filter(ServiceRequest.status.in_(OPEN_STATUSES)).count(),
        "categories": ServiceCategory.query.filter_by(is_active=True).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/riders")
@role_required(ROLE_ADMIN)
def riders():
    items = RiderProfile.query.options(joinedload(RiderProfile.user)).all()
    items.sort(key=lambda r: (VERIFICATION_ORDER.get(r.verification_status, 9), -r.id))
    return render_template("admin/riders.html", riders=items)


@bp.route("/riders/<int:rider_id>/status", methods=["POST"])
@role_required(ROLE_ADMIN)
def set_rider_status(rider_id):
    rider = db.session.get(RiderProfile, rider_id)
    if rider is None:
        abort(404)
    new_status = request.form.get("status")
    if new_status not in (VERIFICATION_APPROVED, VERIFICATION_REJECTED):
        abort(400)
    rider.verification_status = new_status
    db.session.commit()
    flash(f"{rider.full_name} is now {new_status}.", "success")
    return redirect(url_for("admin.riders"))


@bp.route("/categories")
@role_required(ROLE_ADMIN)
def categories():
    items = ServiceCategory.query.order_by(ServiceCategory.sort_order, ServiceCategory.id).all()
    return render_template("admin/categories.html", categories=items)


@bp.route("/categories/new", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def new_category():
    form = CategoryForm()
    if form.validate_on_submit():
        category = ServiceCategory(
            name=form.name.data.strip(),
            description=(form.description.data or "").strip() or None,
            base_fee=form.base_fee.data,
            requires_purchase=form.requires_purchase.data,
            sort_order=form.sort_order.data or 0,
        )
        db.session.add(category)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Could not save: that name is already taken.", "error")
            return render_template("admin/category_form.html", form=form, editing=False), 400
        flash("Category created.", "success")
        return redirect(url_for("admin.categories"))

    status = 400 if request.method == "POST" else 200
    return render_template("admin/category_form.html", form=form, editing=False), status


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def edit_category(category_id):
    category = db.get_or_404(ServiceCategory, category_id)
    form = CategoryForm(obj=category, category=category)
    if form.validate_on_submit():
        category.name = form.name.data.strip()
        category.description = (form.description.data or "").strip() or None
        category.base_fee = form.base_fee.data  # only affects NEW requests; old ones keep their fee
        category.requires_purchase = form.requires_purchase.data
        category.sort_order = form.sort_order.data or 0
        db.session.commit()
        flash("Category updated.", "success")
        return redirect(url_for("admin.categories"))

    status = 400 if request.method == "POST" else 200
    return render_template("admin/category_form.html", form=form, editing=True, category=category), status


@bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@role_required(ROLE_ADMIN)
def toggle_category(category_id):
    category = db.get_or_404(ServiceCategory, category_id)
    category.is_active = not category.is_active
    db.session.commit()
    flash(f"{category.name} is now {'active' if category.is_active else 'hidden from customers'}.", "info")
    return redirect(url_for("admin.categories"))

@bp.route("/requests")
@role_required(ROLE_ADMIN)
def requests_overview():
    items = (
        ServiceRequest.query.options(
            joinedload(ServiceRequest.customer),
            joinedload(ServiceRequest.rider),
            joinedload(ServiceRequest.category),
        )
        .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .limit(200)
        .all()
    )
    return render_template("admin/requests.html", requests=items)

@bp.route("/requests/<int:request_id>")
@role_required(ROLE_ADMIN)
def request_detail(request_id):
    req = db.get_or_404(ServiceRequest, request_id)
    return render_template(
        "admin/request_detail.html",
        req=req,
        can_cancel=req.status in ADMIN_CANCELLABLE,
        can_reopen=req.status in ADMIN_REOPENABLE,
    )


@bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@role_required(ROLE_ADMIN)
def cancel_request(request_id):
    req = db.get_or_404(ServiceRequest, request_id)
    note = request.form.get("note", "").strip()[:255]
    ok, message = admin_cancel_request(req, current_user, note)
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin.request_detail", request_id=request_id))


@bp.route("/requests/<int:request_id>/reopen", methods=["POST"])
@role_required(ROLE_ADMIN)
def reopen_request(request_id):
    req = db.get_or_404(ServiceRequest, request_id)
    note = request.form.get("note", "").strip()[:255]
    ok, message = admin_reopen_request(req, current_user, note)
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin.request_detail", request_id=request_id))