# visa-handler

A tool to extract credit card transactions from PostFinance Visa PDF statements into SQLite.

## Project Structure

```
visa-ingester.py   # PDF → SQLite ingestion (executable, uses uv shebang)
visa-query.py      # Query transactions from SQLite (executable, uses uv shebang)
```

## Key Details

- **PDF Format**: PostFinance Visa Classic Card invoices with tabular transaction data
- **Extraction**: Uses `pdfplumber` to parse PDF text and regex to match transaction lines
- **Database**: SQLite with a single `transactions` table
- **Deduplication**: UNIQUE constraint on (entry_date, purchase_date, merchant, amount_chf, card_holder)

## Transaction Pattern

PDF transaction lines follow this format:
```
DD.MM.YY DD.MM.YY MERCHANT_NAME LOCATION COUNTRY    AMOUNT
```
- First date: entry date (posting date)
- Second date: purchase date
- Category appears on the following line
- Foreign currency transactions have sub-lines for exchange rate and processing surcharge (skipped)

## Environment Variables

- `VISA_DB_PATH`: Path to SQLite database (default: `visa.db`)

## Common Tasks

### Add new statements
```bash
# Using environment variable
export VISA_DB_PATH=/path/to/visa.db
./visa-ingester.py /path/to/pdfs/

# Or using -d flag
./visa-ingester.py -d /path/to/visa.db /path/to/pdfs/
```

### Query transactions
```bash
./visa-query.py netflix                  # Search merchant
./visa-query.py --year 2024              # Filter by year
./visa-query.py --month 2024-01          # Filter by month
./visa-query.py coop --year 2024 --csv   # Combined filters, CSV output
./visa-query.py --year 2024 --json       # JSON output
```

### Rebuild database from scratch
```bash
rm /path/to/visa.db && ./visa-ingester.py -d /path/to/visa.db /path/to/pdfs/
```
