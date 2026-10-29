# Architecture Plan: Multi-Bank & Position CSV Ingestion (KBC Credit Card, KBC Position Overview & Bunq)

| Metadata | Details |
| :--- | :--- |
| **Issue** | [#37](https://github.com/tiwu/paslood/issues/37) |
| **Status** | `Approved` |
| **Branch** | `feature/issue-37-featingestion-support-kbc-credit-card-kb` |
| **Author** | Antigravity Agent |
| **Date** | 2026-10-28 |

---

## 1. Problem Statement & User Value

Users uploading CSV exports from `./csv/` encounter silent failures or empty/bogus imports when uploading:
1. **KBC Credit Card Statements (`export_KBC-Kredietkaart_*.csv`)**: Semicolon-delimited with classic Mac `\r` line endings and columns `kredietkaart;kaarthouder;...;bedrag in EUR;...;Handelaar;locatie;land;toelichting`. Currently routed to `KbcCsvGateway`, which expects `Rekeningnummer;Datum;Bedrag;Omschrijving`, yielding 0 valid transactions.
2. **KBC Easy Invest / Pension Position Overviews (`Positie-overzicht op *.csv`)**: Starts with `sep=;` and 8 metadata lines before the actual header (`Productklasse;Waardeinfo/ISIN;Naam product;Aantal;...;Huidige waarde in EUR;...`). Currently routed to `GenericCsvGateway`, which parses `sep=;` as the CSV header and creates 11 bogus `€ 0.00` assets.
3. **Bunq Checking & Savings Statements (`*_bunq-afschrift.csv`)**: Comma-delimited double-quoted exports (`"Date","Interest Date","Amount","Account","Counterparty","Name","Description"`) with European decimal formatting (`"250,00"`, `"1.000,00"`, `"-1,80"`).

---

## 2. Clean Architecture Impact Analysis

### 2.1 Domain Layer (`src/paslood/domain/`)
- No new framework dependencies. Existing `Asset`, `AssetClass`, `Transaction`, `Category`, and `Money` value objects are used.

### 2.2 Use Case Layer (`src/paslood/use_cases/`)
- **`src/paslood/use_cases/categorize_transactions.py`**:
  - Enhance default categorization heuristics to recognize internal transfers (`spaarrekening`, `eigen rekening`, `bunq payday`) and safely match patterns containing literal `*` characters.

### 2.3 Adapters Layer (`src/paslood/adapters/`)
- **`src/paslood/adapters/ingestion/kbc_csv.py`**:
  - Normalize `\r\n` and `\r` line endings.
  - Detect KBC Credit Card header (`kredietkaart` and `bedrag in EUR`).
  - Parse `bedrag in EUR` (handling foreign currency rows like MGA), skip direct debit settlement rows (`TERUGBETALING VIA JE KBC FLEX BUDGET`), and include a per-row occurrence index in the deterministic ID hash so legitimate same-day identical refunds/charges are preserved while re-uploads remain idempotent.
- **`src/paslood/adapters/ingestion/generic_csv.py`**:
  - Normalize line endings and skip `sep=;` + preamble lines in KBC `Positie-overzicht` exports until the `Productklasse;Waardeinfo/ISIN` header row.
  - Parse Belgian decimal formatting (`12.038,76` -> `Decimal("12038.76")`).
  - Map `beleggingsfonds` with `PENSION` in the name to `AssetClass.PENSION` (otherwise `AssetClass.EQUITY`), and `spaarrekening` to `AssetClass.CASH`.
  - Extract the IBAN from `spaarrekening` rows (`BE68 0000 0000 1234`) and assign `id="kbc-checking-BE68000000001234"` so uploading both the KBC savings CSV and the position overview updates the same cash asset without double-counting.
  - Validate headers in `_parse_generic` so unrecognized transaction CSVs raise a clear `ValueError` instead of creating `€ 0.00` dummy assets.
- **`src/paslood/adapters/ingestion/bunq_csv.py`** (New):
  - Implement `BunqCsvGateway` parsing `"Date","Interest Date","Amount","Account","Counterparty","Name","Description"`.
  - Parse European decimal amounts (`1.000,00`, `-1,80`) into `Money(Decimal, "EUR")`.
  - Generate deterministic transaction IDs (`bunq-tx-<hash>`) with a per-row occurrence index so identical same-day purchases (e.g., two identical €3.50 merchant charge rows) are both preserved while re-uploads remain idempotent.
- **`src/paslood/adapters/repositories/local_db.py`**:
  - Clean up any legacy bogus `gen-*` assets with `0` balance during initialization/save.

### 2.4 Delivery Layer (`src/paslood/delivery/`)
- **`src/paslood/delivery/web/dependencies.py` & `app.py`**:
  - Register `bunq_gateway = BunqCsvGateway()` in `AppContainer`.
- **`src/paslood/delivery/web/routers/ingestion.py`**:
  - Add `POST /api/ingest/bunq` and content-based CSV format auto-detection so any CSV sent to `/api/ingest/kbc`, `/api/ingest/bunq`, or `/api/ingest/generic` is automatically routed to the matching gateway.

---

## 3. TDD Verification Plan

1. **Unit & Integration Tests (`tests/integration/test_ingestion_csv_formats.py`)**:
   - Test KBC checking (`export_BE90000000001234_*.csv`), KBC savings (`export_BE68000000005678_*.csv`), KBC credit card (`export_KBC-Kredietkaart_*.csv`), KBC position overview (`Positie-overzicht op *.csv`), and Bunq checking/savings (`*_bunq-afschrift.csv`).
   - Verify foreign currency (`MGA`) conversion to `EUR`, settlement row filtering, duplicate same-day merchant transaction preservation, and idempotent re-uploads.
   - Verify `spaarrekening` IBAN deduplication between `KbcCsvGateway` and `GenericCsvGateway`.
2. **Delivery API Tests**:
   - Test `POST /api/ingest/kbc`, `POST /api/ingest/bunq`, and `POST /api/ingest/generic` including cross-endpoint auto-detection.
