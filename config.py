import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Falls back to SQLite if DATABASE_URL isn't set (see .env.example for MySQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # Real databases are built by migrations (flask db upgrade). Only the tests build tables directly.
    AUTO_CREATE_DB = False

    # Session / cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Rate limiting (use redis:// in production)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    RESET_TOKEN_MAX_AGE = 3600  # seconds

    TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
    PREFERRED_URL_SCHEME = "https" if os.environ.get("FLASK_ENV") == "production" else "http"

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    AUTO_CREATE_DB = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False