#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["pdfplumber"]
# ///
"""
Extract charges from PostFinance Visa PDF statements and store in SQLite.

Usage:
    uv run visa-ingester.py                                    # Process all PDFs in current dir
    uv run visa-ingester.py /path/to/pdfs/                     # Process all PDFs in directory
    uv run visa-ingester.py "VISA - 2024-08.pdf"               # Process specific file
    uv run visa-ingester.py -d custom.db /path/to/pdfs/        # Use custom database name
"""

import argparse
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pdfplumber

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date DATE NOT NULL,
    purchase_date DATE NOT NULL,
    merchant TEXT NOT NULL,
    category TEXT,
    amount_chf REAL NOT NULL,
    is_credit BOOLEAN NOT NULL,
    card_holder TEXT NOT NULL,
    source_file TEXT NOT NULL,
    UNIQUE(entry_date, purchase_date, merchant, amount_chf, card_holder)
);

CREATE INDEX IF NOT EXISTS idx_entry_date ON transactions(entry_date);
CREATE INDEX IF NOT EXISTS idx_purchase_date ON transactions(purchase_date);
CREATE INDEX IF NOT EXISTS idx_merchant ON transactions(merchant);
CREATE INDEX IF NOT EXISTS idx_card_holder ON transactions(card_holder);
"""


@dataclass
class Transaction:
    entry_date: str
    purchase_date: str
    merchant: str
    category: str
    amount_chf: float
    is_credit: bool
    card_holder: str
    source_file: str


def parse_date(date_str: str) -> str:
    """Convert DD.MM.YY to YYYY-MM-DD format."""
    try:
        dt = datetime.strptime(date_str, "%d.%m.%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def parse_amount(amount_str: str) -> tuple[float, bool]:
    """Parse amount string, return (amount, is_credit)."""
    cleaned = amount_str.replace("'", "").replace(",", "").strip()
    is_credit = cleaned.startswith("-")
    amount = abs(float(cleaned))
    return amount, is_credit


def extract_transactions_from_pdf(pdf_path: Path) -> list[Transaction]:
    """Extract all transactions from a PostFinance Visa PDF."""
    transactions = []
    current_card_holder = ""

    # Patterns
    transaction_pattern = re.compile(
        r"^(\d{2}\.\d{2}\.\d{2})\s+(\d{2}\.\d{2}\.\d{2})\s+(.+?)\s+(-?[\d']+\.\d{2})$"
    )
    card_holder_pattern = re.compile(
        r"Transactions PostFinance Visa.*?/\s*(.+)$"
    )
    # Lines to skip
    skip_patterns = [
        r"^Amount carried forward",
        r"^Exchange rate",
        r"^Processing surcharge",
        r"^Surcharge in CHF",
        r"^\s*(USD|EUR|RON|GBP|CHF)\s+[\d.]+",
    ]
    skip_regex = re.compile("|".join(skip_patterns), re.IGNORECASE)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Check for card holder section
                holder_match = card_holder_pattern.search(line)
                if holder_match:
                    current_card_holder = holder_match.group(1).strip()
                    i += 1
                    continue

                # Skip irrelevant lines
                if skip_regex.search(line):
                    i += 1
                    continue

                # Try to match a transaction line
                tx_match = transaction_pattern.match(line)
                if tx_match:
                    entry_date = parse_date(tx_match.group(1))
                    purchase_date = parse_date(tx_match.group(2))
                    merchant = tx_match.group(3).strip()
                    amount, is_credit = parse_amount(tx_match.group(4))

                    # Look ahead for category on next line
                    category = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if (
                            next_line
                            and not transaction_pattern.match(next_line)
                            and not skip_regex.search(next_line)
                            and not re.match(r"^\d{2}\.\d{2}\.\d{2}", next_line)
                            and not card_holder_pattern.search(next_line)
                            and not next_line.startswith("Total")
                            and not next_line.startswith("Transaction total")
                            and not next_line.startswith("Card account")
                            and not next_line.startswith("Invoice date")
                            and not next_line.startswith("Page ")
                            and not re.match(r"^(USD|EUR|RON|GBP)\s+[\d.]+", next_line)
                        ):
                            category = next_line
                            i += 1

                    transactions.append(Transaction(
                        entry_date=entry_date,
                        purchase_date=purchase_date,
                        merchant=merchant,
                        category=category,
                        amount_chf=amount,
                        is_credit=is_credit,
                        card_holder=current_card_holder,
                        source_file=pdf_path.name,
                    ))

                i += 1

    return transactions


def init_database(db_path: Path) -> sqlite3.Connection:
    """Create database and schema if needed."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_transactions(conn: sqlite3.Connection, transactions: list[Transaction]) -> tuple[int, int]:
    """Insert transactions into database. Returns (imported, skipped)."""
    cursor = conn.cursor()
    imported = 0
    skipped = 0

    for tx in transactions:
        try:
            cursor.execute(
                """
                INSERT INTO transactions
                (entry_date, purchase_date, merchant, category, amount_chf, is_credit, card_holder, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx.entry_date,
                    tx.purchase_date,
                    tx.merchant,
                    tx.category or None,
                    tx.amount_chf,
                    tx.is_credit,
                    tx.card_holder,
                    tx.source_file,
                ),
            )
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    return imported, skipped


def print_summary(conn: sqlite3.Connection):
    """Print database summary."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(CASE WHEN is_credit THEN -amount_chf ELSE amount_chf END) FROM transactions")
    total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT MIN(entry_date), MAX(entry_date) FROM transactions")
    min_date, max_date = cursor.fetchone()

    print(f"\nDatabase summary:")
    print(f"  Total transactions: {count}")
    print(f"  Total amount: {total:,.2f} CHF")
    print(f"  Date range: {min_date} to {max_date}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract Visa PDF statements into SQLite database"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=".",
        help="PDF file or directory containing PDFs (default: current directory)",
    )
    parser.add_argument(
        "-d", "--database",
        default="visa.db",
        help="SQLite database file (default: visa.db)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    db_path = Path(args.database)

    # Collect PDF files
    if input_path.is_file():
        pdf_files = [input_path]
    elif input_path.is_dir():
        pdf_files = sorted(input_path.glob("*.pdf"))
    else:
        print(f"Error: {input_path} not found")
        return 1

    if not pdf_files:
        print(f"No PDF files found in {input_path}")
        return 1

    # Initialize database
    print(f"Database: {db_path}")
    conn = init_database(db_path)

    # Process each PDF
    print(f"Processing {len(pdf_files)} PDF file(s)...")
    total_imported = 0
    total_skipped = 0

    for pdf_file in pdf_files:
        transactions = extract_transactions_from_pdf(pdf_file)
        imported, skipped = insert_transactions(conn, transactions)
        total_imported += imported
        total_skipped += skipped

        # Calculate net total for this file
        net_total = sum(tx.amount_chf * (-1 if tx.is_credit else 1) for tx in transactions)
        status = f"  {pdf_file.name}: {imported} imported"
        if skipped:
            status += f", {skipped} skipped"
        status += f" ({net_total:.2f} CHF)"
        print(status)

    print(f"\nTotal: {total_imported} transactions imported, {total_skipped} skipped")
    print_summary(conn)
    conn.close()
    return 0


if __name__ == "__main__":
    exit(main())
