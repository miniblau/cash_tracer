#!/usr/bin/env python3
"""
Import transactions from CSV into Firefly III.

CSV format (comma-separated):
  date,source,description,amount,category,tag

  - date:        YYYY-MM-DD
  - source:      store name (withdrawal) or revenue source (deposit)
  - description: optional note (can be empty)
  - amount:      negative = withdrawal, positive = deposit
  - category:    Firefly category name (created if it doesn't exist)
  - tag:         e.g. "personal", "shared", or empty

Usage:
  python3 import_csv.py --url https://firefly.yourdomain.com --token YOUR_PAT transactions.csv

  # Specify which asset account to use (defaults to first found):
  python3 import_csv.py --url ... --token ... --account "Savings" transactions.csv

  Or via env vars:
  FIREFLY_URL=https://... FIREFLY_TOKEN=... python3 import_csv.py transactions.csv
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)


def get_categories(session, base_url):
    """Returns a dict of {name_lower: id} for all existing categories."""
    resp = session.get(f"{base_url}/api/v1/categories")
    resp.raise_for_status()
    return {c["attributes"]["name"].lower(): c["id"] for c in resp.json()["data"]}


def get_asset_accounts(session, base_url):
    """Returns a list of {id, name} for all asset accounts."""
    resp = session.get(f"{base_url}/api/v1/accounts?type=asset")
    resp.raise_for_status()
    return [{"id": a["id"], "name": a["attributes"]["name"]} for a in resp.json()["data"]]


def ensure_category(session, base_url, name, cache):
    """Returns category ID for name, creating it in Firefly if needed."""
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    resp = session.post(f"{base_url}/api/v1/categories", json={"name": name.strip()})
    resp.raise_for_status()
    cat_id = resp.json()["data"]["id"]
    cache[key] = cat_id
    print(f"  Created category: {name.strip()}")
    return cat_id


def build_transaction(row, category_id, account_id):
    amount = Decimal(row["amount"])
    date = row["date"].strip()
    source = row["source"].strip()
    description = row["description"].strip() or source
    tags = [row["tag"].strip()] if row.get("tag", "").strip() else []

    if amount < 0:
        return {
            "transactions": [{
                "type": "withdrawal",
                "date": date,
                "description": description,
                "amount": str(abs(amount)),
                "currency_code": "SEK",
                "category_id": category_id,
                "source_id": account_id,
                "destination_name": source,
                "tags": tags,
            }]
        }
    else:
        return {
            "transactions": [{
                "type": "deposit",
                "date": date,
                "description": description,
                "amount": str(amount),
                "currency_code": "SEK",
                "category_id": category_id,
                "destination_id": account_id,
                "source_name": source,
                "tags": tags,
            }]
        }


def main():
    parser = argparse.ArgumentParser(description="Import CSV transactions into Firefly III")
    parser.add_argument("csv_file", help="Path to the CSV file")
    parser.add_argument("--url", default=os.getenv("FIREFLY_URL"), help="Firefly base URL")
    parser.add_argument("--token", default=os.getenv("FIREFLY_TOKEN"), help="Personal Access Token")
    parser.add_argument("--account", default=os.getenv("FIREFLY_ACCOUNT"), help="Asset account name (defaults to first found)")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't submit")
    args = parser.parse_args()

    if not args.url or not args.token:
        print("Error: --url and --token are required (or set FIREFLY_URL / FIREFLY_TOKEN)")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {args.token}",
        "Accept": "application/json",
    })

    print("Fetching asset accounts...")
    accounts = get_asset_accounts(session, base_url)
    if not accounts:
        print("Error: no asset accounts found in Firefly.")
        sys.exit(1)

    if args.account:
        match = next((a for a in accounts if a["name"].lower() == args.account.lower()), None)
        if not match:
            print(f"Error: account '{args.account}' not found. Available accounts:")
            for a in accounts:
                print(f"  - {a['name']}")
            sys.exit(1)
        account = match
    else:
        account = accounts[0]

    print(f"  Using account: {account['name']} (id={account['id']})")

    print("Fetching existing categories...")
    category_cache = get_categories(session, base_url)
    print(f"  Found {len(category_cache)} categories.")

    with open(args.csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Strip whitespace from field names (handles trailing commas/spaces)
        reader.fieldnames = [name.strip() for name in reader.fieldnames if name and name.strip()]
        rows = [row for row in reader if any(v.strip() for v in row.values() if v)]

    print(f"Importing {len(rows)} transactions{' (dry run)' if args.dry_run else ''}...\n")

    ok = 0
    errors = []

    for i, row in enumerate(rows, 1):
        date = row.get("date", "").strip()
        source = row.get("source", "").strip()
        amount_raw = row.get("amount", "").strip()
        category_name = row.get("category", "").strip()

        if not date or not source or not amount_raw or not category_name:
            errors.append((i, row, "Missing required field"))
            print(f"  [{i}/{len(rows)}] SKIP (missing field): {row}")
            continue

        try:
            category_id = ensure_category(session, base_url, category_name, category_cache)
            payload = build_transaction(row, category_id, account["id"])

            if args.dry_run:
                direction = "OUT" if Decimal(amount_raw) < 0 else "IN"
                print(f"  [{i}/{len(rows)}] {direction} {amount_raw} SEK — {source} ({category_name})")
                ok += 1
                continue

            resp = session.post(f"{base_url}/api/v1/transactions", json=payload)
            resp.raise_for_status()
            tx_id = resp.json()["data"]["id"]
            direction = "OUT" if Decimal(amount_raw) < 0 else "IN"
            print(f"  [{i}/{len(rows)}] OK #{tx_id} {direction} {amount_raw} SEK — {source} ({category_name})")
            ok += 1

        except Exception as e:
            errors.append((i, row, str(e)))
            print(f"  [{i}/{len(rows)}] ERROR: {e} — {row}")

    print(f"\nDone: {ok} imported, {len(errors)} errors.")
    if errors:
        print("\nFailed rows:")
        for i, row, reason in errors:
            print(f"  Row {i}: {reason} — {row}")
        sys.exit(1)


if __name__ == "__main__":
    main()
