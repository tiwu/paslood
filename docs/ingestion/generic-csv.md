# Generic CSV / Excel Ingestion

For financial institutions and brokers without automated API connectors, Paslood accepts a standard generic CSV format.

---

## CSV Specification

### Required & Optional Columns

| Column | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `name` | `string` | **Yes** | Security or account name | `Vanguard FTSE All-World` |
| `symbol` | `string` | **Yes** | Ticker symbol | `VWCE` |
| `isin` | `string` | Optional | 12-character ISIN code | `IE00BK5BQT80` |
| `asset_class` | `string` | **Yes** | Instrument classification (`EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, `CASH`, `REAL_ESTATE`) | `ETF` |
| `shares` | `decimal` | **Yes** | Quantity of units held | `125.50` |
| `current_price` | `decimal` | **Yes** | Market price per share | `118.25` |
| `current_value` | `decimal` | **Yes** | Total position value (`shares * current_price`) | `14840.38` |
| `institution` | `string` | Optional | Custodian or bank name | `Saxo Bank` |
| `currency` | `string` | Optional | Currency ISO code (default: `EUR`) | `EUR` |

---

## Example Generic CSV

```csv
name,symbol,isin,asset_class,shares,current_price,current_value,institution,currency
Vanguard FTSE All-World,VWCE,IE00BK5BQT80,ETF,125.50,118.25,14840.38,Saxo Bank,EUR
Apple Inc.,AAPL,US0378331005,EQUITY,45.00,225.50,10147.50,Bolero,EUR
Physical Gold ETC,4GLD,DE000A0S9GB0,COMMODITY,30.00,82.10,2463.00,DEGIRO,EUR
High-Yield Savings,SAVINGS,,CASH,1.00,10000.00,10000.00,Bunq,EUR
```

---

## Template Generation

```bash
uv run paslood template --output portfolio_template.csv
```
