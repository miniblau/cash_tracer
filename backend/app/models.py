from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal


@dataclass
class ReceiptItem:
    name: str
    price: Decimal  # SEK
    action: Literal["accept", "categorize", "personal"] = "accept"
    category_override: str | None = None  # Firefly category ID


@dataclass
class Deposit:
    source: str       # Revenue account name (created in Firefly if it doesn't exist)
    date: date
    amount: Decimal   # SEK
    category: str     # Firefly category ID
    destination_account_id: str  # Firefly asset account ID


@dataclass
class Receipt:
    source: Literal["camera", "upload", "manual"]
    store: str
    date: date
    total: Decimal  # The actual receipt total paid
    default_category: str  # Firefly category ID
    source_account_id: str  # Firefly asset account ID
    description: str | None = None  # Optional note shown in Firefly; falls back to store name
    personal: bool = False  # If True, entire receipt is tagged personal
    items: list[ReceiptItem] = field(default_factory=list)  # Exception items only

    @property
    def remainder(self) -> Decimal:
        """Amount that goes to the default category (total minus exception items)."""
        return self.total - sum(i.price for i in self.items)
