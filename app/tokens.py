import hashlib

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db
from .models import User

_SALT = "password-reset-v1"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def _fingerprint(user):
    # Changes as soon as the password changes, so a reset link only works once
    return hashlib.sha256(user.password_hash.encode("utf-8")).hexdigest()[:20]


def make_reset_token(user):
    return _serializer().dumps({"id": user.id, "f": _fingerprint(user)})


def user_from_reset_token(token):
    try:
        data = _serializer().loads(token, max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
        user = db.session.get(User, int(data["id"]))
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
    if user is None or not user.is_active or data.get("f") != _fingerprint(user):
        return None
    return user