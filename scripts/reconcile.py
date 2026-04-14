#!/usr/bin/env python3
"""
Reconcile a bank CSV export against Firefly III transactions.

Finds:
  - Transactions in bank but missing from Firefly
  - Transactions in Firefly but missing from bank (possible duplicates)
  - Date mismatches between matched transactions

Matching is by amount. When multiple transactions share the same amount,
they're counted: 5 bank rows at 100 kr vs 4 Firefly entries → 1 missing.

CSV format (semicolon-separated, Swedish bank export):
  Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo

Usage:
  python3 reconcile.py bank_export.csv --url https://firefly.example.com --token YOUR_PAT

  # Fix dates automatically:
  python3 reconcile.py bank_export.csv --url ... --token ... --auto-fix

  # Or via env vars:
  FIREFLY_URL=... FIREFLY_TOKEN=... python3 reconcile.py bank_export.csv
"""

import argparse
import csv
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

TWO_PLACES = Decimal("0.01")
DATE_PAD_DAYS = 7


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BankRow:
    booking_date: date      # Bokföringsdatum (when bank processed)
    value_date: date        # Valutadatum
    description: str        # Text column
    amount: Decimal         # Signed: negative = expense, positive = income
    abs_amount: Decimal     # Absolute, quantized to 2dp
    direction: str          # "out" or "in"


@dataclass
class FireflyTxn:
    id: str
    date: date
    description: str
    amount: Decimal         # Absolute, quantized to 2dp
    direction: str          # "out" or "in"
    destination: str        # Store/payee name
    source: str             # Source account/name
    tags: list[str]


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def parse_csv(path: str) -> list[BankRow]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            raw_amount = Decimal(row["Belopp"])
            abs_amount = abs(raw_amount).quantize(TWO_PLACES, ROUND_HALF_UP)
            rows.append(BankRow(
                booking_date=date.fromisoformat(row["Bokföringsdatum"]),
                value_date=date.fromisoformat(row["Valutadatum"]),
                description=row["Text"].strip(),
                amount=raw_amount,
                abs_amount=abs_amount,
                direction="out" if raw_amount < 0 else "in",
            ))
    return rows


# ---------------------------------------------------------------------------
# Firefly API
# ---------------------------------------------------------------------------

def fetch_all_transactions(session, base_url: str, start: date, end: date) -> list[FireflyTxn]:
    """Fetch all Firefly transactions in date range, handling pagination."""
    results = []
    page = 1
    while True:
        resp = session.get(
            f"{base_url}/api/v1/transactions",
            params={"start": start.isoformat(), "end": end.isoformat(), "type": "all", "page": page},
        )
        resp.raise_for_status()
        data = resp.json()
        for t in data["data"]:
            splits = t["attributes"]["transactions"]
            if not splits:
                continue
            first = splits[0]
            txn_type = first["type"]
            if txn_type == "transfer":
                continue  # Skip internal transfers

            # Sum splits for the total amount
            total = sum(Decimal(s["amount"]) for s in splits)
            total = total.quantize(TWO_PLACES, ROUND_HALF_UP)

            results.append(FireflyTxn(
                id=t["id"],
                date=date.fromisoformat(first["date"][:10]),
                description=first["description"],
                amount=total,
                direction="out" if txn_type == "withdrawal" else "in",
                destination=first.get("destination_name", ""),
                source=first.get("source_name", ""),
                tags=[tag for s in splits for tag in (s.get("tags") or [])],
            ))

        pagination = data.get("meta", {}).get("pagination", {})
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
    return results


def update_transaction_date(session, base_url: str, txn_id: str, new_date: date):
    """Update a Firefly transaction's date."""
    resp = session.put(
        f"{base_url}/api/v1/transactions/{txn_id}",
        json={"transactions": [{"date": new_date.isoformat()}]},
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def words(s: str) -> set[str]:
    """Extract lowercase words (3+ chars) for fuzzy comparison."""
    return {w.lower() for w in s.replace("/", " ").replace("-", " ").split() if len(w) >= 3}


def similar(a: str, b: str) -> bool:
    """Check if two descriptions share meaningful words."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return False
    return bool(wa & wb)


@dataclass
class MatchGroup:
    key: tuple[str, Decimal]  # (direction, abs_amount)
    bank_rows: list[BankRow]
    firefly_txns: list[FireflyTxn]

    @property
    def bank_count(self) -> int:
        return len(self.bank_rows)

    @property
    def firefly_count(self) -> int:
        return len(self.firefly_txns)

    @property
    def balanced(self) -> bool:
        return self.bank_count == self.firefly_count


def build_match_groups(bank_rows: list[BankRow], firefly_txns: list[FireflyTxn]) -> list[MatchGroup]:
    bank_by_key: dict[tuple[str, Decimal], list[BankRow]] = defaultdict(list)
    firefly_by_key: dict[tuple[str, Decimal], list[FireflyTxn]] = defaultdict(list)

    for row in bank_rows:
        bank_by_key[(row.direction, row.abs_amount)].append(row)
    for txn in firefly_txns:
        firefly_by_key[(txn.direction, txn.amount)].append(txn)

    all_keys = set(bank_by_key.keys()) | set(firefly_by_key.keys())
    groups = []
    for key in sorted(all_keys, key=lambda k: (k[0], k[1])):
        groups.append(MatchGroup(
            key=key,
            bank_rows=bank_by_key.get(key, []),
            firefly_txns=firefly_by_key.get(key, []),
        ))
    return groups


# ---------------------------------------------------------------------------
# Date mismatch detection
# ---------------------------------------------------------------------------

@dataclass
class DateMismatch:
    firefly_txn: FireflyTxn
    bank_row: BankRow


def find_date_mismatches(group: MatchGroup) -> list[DateMismatch]:
    """For balanced groups, pair by closest date and find mismatches."""
    if not group.balanced or group.bank_count == 0:
        return []

    mismatches = []
    # Sort both by date, pair them up
    bank_sorted = sorted(group.bank_rows, key=lambda r: r.booking_date)
    firefly_sorted = sorted(group.firefly_txns, key=lambda t: t.date)

    # Greedy closest-date pairing
    used_firefly = set()
    for br in bank_sorted:
        best_idx = None
        best_diff = None
        for i, ft in enumerate(firefly_sorted):
            if i in used_firefly:
                continue
            diff = abs((ft.date - br.booking_date).days)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_idx = i
        if best_idx is not None:
            used_firefly.add(best_idx)
            ft = firefly_sorted[best_idx]
            if ft.date != br.booking_date:
                mismatches.append(DateMismatch(firefly_txn=ft, bank_row=br))

    return mismatches


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def fmt_amount(direction: str, amount: Decimal) -> str:
    sign = "-" if direction == "out" else "+"
    return f"{sign}{amount}"


def print_report(groups: list[MatchGroup], date_mismatches: list[DateMismatch], auto_fix: bool):
    matched = sum(min(g.bank_count, g.firefly_count) for g in groups)
    missing_in_firefly = []
    extra_in_firefly = []

    for g in groups:
        if g.bank_count > g.firefly_count:
            diff = g.bank_count - g.firefly_count
            missing_in_firefly.append((g, diff))
        elif g.firefly_count > g.bank_count:
            diff = g.firefly_count - g.bank_count
            extra_in_firefly.append((g, diff))

    direction, amount = "—", "—"
    print(f"\n{'='*60}")
    print(f" RECONCILIATION REPORT")
    print(f"{'='*60}\n")

    print(f"  Matched: {matched} transactions\n")

    # --- Missing in Firefly ---
    if missing_in_firefly:
        total_missing = sum(d for _, d in missing_in_firefly)
        print(f"  MISSING IN FIREFLY ({total_missing} transactions)")
        print(f"  These are in the bank but not in Firefly:\n")
        for g, diff in missing_in_firefly:
            direction, amount = g.key
            print(f"  Amount: {fmt_amount(direction, amount)} kr × {diff} missing "
                  f"(bank has {g.bank_count}, Firefly has {g.firefly_count})")
            print(f"  Bank rows:")
            for br in sorted(g.bank_rows, key=lambda r: r.booking_date):
                print(f"    {br.booking_date}  {br.description}")
            if g.firefly_txns:
                print(f"  Firefly entries:")
                for ft in sorted(g.firefly_txns, key=lambda t: t.date):
                    dest = ft.destination or ft.source
                    print(f"    {ft.date}  {ft.description} ({dest})")
            print()
    else:
        print(f"  No missing transactions.\n")

    # --- Extra in Firefly ---
    if extra_in_firefly:
        total_extra = sum(d for _, d in extra_in_firefly)
        print(f"  EXTRA IN FIREFLY ({total_extra} transactions)")
        print(f"  These are in Firefly but not in the bank:\n")
        for g, diff in extra_in_firefly:
            direction, amount = g.key
            print(f"  Amount: {fmt_amount(direction, amount)} kr × {diff} extra "
                  f"(bank has {g.bank_count}, Firefly has {g.firefly_count})")
            print(f"  Firefly entries:")
            txns = sorted(g.firefly_txns, key=lambda t: t.date)
            for i, ft in enumerate(txns):
                dest = ft.destination or ft.source
                dup_marker = ""
                # Check for potential duplicates among the Firefly entries
                for j, other in enumerate(txns):
                    if i != j and similar(ft.destination or ft.description, other.destination or other.description):
                        dup_marker = "  ← possible dup"
                        break
                print(f"    #{ft.id}  {ft.date}  {ft.description} ({dest}){dup_marker}")
            if g.bank_rows:
                print(f"  Bank rows:")
                for br in sorted(g.bank_rows, key=lambda r: r.booking_date):
                    print(f"    {br.booking_date}  {br.description}")
            print()
    else:
        print(f"  No extra transactions in Firefly.\n")

    # --- Date mismatches ---
    if date_mismatches:
        action = "FIXING" if auto_fix else "PROPOSED DATE FIXES"
        print(f"  {action} ({len(date_mismatches)} transactions)\n")
        for dm in sorted(date_mismatches, key=lambda d: d.bank_row.booking_date):
            ft = dm.firefly_txn
            br = dm.bank_row
            dest = ft.destination or ft.source
            status = "FIXED" if auto_fix else "→"
            print(f"    #{ft.id}  {ft.date} {status} {br.booking_date}"
                  f"  {fmt_amount(ft.direction, ft.amount)} kr  {ft.description} ({dest})")
        if not auto_fix:
            print(f"\n  Run with --auto-fix / -a to apply these date changes.")
        print()
    else:
        print(f"  No date mismatches.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Reconcile bank CSV against Firefly III")
    parser.add_argument("csv_file", help="Path to bank CSV export")
    parser.add_argument("--url", default=os.getenv("FIREFLY_URL"), help="Firefly base URL")
    parser.add_argument("--token", default=os.getenv("FIREFLY_TOKEN"), help="Personal Access Token")
    parser.add_argument("--auto-fix", "-a", action="store_true", help="Apply date fixes (default: dry-run)")
    args = parser.parse_args()

    if not args.url or not args.token:
        print("Error: --url and --token required (or set FIREFLY_URL / FIREFLY_TOKEN)")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {args.token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })

    # Parse bank CSV
    print(f"Parsing {args.csv_file}...")
    bank_rows = parse_csv(args.csv_file)
    if not bank_rows:
        print("No transactions found in CSV.")
        sys.exit(0)

    min_date = min(r.booking_date for r in bank_rows)
    max_date = max(r.booking_date for r in bank_rows)
    print(f"  {len(bank_rows)} rows, date range: {min_date} to {max_date}")

    # Fetch Firefly transactions with padding for date drift
    query_start = min_date - timedelta(days=DATE_PAD_DAYS)
    query_end = max_date + timedelta(days=DATE_PAD_DAYS)
    print(f"Fetching Firefly transactions ({query_start} to {query_end})...")
    firefly_txns = fetch_all_transactions(session, base_url, query_start, query_end)
    print(f"  {len(firefly_txns)} transactions found (excluding transfers)")

    # Match
    groups = build_match_groups(bank_rows, firefly_txns)

    # Find date mismatches on balanced groups
    all_date_mismatches = []
    for g in groups:
        all_date_mismatches.extend(find_date_mismatches(g))

    # Apply fixes if requested
    if args.auto_fix and all_date_mismatches:
        print(f"Applying {len(all_date_mismatches)} date fixes...")
        for dm in all_date_mismatches:
            try:
                update_transaction_date(session, base_url, dm.firefly_txn.id, dm.bank_row.booking_date)
            except Exception as e:
                print(f"  ERROR updating #{dm.firefly_txn.id}: {e}")

    # Report
    print_report(groups, all_date_mismatches, args.auto_fix)


if __name__ == "__main__":
    main()
