import os
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .firefly_client import FireflyClient, FireflyError
from .models import Deposit, Receipt, ReceiptItem

app = FastAPI(title="Cash Trace")

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:4173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/response schemas ---

class ValidateRequest(BaseModel):
    firefly_url: str
    token: str


class CreateCategoryRequest(BaseModel):
    name: str


class ReceiptItemSchema(BaseModel):
    name: str
    price: Decimal
    action: Literal["accept", "categorize", "personal"] = "accept"
    category_override: str | None = None


class DepositSchema(BaseModel):
    source: str
    description: str | None = None
    date: date
    amount: Decimal
    category: str
    destination_account_id: str


class ReceiptSchema(BaseModel):
    source: Literal["camera", "upload", "manual"]
    store: str
    description: str | None = None
    date: date
    total: Decimal
    default_category: str
    source_account_id: str
    personal: bool = False
    items: list[ReceiptItemSchema] = []


# --- Endpoints ---

@app.post("/auth/validate")
async def validate_auth(body: ValidateRequest):
    try:
        client = FireflyClient(body.firefly_url, body.token)
        user = await client.validate_token()
    except FireflyError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"valid": True, "user": user}


@app.get("/categories")
async def get_categories(
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)
    return await client.get_categories()


@app.post("/categories")
async def create_category(
    body: CreateCategoryRequest,
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)
    return await client.create_category(body.name)


@app.get("/accounts")
async def get_accounts(
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)
    return await client.get_accounts()


@app.get("/revenue-accounts")
async def get_revenue_accounts(
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)
    return await client.get_revenue_accounts()


@app.get("/expense-accounts")
async def get_expense_accounts(
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)
    return await client.get_expense_accounts()


@app.post("/receipt")
async def submit_receipt(
    body: ReceiptSchema,
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)

    receipt = Receipt(
        source=body.source,
        store=body.store,
        description=body.description,
        date=body.date,
        total=body.total,
        default_category=body.default_category,
        source_account_id=body.source_account_id,
        personal=body.personal,
        items=[
            ReceiptItem(
                name=i.name,
                price=i.price,
                action=i.action,
                category_override=i.category_override,
            )
            for i in body.items
        ],
    )

    transaction_id = await client.push_transaction(receipt)
    return {"firefly_transaction_id": transaction_id}


@app.post("/deposit")
async def submit_deposit(
    body: DepositSchema,
    firefly_url: str,
    authorization: str = Header(...),
):
    token = authorization.removeprefix("Bearer ")
    client = FireflyClient(firefly_url, token)
    deposit = Deposit(
        source=body.source,
        description=body.description,
        date=body.date,
        amount=body.amount,
        category=body.category,
        destination_account_id=body.destination_account_id,
    )
    transaction_id = await client.push_deposit(deposit)
    return {"firefly_transaction_id": transaction_id}
