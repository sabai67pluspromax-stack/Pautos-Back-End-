from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..constants import ROLE_CUSTOMER, ROLE_RIDER
from ..extensions import db, limiter
from ..forms import LoginForm, RegisterForm
from ..models import CustomerProfile, RiderProfile, User
from ..utils import is_safe_redirect
from ..forms import ForgotPasswordForm, ResetPasswordForm   # add to your existing forms import
from ..mail import send_email
from ..tokens import make_reset_token, user_from_reset_token

bp = Blueprint("auth", __name__)

# Used so a login for a non-existent email takes about as long as a real one
_DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data.strip().lower(), role=form.role.data)
        user.set_password(form.password.data)
        full_name = form.full_name.data.strip()

        if user.role == ROLE_RIDER:
            user.rider_profile = RiderProfile(
                full_name=full_name,
                phone=form.phone_normalized,
                vehicle_type=form.vehicle_type.data,
                plate_number=(form.plate_number.data or "").strip().upper() or None,
            )
        else:
            user.role = ROLE_CUSTOMER
            user.customer_profile = CustomerProfile(full_name=full_name, phone=form.phone_normalized)

        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Race condition: someone registered the same email a moment ago
            db.session.rollback()
            flash("That email is already registered.", "error")
            return render_template("auth/register.html", form=form), 400

        login_user(user)
        flash("Welcome! Your account has been created.", "success")
        return redirect(url_for("main.dashboard"))

    status = 400 if request.method == "POST" else 200
    return render_template("auth/register.html", form=form), status


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            password_ok = user.check_password(form.password.data)
        else:
            check_password_hash(_DUMMY_HASH, form.password.data)
            password_ok = False

        if not password_ok or not user.is_active:
            # Same message either way, so attackers can't tell which emails exist
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", form=form), 401

        login_user(user, remember=form.remember.data)

        next_url = request.args.get("next")
        if is_safe_redirect(next_url):
            return redirect(next_url)
        return redirect(url_for("main.dashboard"))

    status = 400 if request.method == "POST" else 200
    return render_template("auth/login.html", form=form), status


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))

@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active:
            link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
            send_email(
                user.email,
                "Reset your PaUtos password",
                "Hi,\n\nUse this link to choose a new password. It works once and expires in 1 hour:\n\n"
                f"{link}\n\nIf you didn't ask for this, you can ignore this email.",
            )
        # Same message whether or not the email exists, so the page can't be used to find accounts
        flash("If that email has an account, we've sent a link to reset the password.", "info")
        return redirect(url_for("auth.login"))

    status = 400 if request.method == "POST" else 200
    return render_template("auth/forgot_password.html", form=form), status


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def reset_password(token):
    user = user_from_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        flash("Password updated. You can log in now.", "success")
        return redirect(url_for("auth.login"))

    status = 400 if request.method == "POST" else 200
    return render_template("auth/reset_password.html", form=form), status