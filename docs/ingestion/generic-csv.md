# Generic CSV / Excel Ingestion

For brokerages or banks that do not have an automated connector, Wealth Pilot provides an open, standard CSV format.

---

## CSV Column Headers

```csv
name,symbol,isin,asset_class,shares,current_price,current_value,institution,currency
```

### Supported Columns:
- `name`: Security or account name (e.g. `Microsoft Corp.`)
- `symbol`: Ticker symbol (e.g. `MSFT`, `VWCE`)
- `isin`: 12-character ISIN code (e.g. `US5949181045`)
- `asset_class`: `EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, `CASH`, or `REAL_ESTATE`
- `shares`: Number of units held
- `current_price`: Market price per share
- `current_value`: Total valuation in the specified currency
- `institution`: Brokerage or bank name (e.g. `DEGIRO`, `Saxo Bank`, `Bolero`)
- `currency`: Currency code (default: `EUR`)

---

## Generating a Sample Template

You can generate a sample CSV directly from the CLI or download it from the Web Dashboard:

```bash
uv run wealth-pilot template --output portfolio_template.csv
```
