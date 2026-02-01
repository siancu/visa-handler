# visa-handler

Extract charges from PostFinance Visa credit card PDF statements into a SQLite database.

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (dependencies are managed automatically)

## Usage

```bash
# Process all PDFs in a directory
./visa-ingester.py -d /path/to/visa.db /path/to/pdfs/

# Process a single PDF
./visa-ingester.py -d /path/to/visa.db statement.pdf

# Show help
./visa-ingester.py --help
```

## Database Schema

```sql
CREATE TABLE transactions (
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
```

## Example Queries

```bash
# Total spending by year
sqlite3 visa.db "SELECT strftime('%Y', entry_date) as year, printf('%.2f', SUM(CASE WHEN is_credit THEN -amount_chf ELSE amount_chf END)) as total FROM transactions GROUP BY year ORDER BY year;"

# Top 10 merchants by spending
sqlite3 visa.db "SELECT merchant, printf('%.2f', SUM(amount_chf)) as total FROM transactions WHERE NOT is_credit GROUP BY merchant ORDER BY SUM(amount_chf) DESC LIMIT 10;"

# Monthly spending for current year
sqlite3 visa.db "SELECT strftime('%Y-%m', entry_date) as month, printf('%.2f', SUM(CASE WHEN is_credit THEN -amount_chf ELSE amount_chf END)) as total FROM transactions WHERE entry_date LIKE '2024%' GROUP BY month ORDER BY month;"

# Search transactions by merchant
sqlite3 visa.db "SELECT entry_date, merchant, amount_chf FROM transactions WHERE merchant LIKE '%SEARCH_TERM%' ORDER BY entry_date DESC;"
```

## Notes

- Duplicate transactions are automatically skipped (based on entry_date, purchase_date, merchant, amount, and card_holder)
- Credits/refunds are marked with `is_credit = 1`
- The script extracts the final CHF amount (after currency conversion and fees)
