import re
from datetime import timedelta

import click

from .constants import ROLE_ADMIN, ROLE_RIDER, VERIFICATION_APPROVED
from .extensions import db
from .models import RiderLocation, User, utcnow
from .seed import seed_categories


def register_cli(app):
    @app.cli.command("seed-categories")
    def seed_categories_command():
        """Add the starter service categories (does nothing if categories already exist)."""
        added = seed_categories()
        click.echo(f"Added {added} categories." if added else "Categories already exist, nothing to do.")

    @app.cli.command("approve-rider")
    @click.argument("email")
    def approve_rider(email):
        """Mark a rider as approved so they can accept jobs."""
        user = User.query.filter_by(email=email.strip().lower(), role=ROLE_RIDER).first()
        if user is None:
            click.echo("No rider found with that email.")
            return
        user.rider_profile.verification_status = VERIFICATION_APPROVED
        db.session.commit()
        click.echo(f"Approved rider: {user.full_name} ({user.email})")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(email, password):
        """Create an admin account (admins can't register through the website)."""
        email = email.strip().lower()
        if len(password) < 8 or not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
            click.echo("Password needs 8+ characters with at least one letter and one number.")
            return
        if User.query.filter_by(email=email).first():
            click.echo("An account with that email already exists.")
            return

        user = User(email=email, role=ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin created: {user.email}")

    @app.cli.command("purge-locations")
    @click.option("--days", default=7, show_default=True, help="Delete rider positions older than this.")
    def purge_locations(days):
        """rider_location grows with every update, so run this now and then to trim old rows."""
        cutoff = utcnow() - timedelta(days=days)
        deleted = RiderLocation.query.filter(RiderLocation.updated_at < cutoff).delete()
        db.session.commit()
        click.echo(f"Deleted {deleted} old location rows.")