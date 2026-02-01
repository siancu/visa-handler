# visa-handler

A tool to extract credit card transactions from PostFinance Visa PDF statements into SQLite.

## Project Structure

```
visa-ingester.py   # Main script: PDF → SQLite (executable, uses uv shebang)
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

## Common Tasks

### Add new statements
```bash
./visa-ingester.py -d /path/to/visa.db /path/to/pdfs/
```

### Query the database
```bash
sqlite3 /path/to/visa.db "SELECT * FROM transactions WHERE merchant LIKE '%NETFLIX%';"
```

### Rebuild database from scratch
```bash
rm /path/to/visa.db && ./visa-ingester.py -d /path/to/visa.db /path/to/pdfs/
```
