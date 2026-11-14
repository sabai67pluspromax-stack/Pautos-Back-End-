from flask import g, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import MultiDict
from werkzeug.security import check_password_hash, generate_password_hash

from ..constants import ROLE_CUSTOMER, ROLE_RIDER
from ..extensions import db, limiter
from ..forms import RegisterForm
from ..models import CustomerProfile, RiderProfile, User
from . import api_login_required, bp, issue_token, jerr, user_json

_DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.route("/health")
def health():
    return jsonify(ok=True)


@bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jerr("Send a JSON body.", 400)

    data = {k: str(v) for k, v in payload.items() if v is not None}
    data.setdefault("vehicle_type", "motorcycle")   # PaUtos accepts motorcycle riders only

    # Reuse the website's registration rules (phone format, password strength, rider plate...)
    form = RegisterForm(formdata=MultiDict(data), meta={"csrf": False})
    if not form.validate():
        return jerr("Please fix the highlighted fields.", 422, fields=form.errors)

    user = User(email=form.email.data.strip().lower(), role=form.role.data)
    user.set_password(form.password.data)
    full_name = form.full_name.data.strip()
    if user.role == ROLE_RIDER:
        user.rider_profile = RiderProfile(
            full_name=full_name,
            phone=form.phone_normalized,
            vehicle_type="motorcycle",
            plate_number=(form.plate_number.data or "").strip().upper() or None,
        )
    else:
        user.role = ROLE_CUSTOMER
        user.customer_profile = CustomerProfile(full_name=full_name, phone=form.phone_normalized)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jerr("That email is already registered.", 409)

    return jsonify(token=issue_token(user, payload.get("device")), user=user_json(user)), 201


@bp.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not email or not password:
        return jerr("Email and password are required.", 400)

    user = User.query.filter_by(email=email).first()
    # Always run one hash check, so unknown emails take as long as real ones
    password_ok = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
    if not (user and password_ok and user.is_active):
        return jerr("Invalid email or password.", 401)
    if user.role not in (ROLE_CUSTOMER, ROLE_RIDER):
        return jerr("Admin accounts use the website.", 403)

    return jsonify(token=issue_token(user, payload.get("device")), user=user_json(user))


@bp.route("/auth/logout", methods=["POST"])
@api_login_required()
def logout():
    db.session.delete(g.api_token)
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/me")
@api_login_required()
def me():
    return jsonify(user=user_json(g.api_user))