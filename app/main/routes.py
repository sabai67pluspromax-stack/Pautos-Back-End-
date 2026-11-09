from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..constants import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_RIDER
from ..utils import role_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == ROLE_ADMIN:
        return redirect(url_for("admin.dashboard"))
    if current_user.role == ROLE_RIDER:
        return redirect(url_for("main.rider_dashboard"))
    return redirect(url_for("main.customer_dashboard"))


@bp.route("/customer/dashboard")
@role_required(ROLE_CUSTOMER)
def customer_dashboard():
    return render_template("customer/dashboard.html")


@bp.route("/rider/dashboard")
@role_required(ROLE_RIDER)
def rider_dashboard():
    return render_template("rider/dashboard.html")