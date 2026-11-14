import hashlib
import secrets
from datetime import timedelta, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request
from werkzeug.exceptions import HTTPException

from ..extensions import db
from ..models import ApiToken, User, utcnow

bp = Blueprint("api", _name_, url_prefix="/api/v1")

TOKEN_DAYS = 30


def jerr(message, status=400, **extra):
    return jsonify(error=message, **extra), status


@bp.errorhandler(HTTPException)
def http_error(e):
    return jerr(e.description, e.code)


def _hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def issue_token(user, device=None):
    """Create a login token and return the raw value (the app sees it only once)."""
    ApiToken.query.filter(ApiToken.expires_at < utcnow()).delete()   # tidy up expired ones
    raw = secrets.token_urlsafe(32)
    db.session.add(
        ApiToken(
            user_id=user.id,
            token_hash=_hash(raw),
            device=(str(device)[:100] if device else None),
            expires_at=utcnow() + timedelta(days=TOKEN_DAYS),
        )
    )
    db.session.commit()
    return raw


def user_for_token(raw):
    row = ApiToken.query.filter_by(token_hash=_hash(raw)).first()
    now = utcnow()
    if row is None or _aware(row.expires_at) < now:
        return None, None
    user = db.session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None, None
    if row.last_used_at is None or (now - _aware(row.last_used_at)).total_seconds() > 300:
        row.last_used_at = now
        db.session.commit()
    return user, row


def api_login_required(*roles):
    """Needs 'Authorization: Bearer <token>', optionally for specific roles only."""

    def wrap(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jerr("Missing login token.", 401)
            user, row = user_for_token(header[7:].strip())
            if user is None:
                return jerr("Your login expired. Please log in again.", 401)
            if roles and user.role not in roles:
                return jerr("This isn't available for your account type.", 403)
            g.api_user = user
            g.api_token = row
            return fn(*args, **kwargs)

        return inner

    return wrap


def user_json(user):
    data = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "phone": user.phone,
    }
    if user.customer_profile:
        data["customer"] = {"default_address": user.customer_profile.default_address}
    if user.rider_profile:
        r = user.rider_profile
        data["rider"] = {
            "vehicle_type": r.vehicle_type,
            "plate_number": r.plate_number,
            "availability": r.availability_status,
            "verification": r.verification_status,
            "has_gcash_qr": bool(r.gcash_qr_file),
            "gcash_name": r.gcash_name,
        }
    return data


from . import auth  # noqa: E402,F401  (registers the routes)