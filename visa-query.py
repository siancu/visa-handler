#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Query Visa transactions from SQLite database.

Usage:
    visa-query netflix                  # Search merchant for "netflix"
    visa-query --year 2024              # All transactions from 2024
    visa-query --month 2024-01          # All transactions from January 2024
    visa-query coop --year 2024         # Search + year filter
    visa-query --year 2024 --csv        # Output as CSV
    visa-query --year 2024 --json       # Output as JSON

Environment:
    VISA_DB_PATH    Path to SQLite database (default: visa.db)
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path


def build_query(search: str | None, year: str | None, month: str | None) -> tuple[str, list]:
    """Build SQL query and parameters from filters."""
    conditions = []
    params = []

    if search:
        conditions.append("merchant LIKE ?")
        params.append(f"%{search}%")

    if year:
        conditions.append("strftime('%Y', purchase_date) = ?")
        params.append(year)

    if month:
        conditions.append("strftime('%Y-%m', purchase_date) = ?")
        params.append(month)

    query = "SELECT purchase_date, merchant, amount_chf FROM transactions"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY purchase_date DESC"

    return query, params


def format_table(rows: list[tuple]) -> str:
    """Format rows as aligned table."""
    if not rows:
        return "No transactions found."

    # Column headers
    headers = ["Date", "Merchant", "Amount (CHF)"]

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        widths[0] = max(widths[0], len(str(row[0])))
        widths[1] = max(widths[1], len(str(row[1])))
        widths[2] = max(widths[2], len(f"{row[2]:,.2f}"))

    # Build output
    lines = []

    # Header
    header_line = f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]:>{widths[2]}}"
    lines.append(header_line)
    lines.append("-" * len(header_line))

    # Data rows
    for row in rows:
        amount_str = f"{row[2]:,.2f}"
        lines.append(f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  {amount_str:>{widths[2]}}")

    # Summary
    total = sum(row[2] for row in rows)
    lines.append("-" * len(header_line))
    lines.append(f"{'Total':<{widths[0]}}  {'':<{widths[1]}}  {total:>{widths[2]},.2f}")
    lines.append(f"{len(rows)} transaction(s)")

    return "\n".join(lines)


def format_csv(rows: list[tuple]) -> str:
    """Format rows as CSV."""
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["purchase_date", "merchant", "amount_chf"])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().rstrip()


def format_json(rows: list[tuple]) -> str:
    """Format rows as JSON."""
    data = [
        {"purchase_date": row[0], "merchant": row[1], "amount_chf": row[2]}
        for row in rows
    ]
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Query Visa transactions from SQLite database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    visa-query netflix                  Search for "netflix" in merchant
    visa-query --year 2024              All transactions from 2024
    visa-query --month 2024-01          January 2024 transactions
    visa-query coop --year 2024 --csv   Combined filters with CSV output
        """,
    )
    parser.add_argument(
        "search",
        nargs="?",
        help="Search term for merchant name (case-insensitive)",
    )
    parser.add_argument(
        "--year",
        help="Filter by year (e.g., 2024)",
    )
    parser.add_argument(
        "--month",
        help="Filter by month (e.g., 2024-01)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        dest="output_csv",
        help="Output as CSV",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output as JSON",
    )
    parser.add_argument(
        "-d", "--database",
        default=os.environ.get("VISA_DB_PATH", "visa.db"),
        help="SQLite database file (default: $VISA_DB_PATH or visa.db)",
    )

    # Show help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    db_path = Path(args.database)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    # Build and execute query
    query, params = build_query(args.search, args.year, args.month)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    # Output in requested format
    if args.output_csv:
        print(format_csv(rows))
    elif args.output_json:
        print(format_json(rows))
    else:
        print(format_table(rows))

    return 0


if __name__ == "__main__":
    sys.exit(main())
