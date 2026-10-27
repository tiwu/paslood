# Belgian Fiscal Shield & EquatePlus Tax Optimization

Paslood includes a legally grounded Belgian tax engine designed for DIY investors holding ETFs at Belgian brokers (e.g., Saxo, Bolero) alongside employee shares at foreign custodians (e.g., ASML on **EquatePlus / Equatex AG Zurich**).

---

## 1. Official Statutory Sources (FOD Financiën)

All rates, thresholds, caps, and cost-basis rules in [`tax_rules.py`](https://github.com/tiwu/paslood/blob/main/src/paslood/domain/tax_rules.py) and [`optimize_tax.py`](https://github.com/tiwu/paslood/blob/main/src/paslood/use_cases/optimize_tax.py) follow official Belgian legislation:

1. **Meerwaardebelasting op financiële activa (Effective 1 Jan 2026)**:
   - **Legal Basis**: *Wetboek van de Inkomstenbelastingen 1992 (WIB 92), Art. 90, eerste lid, 9° & Art. 101–102*.
   - **Official Portal**: [FOD Financiën — Meerwaardebelasting](https://financien.belgium.be/nl/particulieren/belastingen/inkomstenbelastingen/meerwaardebelasting)
2. **Taks op de beursverrichtingen (TOB)**:
   - **Legal Basis**: *Wetboek diverse rechten en taksen (WDRT), Art. 120–126/2*.
   - **Official Portal**: [FOD Financiën — TOB](https://financien.belgium.be/nl/particulieren/internationaal/buitenlandse-inkomsten-en-rekeningen/taks-op-beursverrichtingen)
3. **Reynderstaks (Fixed-Income & Mixed Fund Gains)**:
   - **Legal Basis**: *Wetboek van de Inkomstenbelastingen 1992 (WIB 92), Art. 19bis*.
   - **Official Portal**: [Fisconetplus (FOD Financiën)](https://eservices.minfin.fgov.be/myminfin-web/pages/public/fisconet)

---

## 2. Key Fiscal Rules Implemented

### A. 2026 Meerwaardebelasting & The 31 Dec 2025 "Fotomoment"
- **Pre-2026 Acquisition Cost Basis (`max(Fotomoment, Historical Purchase Price)`)**:
  - For shares acquired on or before **31 December 2025**, the default fiscal cost basis is the closing market price on **31 December 2025** (for **ASML** on Euronext Amsterdam: **`€921.40`**).
  - **Historical Loss Protection**: If your actual historical purchase price was *higher* than the 31 December 2025 closing price, the law entitles you (until 31 Dec 2030) to use `max(price_2025_12_31, historical_purchase_price)` so historical losses are never taxed as artificial post-2025 gains.
- **Annual Exemption & 5-Year Carry-Over**:
  - Base exemption: **`€10,000.00`** per person per year (**`€20,000.00`** for joint filing).
  - Unused exemption carries forward by **`+€1,000.00/year`** for up to **5 years** (maximum **`€15,000.00`** single / **`€30,000.00`** joint).
  - Net gains above the exemption are taxed at **`10.0%`**.

### B. EquatePlus (Equatex AG Zurich) Forensic Reconciliation
When selling employee shares (such as ASML) on **EquatePlus**, Equatex AG (Zurich, Switzerland) deducts two charges on your settlement PDF and reports a misleading capital gain figure:
1. **`Provisies` (`0.35%`)**: Equatex AG's brokerage commission (not Belgian TOB).
2. **`Zegelrechten bij verkoop` (`0.15%`)**: Swiss Federal Securities Transfer Stamp Duty (*Umsatzabgabe*) levied because Equatex AG is a Swiss securities dealer trading a foreign (Dutch) stock.
3. **Unwithheld Belgian TOB (`0.35%`)**: Because Equatex AG does not withhold Belgian TOB, you must self-declare and pay **`0.35%` Belgian TOB** to FOD Financiën by the **last working day of the second month** following the sale (`M+2`).
4. **Historical FMV Gain vs. Belgian Fotomoment Gain**: Equatex calculates `Totale vermogenswinst` against your original grant FMV (e.g., `€271.55` in April 2020) instead of the **31 Dec 2025 fotomoment (`€921.40`)**. Paslood automatically calculates the exact exemption saved by applying the legal 31 Dec 2025 benchmark.

### C. TOB Tiers & Statutory Plafonds (`WDRT Art. 120`)
- **`0.12%`** (Plafond **`€1,300.00`**): EEA distributing ETFs, bonds, Belgian REITs (*GVV/SIR*).
- **`0.35%`** (Plafond **`€1,600.00`**): Individual stocks (ASML, etc.), non-EEA ETFs, Gold ETCs.
- **`1.32%`** (Plafond **`€4,000.00`**): Accumulating funds/ETFs registered in Belgium.

### D. Reynders Tax (`WIB 92 Art. 19bis`)
- Funds or ETFs holding **`>10%` in debt claims** (bonds, cash, money-market instruments) incur a **`30.0%` withholding tax** on the fixed-income portion of the gain (with no €10,000 exemption), while the remaining equity portion falls under the 10% CGT.
