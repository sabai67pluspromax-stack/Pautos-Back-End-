from decimal import Decimal

from .extensions import db
from .models import ServiceCategory

# (name, description, base fee in PHP, rider spends money for the customer)
DEFAULT_CATEGORIES = [
    ("Water Delivery", "Refill or buy water containers delivered to you.", "50.00", True),
    ("Grocery Shopping", "A rider shops from your list and delivers it.", "80.00", True),
    ("Bill Payment", "A rider pays your bill at an outlet and brings the receipt.", "60.00", True),
    ("Parcel Pickup and Delivery", "Pick up an item from one place and deliver it to another.", "60.00", False),
    ("Other Errand", "Anything else you need done. Describe it clearly.", "70.00", False),
]


def seed_categories():
    """Insert the starter categories, only when the table is empty. Returns how many were added."""
    if ServiceCategory.query.count() > 0:
        return 0
    for order, (name, desc, fee, purchase) in enumerate(DEFAULT_CATEGORIES, start=1):
        db.session.add(
            ServiceCategory(
                name=name, description=desc, base_fee=Decimal(fee),
                requires_purchase=purchase, sort_order=order,
            )
        )
    db.session.commit()
    return len(DEFAULT_CATEGORIES)