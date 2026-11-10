"""Database models.

Table and column names follow the ERD. Where the Python attribute has a different name, the ERD
column name is the first argument of db.Column(...), e.g. status = db.Column("request_status", ...).
If your analyst renames a column, change that one string and create a migration.
Anything marked EXTENSION is not in the ERD and can be removed on its own.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .constants import AVAILABILITY_OFFLINE, STATUS_PENDING, VERIFICATION_PENDING
from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column("user_id", db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # EXTENSION: lets an admin disable an account

    customer_profile = db.relationship(
        "CustomerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    rider_profile = db.relationship(
        "RiderProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def profile(self):
        return self.customer_profile or self.rider_profile

    @property
    def full_name(self):
        """Name lives on the customer/rider table (as in the ERD). Admins have no profile row."""
        return self.profile.full_name if self.profile else self.email

    @property
    def phone(self):
        return self.profile.phone if self.profile else None

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class CustomerProfile(db.Model):
    __tablename__ = "customer"

    id = db.Column("customer_id", db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    default_address = db.Column(db.String(255))

    user = db.relationship("User", back_populates="customer_profile")


class RiderProfile(db.Model):
    __tablename__ = "rider"

    id = db.Column("rider_id", db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    vehicle_type = db.Column(db.String(50))
    availability_status = db.Column(db.String(30), nullable=False, default=AVAILABILITY_OFFLINE)

    plate_number = db.Column(db.String(20))  # EXTENSION
    # EXTENSION: admin approval before a rider can accept jobs (pending / approved / rejected)
    verification_status = db.Column(db.String(20), nullable=False, default=VERIFICATION_PENDING)

    user = db.relationship("User", back_populates="rider_profile")


class ServiceCategory(db.Model):
    __tablename__ = "service_category"

    id = db.Column("category_id", db.Integer, primary_key=True)
    name = db.Column("category_name", db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # EXTENSIONS: pricing and ordering
    base_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # True when the rider spends money for the customer, so the customer must enter a budget
    requires_purchase = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class ServiceRequest(db.Model):
    __tablename__ = "delivery_request"

    id = db.Column("request_id", db.Integer, primary_key=True)
    # customer_id / rider_id point at the customer and rider tables (not the user table), as in the ERD
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.customer_id"), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("rider.rider_id"), index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("service_category.category_id"), nullable=False)
    status = db.Column("request_status", db.String(30), nullable=False, default=STATUS_PENDING, index=True)
    instructions = db.Column("task_instructions", db.Text)
    pickup_address = db.Column(db.String(255), nullable=False)
    dropoff_address = db.Column("delivery_address", db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))

    # EXTENSIONS: money
    item_budget = db.Column(db.Numeric(10, 2))
    service_fee = db.Column(db.Numeric(10, 2), nullable=False)
    pickup_lat = db.Column(db.Numeric(10, 7))
    pickup_lng = db.Column(db.Numeric(10, 7))
    dropoff_lat = db.Column(db.Numeric(10, 7))
    dropoff_lng = db.Column(db.Numeric(10, 7))

    customer = db.relationship("CustomerProfile", foreign_keys=[customer_id])
    rider = db.relationship("RiderProfile", foreign_keys=[rider_id])
    category = db.relationship("ServiceCategory")
    history = db.relationship(
        "RequestStatusHistory",
        back_populates="request",
        order_by="RequestStatusHistory.id",
        cascade="all, delete-orphan",
    )


class RequestStatusHistory(db.Model):
    __tablename__ = "request_status_history"

    id = db.Column("history_id", db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("delivery_request.request_id"), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False)
    changed_by_id = db.Column("updated_by_user_id", db.Integer, db.ForeignKey("user.user_id"))
    created_at = db.Column("recorded_at", db.DateTime(timezone=True), default=utcnow, nullable=False)
    note = db.Column("notes", db.Text)

    request = db.relationship("ServiceRequest", back_populates="history")


class RiderLocation(db.Model):
    """One row per position update, so it is a history. The newest row is the current position."""

    __tablename__ = "rider_location"

    id = db.Column("location_id", db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("rider.rider_id"), nullable=False, index=True)
    lat = db.Column("latitude", db.Numeric(10, 7), nullable=False)
    lng = db.Column("longitude", db.Numeric(10, 7), nullable=False)
    updated_at = db.Column("recorded_at", db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class RiderEarning(db.Model):
    __tablename__ = "rider_earnings"

    id = db.Column("earning_id", db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("rider.rider_id"), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey("delivery_request.request_id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    earned_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class RiderDecline(db.Model):
    """EXTENSION: remembers which requests a rider declined, so they don't show up for that rider again."""

    __tablename__ = "rider_decline"
    __table_args__ = (db.UniqueConstraint("request_id", "rider_id", name="uq_decline_request_rider"),)

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("delivery_request.request_id"), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("rider.rider_id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))