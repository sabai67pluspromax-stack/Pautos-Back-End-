"""The app's fixed vocabulary in one place.

Need a new status, vehicle type or role? Change it here instead of hunting through routes.
The database stores these as plain text (VARCHAR), so editing a list never needs a migration.
"""

# Roles. The ERD lists customer and rider; admin is an extension.
ROLE_CUSTOMER = "customer"
ROLE_RIDER = "rider"
ROLE_ADMIN = "admin"
SELF_REGISTER_ROLES = (ROLE_CUSTOMER, ROLE_RIDER)  # what the register form offers

# Request statuses (same set as the ERD). Shown to people in Title Case ("picked_up" -> "Picked Up").
STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"  # in the ERD but unused: declines are tracked per rider (rider_decline table)
STATUS_PICKED_UP = "picked_up"
STATUS_IN_TRANSIT = "in_transit"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

ALL_STATUSES = (
    STATUS_PENDING,
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_PICKED_UP,
    STATUS_IN_TRANSIT,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
)

# A rider currently owns the request and is working on it
ACTIVE_STATUSES = (STATUS_ACCEPTED, STATUS_PICKED_UP, STATUS_IN_TRANSIT)
# Still moving (waiting for a rider, or in progress). Customer pages keep refreshing for these.
OPEN_STATUSES = (STATUS_PENDING,) + ACTIVE_STATUSES
# Statuses from which a customer may still cancel
CUSTOMER_CANCELLABLE = (STATUS_PENDING,)
ADMIN_CANCELLABLE = OPEN_STATUSES
ADMIN_REOPENABLE = ACTIVE_STATUSES

# What a rider may do next from each status. Add a status or a branch here and the buttons follow.
RIDER_FLOW = {
    STATUS_ACCEPTED: [STATUS_PICKED_UP],
    STATUS_PICKED_UP: [STATUS_IN_TRANSIT],
    STATUS_IN_TRANSIT: [STATUS_COMPLETED],
}
RIDER_ACTION_LABELS = {
    STATUS_PICKED_UP: "I've picked it up / bought it",
    STATUS_IN_TRANSIT: "I'm on my way to deliver",
    STATUS_COMPLETED: "Delivered. Mark as completed",
}

RIDER_RELEASABLE = (STATUS_ACCEPTED,)
RELEASE_REASONS = (
    ("vehicle", "Vehicle problem"),
    ("emergency", "Personal emergency"),
    ("location", "Can't reach the location"),
    ("other", "Other reason"),
)

# Reaching this status finishes the job: completed_at is set, an earnings row is created
FINAL_STATUS = STATUS_COMPLETED

# Rider availability (rider.availability_status)
AVAILABILITY_OFFLINE = "offline"
AVAILABILITY_AVAILABLE = "available"
AVAILABILITY_BUSY = "busy"  # set automatically while on a job
RIDER_SELECTABLE_AVAILABILITY = (AVAILABILITY_AVAILABLE, AVAILABILITY_OFFLINE)

# Rider verification (extension: not in the ERD)
VERIFICATION_PENDING = "pending"
VERIFICATION_APPROVED = "approved"
VERIFICATION_REJECTED = "rejected"
VERIFICATION_ORDER = {VERIFICATION_PENDING: 0, VERIFICATION_APPROVED: 1, VERIFICATION_REJECTED: 2}

# Vehicles
VEHICLE_TYPES = (
    ("motorcycle", "Motorcycle"),
    ("bicycle", "Bicycle"),
    ("car", "Car"),
    ("walker", "On foot"),
)
PLATE_REQUIRED_VEHICLES = ("motorcycle", "car")