"""Local SQLite Database Repository for persistent caching of transactions, assets, and liabilities."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.balance_sheet import MonthlyCashflow, Transaction
from wealth_pilot.domain.liability import Liability, LoanType
from wealth_pilot.domain.money import Money


class LocalDbRepository:
    """Manages local SQLite database for caching multi-account / multi-month CSV transactions,

    assets, and discovered loan liabilities.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        data_dir: str | Path | None = None,
        tenant_id: str = "default",
    ) -> None:
        self.tenant_id = tenant_id
        if db_path is None:
            raw_env_dir = None
            import os

            raw_env_dir = os.getenv("WEALTH_PILOT_DATA_DIR")
            base_dir = (
                Path(data_dir).expanduser().resolve()
                if data_dir
                else (
                    Path(raw_env_dir).expanduser().resolve()
                    if raw_env_dir
                    else Path.home() / ".wealth_pilot"
                )
            )
            if tenant_id != "default":
                self.db_path = base_dir / "tenants" / tenant_id / "wealth_pilot.db"
            else:
                self.db_path = base_dir / "wealth_pilot.db"
        elif str(db_path) == ":memory:":
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)

        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        if str(self.db_path) != ":memory:":
            with sqlite3.connect(str(self.db_path)) as raw_conn:
                raw_conn.execute("PRAGMA journal_mode=WAL")
                raw_conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    date TEXT,
                    amount REAL,
                    currency TEXT DEFAULT 'EUR',
                    description TEXT,
                    counterparty_name TEXT,
                    counterparty_iban TEXT,
                    category TEXT,
                    balance_after REAL,
                    is_inflow INTEGER,
                    source TEXT,
                    raw_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovered_assets (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    symbol TEXT,
                    isin TEXT,
                    asset_class TEXT,
                    current_value REAL,
                    currency TEXT DEFAULT 'EUR',
                    institution TEXT,
                    account_id TEXT,
                    source TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovered_liabilities (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    loan_type TEXT,
                    principal_balance REAL,
                    interest_rate_pct REAL,
                    monthly_payment REAL,
                    currency TEXT DEFAULT 'EUR',
                    institution TEXT,
                    account_reference TEXT,
                    user_confirmed INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_transactions(self, transactions: list[Transaction], source: str = "kbc_csv") -> int:
        """Inserts transactions, ignoring duplicates based on primary key id.

        Returns the number of newly inserted rows.
        """
        if not transactions:
            return 0

        inserted_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for tx in transactions:
                raw_str = json.dumps(tx.raw_data or {}) if tx.raw_data else None
                balance_val = float(tx.balance_after.amount) if tx.balance_after else None
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO transactions (
                        id, account_id, date, amount, currency, description,
                        counterparty_name, counterparty_iban, category,
                        balance_after, is_inflow, source, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx.id,
                        tx.account_id,
                        tx.date,
                        float(tx.amount.amount),
                        tx.amount.currency,
                        tx.description,
                        tx.counterparty_name,
                        tx.counterparty_iban,
                        tx.category,
                        balance_val,
                        1 if tx.is_inflow else 0,
                        source,
                        raw_str,
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_count += 1
            conn.commit()
        return inserted_count

    def get_transactions(
        self,
        limit: int = 1000,
        category: str | None = None,
        account_id: str | None = None,
    ) -> list[Transaction]:
        """Returns transactions from the local database, ordered by date descending."""
        query = "SELECT * FROM transactions"
        params: list[Any] = []
        conditions: list[str] = []

        if category:
            conditions.append("category = ?")
            params.append(category)
        if account_id:
            conditions.append("account_id = ?")
            params.append(account_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY date DESC, id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        txs: list[Transaction] = []
        for r in rows:
            cur = r["currency"] or "EUR"
            amt = Money(Decimal(str(r["amount"])), cur)
            bal = (
                Money(Decimal(str(r["balance_after"])), cur)
                if r["balance_after"] is not None
                else None
            )
            raw_d = json.loads(r["raw_json"]) if r["raw_json"] else {}
            txs.append(
                Transaction(
                    id=r["id"],
                    date=r["date"],
                    amount=amt,
                    account_id=r["account_id"] or "",
                    description=r["description"] or "",
                    counterparty_name=r["counterparty_name"] or "",
                    counterparty_iban=r["counterparty_iban"] or "",
                    category=r["category"] or "UNCATEGORIZED",
                    balance_after=bal,
                    raw_data=raw_d,
                )
            )
        return txs

    def update_transaction_category(self, transaction_id: str, new_category: str) -> bool:
        """Updates the category of a transaction in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                (new_category, transaction_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def save_discovered_assets(self, assets: list[Asset], source: str = "kbc_csv") -> None:
        """Upserts discovered assets into the database."""
        if not assets:
            return
        with self._get_connection() as conn:
            for a in assets:
                ac_str = (
                    a.asset_class.value if hasattr(a.asset_class, "value") else str(a.asset_class)
                )
                conn.execute(
                    """
                    INSERT INTO discovered_assets (
                        id, name, symbol, isin, asset_class, current_value,
                        currency, institution, account_id, source, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        current_value=excluded.current_value,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        a.id,
                        a.name,
                        a.symbol,
                        a.isin,
                        ac_str,
                        float(a.current_value.amount),
                        a.currency,
                        a.institution,
                        a.account_id,
                        source,
                    ),
                )
            conn.commit()

    def delete_discovered_assets_by_source(self, source: str) -> None:
        """Removes discovered assets originating from a specific source (e.g. 'pdt_mcp')."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM discovered_assets WHERE source = ?", (source,))
            conn.commit()

    def get_discovered_assets(self) -> list[Asset]:
        """Returns all cached discovered assets."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM discovered_assets ORDER BY name ASC")
            rows = cursor.fetchall()

        assets: list[Asset] = []
        for r in rows:
            ac_str = r["asset_class"] or "CASH"
            try:
                ac = AssetClass(ac_str)
            except ValueError:
                ac = AssetClass.CASH
            cur = r["currency"] or "EUR"
            assets.append(
                Asset(
                    id=r["id"],
                    name=r["name"],
                    symbol=r["symbol"] or "",
                    isin=r["isin"],
                    asset_class=ac,
                    current_value=Money(Decimal(str(r["current_value"])), cur),
                    institution=r["institution"] or "Unknown",
                    account_id=r["account_id"] or "",
                    currency=cur,
                )
            )
        return assets

    def save_discovered_liabilities(self, liabilities: list[Liability]) -> None:
        """Upserts discovered liabilities.

        Preserves user-confirmed principal balance and APR if already edited by user.
        """
        if not liabilities:
            return

        with self._get_connection() as conn:
            for liab in liabilities:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_confirmed, principal_balance, interest_rate_pct FROM discovered_liabilities WHERE id = ?",
                    (liab.id,),
                )
                existing = cursor.fetchone()

                lt_str = (
                    liab.loan_type.value
                    if hasattr(liab.loan_type, "value")
                    else str(liab.loan_type)
                )

                if existing and existing["user_confirmed"] == 1:
                    # User already confirmed this liability: preserve user's balance and APR!
                    cursor.execute(
                        """
                        UPDATE discovered_liabilities SET
                            monthly_payment = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (float(liab.monthly_payment.amount), liab.id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO discovered_liabilities (
                            id, name, loan_type, principal_balance, interest_rate_pct,
                            monthly_payment, currency, institution, account_reference,
                            user_confirmed, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name,
                            monthly_payment=excluded.monthly_payment,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (
                            liab.id,
                            liab.name,
                            lt_str,
                            float(liab.principal_balance.amount),
                            float(liab.interest_rate_pct),
                            float(liab.monthly_payment.amount),
                            liab.monthly_payment.currency,
                            liab.institution,
                            liab.account_reference,
                        ),
                    )
            conn.commit()

    def update_liability(self, liability_id: str, updates: dict[str, Any]) -> bool:
        """Updates a liability with user-provided parameters, marking it as user_confirmed."""
        fields: list[str] = []
        values: list[Any] = []

        if "name" in updates:
            fields.append("name = ?")
            values.append(updates["name"])
        if "loan_type" in updates:
            fields.append("loan_type = ?")
            values.append(updates["loan_type"])
        if "principal_balance" in updates:
            fields.append("principal_balance = ?")
            values.append(float(updates["principal_balance"]))
        if "interest_rate_pct" in updates:
            fields.append("interest_rate_pct = ?")
            values.append(float(updates["interest_rate_pct"]))
        if "monthly_payment" in updates:
            fields.append("monthly_payment = ?")
            values.append(float(updates["monthly_payment"]))
        if "institution" in updates:
            fields.append("institution = ?")
            values.append(updates["institution"])
        if "account_reference" in updates:
            fields.append("account_reference = ?")
            values.append(updates["account_reference"])

        fields.append("user_confirmed = 1")
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(liability_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE discovered_liabilities SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_liability(self, liability_id: str) -> bool:
        """Removes a liability from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM discovered_liabilities WHERE id = ?", (liability_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_discovered_liabilities(self) -> list[Liability]:
        """Returns all cached discovered liabilities."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM discovered_liabilities ORDER BY name ASC")
            rows = cursor.fetchall()

        liabs: list[Liability] = []
        for r in rows:
            lt_str = r["loan_type"] or "MORTGAGE"
            try:
                lt = LoanType(lt_str)
            except ValueError:
                lt = LoanType.MORTGAGE
            cur = r["currency"] or "EUR"
            liabs.append(
                Liability(
                    id=r["id"],
                    name=r["name"],
                    loan_type=lt,
                    principal_balance=Money(Decimal(str(r["principal_balance"])), cur),
                    interest_rate_pct=Decimal(str(r["interest_rate_pct"])),
                    monthly_payment=Money(Decimal(str(r["monthly_payment"])), cur),
                    institution=r["institution"] or "Manual",
                    account_reference=r["account_reference"] or "",
                )
            )
        return liabs

    def get_monthly_cashflow(self) -> MonthlyCashflow:
        """Calculates cumulative monthly cashflow across all cached transactions."""
        txs = self.get_transactions(limit=5000)
        liabs = self.get_discovered_liabilities()

        if not txs:
            total_debt_payment = sum(
                (liab.monthly_payment.amount for liab in liabs), Decimal("0.00")
            )
            return MonthlyCashflow(
                monthly_income=Money(Decimal("4800.00")),
                fixed_costs=Money(Decimal("1200.00")),
                debt_payments=Money(total_debt_payment),
                living_expenses=Money(Decimal("800.00")),
            )

        inflows = [t.amount.amount for t in txs if t.is_inflow]
        total_income = sum(inflows, Decimal("0.00"))

        distinct_income_months = (
            len({t.date[:7] for t in txs if t.is_inflow and t.amount.amount > Decimal("100.0")})
            or 1
        )
        avg_monthly_income = (total_income / Decimal(str(distinct_income_months))).quantize(
            Decimal("0.01")
        )

        total_debt_payment = sum((liab.monthly_payment.amount for liab in liabs), Decimal("0.00"))

        return MonthlyCashflow(
            monthly_income=Money(avg_monthly_income),
            fixed_costs=Money(Decimal("1200.00")),
            debt_payments=Money(total_debt_payment),
            living_expenses=Money(Decimal("800.00")),
        )

    def clear_all_cached_data(self) -> None:
        """Clears all transactions, discovered assets, and liabilities."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM discovered_assets")
            conn.execute("DELETE FROM discovered_liabilities")
            conn.commit()

    def export_state_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Exports all SQLite tables as serializable dictionaries for encrypted vault backups."""
        with self._get_connection() as conn:
            tx_rows = [dict(r) for r in conn.execute("SELECT * FROM transactions").fetchall()]
            asset_rows = [
                dict(r) for r in conn.execute("SELECT * FROM discovered_assets").fetchall()
            ]
            liab_rows = [
                dict(r) for r in conn.execute("SELECT * FROM discovered_liabilities").fetchall()
            ]
        return {
            "transactions": tx_rows,
            "discovered_assets": asset_rows,
            "discovered_liabilities": liab_rows,
        }

    def import_state_dict(self, state: dict[str, list[dict[str, Any]]]) -> None:
        """Restores SQLite tables from a decrypted vault backup dictionary."""
        with self._get_connection() as conn:
            if "transactions" in state:
                conn.execute("DELETE FROM transactions")
                for r in state["transactions"]:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO transactions (
                            id, account_id, date, amount, currency, description,
                            counterparty_name, counterparty_iban, category,
                            balance_after, is_inflow, source, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r.get("id"),
                            r.get("account_id"),
                            r.get("date"),
                            r.get("amount"),
                            r.get("currency", "EUR"),
                            r.get("description"),
                            r.get("counterparty_name"),
                            r.get("counterparty_iban"),
                            r.get("category"),
                            r.get("balance_after"),
                            r.get("is_inflow", 0),
                            r.get("source"),
                            r.get("raw_json"),
                        ),
                    )
            if "discovered_assets" in state:
                conn.execute("DELETE FROM discovered_assets")
                for r in state["discovered_assets"]:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO discovered_assets (
                            id, name, symbol, isin, asset_class, current_value,
                            currency, institution, account_id, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r.get("id"),
                            r.get("name"),
                            r.get("symbol"),
                            r.get("isin"),
                            r.get("asset_class"),
                            r.get("current_value"),
                            r.get("currency", "EUR"),
                            r.get("institution"),
                            r.get("account_id"),
                            r.get("source"),
                        ),
                    )
            if "discovered_liabilities" in state:
                conn.execute("DELETE FROM discovered_liabilities")
                for r in state["discovered_liabilities"]:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO discovered_liabilities (
                            id, name, loan_type, principal_balance, interest_rate_pct,
                            monthly_payment, currency, institution, account_reference, user_confirmed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r.get("id"),
                            r.get("name"),
                            r.get("loan_type"),
                            r.get("principal_balance"),
                            r.get("interest_rate_pct"),
                            r.get("monthly_payment"),
                            r.get("currency", "EUR"),
                            r.get("institution"),
                            r.get("account_reference"),
                            r.get("user_confirmed", 0),
                        ),
                    )
            conn.commit()
