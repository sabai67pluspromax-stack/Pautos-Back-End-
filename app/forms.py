import re
from flask_wtf.file import FileAllowed, FileField
from decimal import Decimal
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
    Regexp,
)

from .constants import PLATE_REQUIRED_VEHICLES, SELF_REGISTER_ROLES, VEHICLE_TYPES
from .models import CustomerProfile, RiderProfile, ServiceCategory, User

ROLE_CHOICES = [(role, role.title()) for role in SELF_REGISTER_ROLES]
VEHICLE_CHOICES = [("", "Select...")] + list(VEHICLE_TYPES)


def normalize_ph_phone(raw):
    """Return +639XXXXXXXXX or None if the number isn't a valid PH mobile."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if re.fullmatch(r"09\d{9}", digits):
        return "+63" + digits[1:]
    if re.fullmatch(r"\+639\d{9}", digits):
        return digits
    if re.fullmatch(r"639\d{9}", digits):
        return "+" + digits
    return None


def phone_in_use(phone, exclude_user_id=None):
    """Phones live on the customer and rider tables, so check both."""
    for model in (CustomerProfile, RiderProfile):
        query = model.query.filter(model.phone == phone)
        if exclude_user_id is not None:
            query = query.filter(model.user_id != exclude_user_id)
        if query.first():
            return True
    return False


def strong_password(form, field):
    pw = field.data or ""
    if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        raise ValidationError("Password must contain at least one letter and one number.")


class RegisterForm(FlaskForm):
    role = SelectField("I want to register as", choices=ROLE_CHOICES, validators=[DataRequired()])
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Mobile number", validators=[DataRequired(), Length(max=30)])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=128), strong_password]
    )
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")]
    )

    # Rider-only fields
    vehicle_type = SelectField("Vehicle type", choices=VEHICLE_CHOICES, validators=[Optional()])
    plate_number = StringField("Plate number", validators=[Optional(), Length(max=20)])

    phone_normalized = None

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("That email is already registered.")

    def validate_phone(self, field):
        normalized = normalize_ph_phone(field.data)
        if not normalized:
            raise ValidationError("Enter a valid PH mobile number (e.g. 09171234567).")
        if phone_in_use(normalized):
            raise ValidationError("That mobile number is already registered.")
        self.phone_normalized = normalized

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if self.role.data == "rider":
            if not self.vehicle_type.data:
                self.vehicle_type.errors.append("Please select your vehicle type.")
                ok = False
            elif self.vehicle_type.data in PLATE_REQUIRED_VEHICLES and not (self.plate_number.data or "").strip():
                self.plate_number.errors.append("Plate number is required for this vehicle.")
                ok = False
        return ok


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me logged in")


class BaseProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150)])
    phone = StringField("Mobile number", validators=[DataRequired(), Length(max=30)])

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.phone_normalized = None

    def validate_phone(self, field):
        normalized = normalize_ph_phone(field.data)
        if not normalized:
            raise ValidationError("Enter a valid PH mobile number (e.g. 09171234567).")
        if phone_in_use(normalized, exclude_user_id=self.user.id):
            raise ValidationError("That mobile number is already used by another account.")
        self.phone_normalized = normalized


class CustomerProfileForm(BaseProfileForm):
    default_address = StringField("Default address", validators=[Optional(), Length(max=255)])


class RiderProfileForm(BaseProfileForm):
    vehicle_type = SelectField(
        "Vehicle type",
        choices=VEHICLE_CHOICES,
        validators=[DataRequired(message="Please select your vehicle type.")],
    )
    plate_number = StringField("Plate number", validators=[Optional(), Length(max=20)])

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if self.vehicle_type.data in PLATE_REQUIRED_VEHICLES and not (self.plate_number.data or "").strip():
            self.plate_number.errors.append("Plate number is required for this vehicle.")
            ok = False
        return ok


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField(
        "New password", validators=[DataRequired(), Length(min=8, max=128), strong_password]
    )
    confirm_password = PasswordField(
        "Confirm new password", validators=[DataRequired(), EqualTo("new_password", "Passwords must match.")]
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def validate_current_password(self, field):
        if not self.user.check_password(field.data):
            raise ValidationError("Current password is incorrect.")

class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        "New password", validators=[DataRequired(), Length(min=8, max=128), strong_password]
    )
    confirm_password = PasswordField(
        "Confirm new password", validators=[DataRequired(), EqualTo("new_password", "Passwords must match.")]
    )

class NewRequestForm(FlaskForm):
    category_id = SelectField("Service", coerce=int, validators=[DataRequired()])
    instructions = TextAreaField("Task instructions", validators=[DataRequired(), Length(min=5, max=1000)])
    pickup_address = StringField(
        "Pickup / store location (where the rider goes first)", validators=[DataRequired(), Length(max=255)]
    )
    dropoff_address = StringField("Delivery address", validators=[DataRequired(), Length(max=255)])
    item_budget = DecimalField(
        "Budget for items or bill amount (PHP)",
        places=2,
        validators=[Optional(), NumberRange(min=0, max=50000)],
    )
    pickup_lat = DecimalField(places=7, validators=[Optional(), NumberRange(min=-90, max=90)])
    pickup_lng = DecimalField(places=7, validators=[Optional(), NumberRange(min=-180, max=180)])
    dropoff_lat = DecimalField(places=7, validators=[Optional(), NumberRange(min=-90, max=90)])
    dropoff_lng = DecimalField(places=7, validators=[Optional(), NumberRange(min=-180, max=180)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories = (
            ServiceCategory.query.filter_by(is_active=True).order_by(ServiceCategory.sort_order).all()
        )
        self.category_id.choices = [(c.id, c.name) for c in self.categories]

    def selected_category(self):
        return next((c for c in self.categories if c.id == self.category_id.data), None)

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        category = self.selected_category()
        if ok and category and category.requires_purchase and self.item_budget.data is None:
            self.item_budget.errors.append("Please enter the budget or amount for this service.")
            ok = False
        for lat, lng in ((self.pickup_lat, self.pickup_lng), (self.dropoff_lat, self.dropoff_lng)):
            if (lat.data is None) != (lng.data is None):
                lat.errors.append("The map pin is incomplete. Please place it again.")
                ok = False
        if self.pickup_lat.data is None or self.pickup_lng.data is None:
            self.pickup_lat.errors.append("Please pin the pickup place on the map so nearby riders can see your request.")
            ok = False        
        return ok

    def coordinates(self):
        values = {}
        for name in ("pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng"):
            value = getattr(self, name).data
            values[name] = None if value is None else value.quantize(Decimal("0.0000001"))
        return values

class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=100)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    base_fee = DecimalField(
        "Service fee (PHP)", places=2, validators=[InputRequired(), NumberRange(min=0, max=5000)]
    )
    requires_purchase = BooleanField("The rider spends money for the customer (customer must enter a budget)")
    sort_order = IntegerField("Display order", default=0, validators=[Optional(), NumberRange(min=0, max=1000)])

    def __init__(self, *args, category=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category  # the category being edited, or None when creating

    def validate_name(self, field):
        query = ServiceCategory.query.filter(func.lower(ServiceCategory.name) == field.data.strip().lower())
        if self.category is not None:
            query = query.filter(ServiceCategory.id != self.category.id)
        if query.first():
            raise ValidationError("A category with that name already exists.")

class GcashQrForm(FlaskForm):
    qr_image = FileField(
        "GCash QR image (PNG, JPG or WebP)",
        validators=[FileAllowed(["png", "jpg", "jpeg", "webp"], "Please choose a PNG, JPG or WebP image.")],
    )
    gcash_name = StringField("Name shown on your GCash", validators=[Optional(), Length(max=100)])

class PaymentForm(FlaskForm):
    method = SelectField(
        "How will you pay?",
        choices=[("cash", "Cash to the rider"), ("gcash_qr", "GCash: scan the rider's QR code")],
        validators=[DataRequired()],
    )
    reference = StringField(
        "GCash reference number (optional)",
        validators=[Optional(), Length(max=40), Regexp(r"^[A-Za-z0-9 \-]*$", message="Letters, numbers, spaces and dashes only.")],
    )