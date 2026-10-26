# Ingesting Belgian KBC Bank Statements

Paslood features native, zero-configuration support for **KBC Bank CSV statement exports**.

---

## How to Export from KBC Touch / KBC Mobile

1. Log in to **KBC Touch** (web) or **KBC Mobile**.
2. Navigate to your checking account (`Zichtrekening`).
3. Click **Historiek exporteren** (Export History) -> Select **CSV-formaat**.
4. Download the `.csv` file.

---

## File Format Specs Handled Automatically

- **Encoding**: ISO-8859-1 (Latin-1) / Windows-1252
- **Delimiter**: Semicolon (`;`)
- **Number Formats**: European format (e.g., `-579,68` or `1.452,04`)
- **Date Format**: `DD/MM/YYYY`

---

## Automated Discovery

When you upload or ingest your KBC CSV:
1. **Liquid Checking Balance**: Extracted from the most recent transaction's `Saldo` column and assigned to the Cash asset.
2. **Liabilities Discovery**: Scans descriptions for loan references (`WONINGKREDIET` and `FLEX BUDGET`) and automatically records active debts.
3. **Monthly Debt Servicing**: Sums recurring mortgage repayments and consumer credit payments.
4. **Income Extraction**: Averages recurring salary deposits from your employer.
5. **Interactive Re-Bucketing**: Displays all transactions in the Web Dashboard, allowing you to re-bucket any transaction and save custom categorization rules.
