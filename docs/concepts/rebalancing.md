# Buy-Only Rebalancing Strategy

Traditional portfolio rebalancing involves selling over-allocated winners and buying under-allocated laggards. While mathematically sound, selling in the real world introduces friction:

1. **Transaction Fees & Spreads**: Broker commissions on both sell orders and buy orders.
2. **Transaction Taxes (TOB)**: E.g., Belgian stock exchange tax on both sales and purchases.
3. **Capital Gains Taxes**: Realizing taxable profits unnecessarily.

---

## The Buy-Only Cash Injection Model

Wealth Pilot defaults to **Buy-Only Rebalancing**:

1. You specify an incoming cash deposit (e.g. your monthly savings of €1,500).
2. The engine identifies which buckets are currently **UNDERWEIGHT** (where Current Weight < Target Weight).
3. The deposit is distributed **proportionally to each bucket's deficit**, bringing the overall portfolio toward target weights with **zero forced sales**.

```
Example:
Planned Deposit: € 2,000.00
- Core World ETF Deficit: € 15,000 (60% of total shortfall) -> BUY € 1,200.00
- Tech Conviction Deficit: € 10,000 (40% of total shortfall) -> BUY € 800.00
- Gold Bucket: Already balanced -> BUY € 0.00
```

By accumulating new cash directly into underweight assets, you rebalance continuously without selling your winners.
