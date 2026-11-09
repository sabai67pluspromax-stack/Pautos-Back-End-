from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, current_app, request
from flask_login import current_user


def role_required(role):
    """Restrict a route to a single role (customer, rider, admin)."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def is_safe_redirect(target):
    """Prevent open-redirects through the ?next= parameter."""
    if not target:
        return False
    host = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and host.netloc == test.netloc
