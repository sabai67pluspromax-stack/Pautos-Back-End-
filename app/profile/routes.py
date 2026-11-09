from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..constants import ROLE_CUSTOMER, ROLE_RIDER
from ..extensions import db, limiter
from ..forms import ChangePasswordForm, CustomerProfileForm, RiderProfileForm

bp = Blueprint("profile", __name__, url_prefix="/profile")


@bp.route("/", methods=["GET", "POST"])
@login_required
def edit_profile():
    if current_user.role == ROLE_RIDER:
        form = RiderProfileForm(current_user)
        profile = current_user.rider_profile
    elif current_user.role == ROLE_CUSTOMER:
        form = CustomerProfileForm(current_user)
        profile = current_user.customer_profile
    else:
        abort(403)

    if request.method == "GET":
        form.full_name.data = profile.full_name
        form.phone.data = profile.phone
        if current_user.role == ROLE_RIDER:
            form.vehicle_type.data = profile.vehicle_type
            form.plate_number.data = profile.plate_number
        else:
            form.default_address.data = profile.default_address

    if form.validate_on_submit():
        profile.full_name = form.full_name.data.strip()
        profile.phone = form.phone_normalized
        if current_user.role == ROLE_RIDER:
            profile.vehicle_type = form.vehicle_type.data
            profile.plate_number = (form.plate_number.data or "").strip().upper() or None
        else:
            profile.default_address = (form.default_address.data or "").strip() or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.edit_profile"))

    status = 400 if request.method == "POST" else 200
    return render_template("profile/edit.html", form=form, profile=profile), status


@bp.route("/password", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per hour", methods=["POST"])
def change_password():
    form = ChangePasswordForm(current_user)
    if form.validate_on_submit():
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Password changed.", "success")
        return redirect(url_for("profile.edit_profile"))

    status = 400 if request.method == "POST" else 200
    return render_template("profile/password.html", form=form), status