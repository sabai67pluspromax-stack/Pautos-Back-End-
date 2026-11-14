from datetime import timedelta, timezone

from flask import Flask

from config import Config

from .extensions import csrf, db, limiter, login_manager, migrate

PH_TZ = timezone(timedelta(hours=8))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    # render_as_batch lets the same migrations also run on SQLite if you ever fall back to it
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  (migrations and tests need every model imported)
    from .admin.routes import bp as admin_bp
    from .auth.routes import bp as auth_bp
    from .cli import register_cli
    from .customer.routes import bp as customer_bp
    from .main.routes import bp as main_bp
    from .profile.routes import bp as profile_bp
    from .rider.routes import bp as rider_bp
    from .seed import seed_categories
    from .api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(rider_bp)
    app.register_blueprint(admin_bp)
    register_cli(app)
    csrf.exempt(api_bp)

    if app.config["AUTO_CREATE_DB"]:  # tests only; real databases come from `flask db upgrade`
        with app.app_context():
            db.create_all()
            seed_categories()

    @app.template_filter("ph_time")
    def ph_time(dt):
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(PH_TZ).strftime("%b %d, %Y %I:%M %p")

    @app.template_filter("status_label")
    def status_label(value):
        return (value or "").replace("_", " ").title()

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    return app