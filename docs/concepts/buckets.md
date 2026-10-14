# Strategic Allocation Buckets

Wealth Pilot organizes all your financial holdings into macro **strategic allocation buckets**.

---

## What is a Bucket?

A **Bucket** represents a strategic investment pillar or wealth goal, rather than an arbitrary financial product.

Common examples:
- **Core World ETFs (e.g. 50%)**: Broad, low-cost global equity index funds (e.g. VWCE, IWDA).
- **High-Conviction Tech / Equities (e.g. 35%)**: Individual stock positions (e.g. ASML, NVDA) with higher growth potential.
- **Gold & Commodities (e.g. 5%)**: Inflation hedges and uncorrelated assets.
- **Liquid Emergency Buffer (e.g. 10%)**: High-yield cash reserves in checking/savings (KBC, Bunq).

---

## Target Weight & Drift Tolerance

Each bucket is defined by:
1. **Target Weight (%)**: The ideal percentage of your total liquid portfolio value.
2. **Drift Tolerance (±%)**: The acceptable deviation band before a rebalance alert is triggered (default: ±3.0%).

### Drift Statuses:
- **BALANCED (🟢)**: Current weight is within the target weight ± drift tolerance.
- **UNDERWEIGHT (🔵)**: Current weight is below target by more than the tolerance. Cash deposits will be routed here.
- **OVERWEIGHT (🟡)**: Current weight exceeds target by more than tolerance.

---

## Rule-Based Asset Matching

Assets are dynamically assigned to buckets using declarative rules:
- **Symbols**: Match specific tickers (e.g. `ASML`, `VWCE`).
- **ISINs**: Match exact security identifiers (e.g. `NL0010273215`, `IE00BK5BQT80`).
- **Asset Classes**: Match entire classes (`EQUITY`, `ETF`, `COMMODITY`, `CRYPTO`, `CASH`).
- **Institutions**: Match specific accounts (e.g. `KBC`, `Bunq`).
