from decimal import Decimal

import httpx

from .models import Deposit, Receipt


class FireflyError(Exception):
    pass


class FireflyClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        if not token:
            raise FireflyError("Token is required")
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def validate_token(self) -> str:
        """Returns the username if the token is valid, raises FireflyError otherwise."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/about/user", headers=self.headers
                )
        except httpx.ConnectError:
            raise FireflyError("Could not reach Firefly at that URL")
        if resp.status_code == 401:
            raise FireflyError("Invalid token")
        resp.raise_for_status()
        return resp.json()["data"]["attributes"]["email"]

    async def get_categories(self) -> list[dict]:
        """Returns [{ id, name }] for all categories."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/categories", headers=self.headers
            )
        resp.raise_for_status()
        return [
            {"id": c["id"], "name": c["attributes"]["name"]}
            for c in resp.json()["data"]
        ]

    async def create_category(self, name: str) -> dict:
        """Creates a new category and returns { id, name }."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/categories",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"name": name},
            )
        resp.raise_for_status()
        data = resp.json()["data"]
        return {"id": data["id"], "name": data["attributes"]["name"]}

    async def get_accounts(self) -> list[dict]:
        """Returns [{ id, name }] for all asset accounts."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/accounts?type=asset", headers=self.headers
            )
        resp.raise_for_status()
        return [
            {"id": a["id"], "name": a["attributes"]["name"]}
            for a in resp.json()["data"]
        ]

    async def get_revenue_accounts(self) -> list[dict]:
        """Returns [{ id, name }] for all revenue accounts (known income sources)."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/accounts?type=revenue", headers=self.headers
            )
        resp.raise_for_status()
        return [
            {"id": a["id"], "name": a["attributes"]["name"]}
            for a in resp.json()["data"]
        ]

    async def get_expense_accounts(self) -> list[dict]:
        """Returns [{ id, name }] for all expense accounts (known stores/payees)."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/accounts?type=expense", headers=self.headers
            )
        resp.raise_for_status()
        return [
            {"id": a["id"], "name": a["attributes"]["name"]}
            for a in resp.json()["data"]
        ]

    async def push_transaction(self, receipt: Receipt) -> str:
        """Submits a receipt to Firefly. Returns the transaction ID."""
        splits = _build_splits(receipt)
        payload: dict = {
            "transactions": splits,
            "error_if_duplicate_hash": False,
        }
        if len(splits) > 1:
            payload["group_title"] = receipt.store
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/transactions",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["data"]["id"]

    async def push_deposit(self, deposit: Deposit) -> str:
        """Submits an income deposit to Firefly. Returns the transaction ID."""
        payload = {
            "transactions": [{
                "type": "deposit",
                "date": deposit.date.isoformat(),
                "description": deposit.description or deposit.source,
                "amount": str(deposit.amount),
                "currency_code": "SEK",
                "category_id": deposit.category,
                "source_name": deposit.source,
                "destination_id": deposit.destination_account_id,
                "tags": ["personal"],
            }]
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/transactions",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["data"]["id"]


def _build_splits(receipt: Receipt) -> list[dict]:
    """Builds Firefly transaction splits from a receipt.

    The remainder (total minus exception items) goes to the default category.
    Exception items are grouped by (category, personal) and split out separately.
    """
    date_str = receipt.date.isoformat()
    store = receipt.store
    description = receipt.description or store
    source_account_id = receipt.source_account_id

    splits = []

    def tags_for(is_personal: bool) -> list[str]:
        return ["personal"] if (receipt.personal or is_personal) else ["shared"]

    # Remainder → default category
    remainder = receipt.remainder
    if remainder > 0:
        splits.append(_split(description, store, date_str, remainder, receipt.default_category, source_account_id, tags=tags_for(False)))

    # Exception items grouped by (category, is_personal)
    groups: dict[tuple[str, bool], Decimal] = {}
    for item in receipt.items:
        cat = item.category_override or receipt.default_category
        is_personal = item.action == "personal"
        key = (cat, is_personal)
        groups[key] = groups.get(key, Decimal("0")) + item.price

    for (cat_id, is_personal), amount in groups.items():
        splits.append(_split(description, store, date_str, amount, cat_id, source_account_id, tags=tags_for(is_personal)))

    return splits


def _split(description: str, destination_name: str, date: str, amount: Decimal, category_id: str, source_account_id: str, tags: list[str]) -> dict:
    return {
        "type": "withdrawal",
        "date": date,
        "description": description,
        "amount": str(amount),
        "currency_code": "SEK",
        "category_id": category_id,
        "source_id": source_account_id,
        "destination_name": destination_name,
        "tags": tags,
    }
