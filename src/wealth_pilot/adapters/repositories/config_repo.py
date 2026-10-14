"""Config Repository for managing Buckets, Manual Accounts, and Classification Rules."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.bucket import AllocationRule, Bucket
from wealth_pilot.domain.liability import Liability, LoanType
from wealth_pilot.domain.money import Money

DEFAULT_BUCKETS_CONFIG: list[dict[str, Any]] = [
    {
        "id": "core-etf",
        "name": "Core World ETFs",
        "target_weight_pct": 50.0,
        "drift_tolerance_pct": 3.0,
        "color": "#3B82F6",
        "rules": [
            {"asset_classes": ["ETF"]},
            {"symbols": ["VWCE", "IWDA", "EMIM"]},
        ],
    },
    {
        "id": "tech-growth",
        "name": "High-Conviction Tech",
        "target_weight_pct": 35.0,
        "drift_tolerance_pct": 5.0,
        "color": "#10B981",
        "rules": [
            {"symbols": ["ASML", "NVDA", "AAPL", "MSFT"]},
        ],
    },
    {
        "id": "commodities",
        "name": "Gold & Commodities",
        "target_weight_pct": 5.0,
        "drift_tolerance_pct": 2.0,
        "color": "#F59E0B",
        "rules": [
            {"asset_classes": ["COMMODITY"]},
            {"name_keywords": ["GOLD", "GOUD", "COMMODITY"]},
        ],
    },
    {
        "id": "cash-buffer",
        "name": "Cash & Emergency Buffer",
        "target_weight_pct": 10.0,
        "drift_tolerance_pct": 2.5,
        "color": "#6366F1",
        "rules": [
            {"asset_classes": ["CASH"]},
            {"institutions": ["KBC", "BUNQ"]},
        ],
    },
]


class ConfigRepository:
    """Manages YAML/JSON configuration files for user buckets, accounts, and learned rules."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path.home() / ".wealth_pilot" / "portfolio.yaml"

        self.rules_path = self.config_path.parent / "rules.yaml"
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_data = {
                "buckets": DEFAULT_BUCKETS_CONFIG,
                "manual_assets": [
                    {
                        "id": "bunq-savings",
                        "name": "Bunq High-Yield Savings",
                        "symbol": "SAVINGS",
                        "asset_class": "CASH",
                        "current_value": 15000.0,
                        "institution": "Bunq",
                        "currency": "EUR",
                    }
                ],
                "manual_liabilities": [],
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(default_data, f, sort_keys=False, indent=2)

        if not self.rules_path.exists():
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.rules_path, "w", encoding="utf-8") as f:
                yaml.dump([], f, sort_keys=False)

    def load_buckets(self) -> list[Bucket]:
        """Loads configured strategic buckets with allocation rules."""
        if not self.config_path.exists():
            return []

        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_buckets = data.get("buckets", [])
        buckets: list[Bucket] = []

        for b in raw_buckets:
            rules: list[AllocationRule] = []
            for r in b.get("rules", []):
                syms = set(r.get("symbols", []))
                isins = set(r.get("isins", []))
                insts = set(r.get("institutions", []))
                keywords = set(r.get("name_keywords", []))
                classes = {
                    AssetClass(c) for c in r.get("asset_classes", []) if c in AssetClass.__members__
                }
                rules.append(
                    AllocationRule(
                        symbols=syms,
                        isins=isins,
                        asset_classes=classes,
                        institutions=insts,
                        name_keywords=keywords,
                    )
                )

            buckets.append(
                Bucket(
                    id=str(b.get("id")),
                    name=str(b.get("name")),
                    target_weight_pct=Decimal(str(b.get("target_weight_pct", 0.0))),
                    drift_tolerance_pct=Decimal(str(b.get("drift_tolerance_pct", 3.0))),
                    rules=rules,
                    color=str(b.get("color", "#3B82F6")),
                    description=str(b.get("description", "")),
                )
            )

        return buckets

    def save_bucket_target(self, bucket_id: str, name: str, target_weight_pct: Decimal) -> None:
        """Updates or creates a bucket allocation target in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        buckets = data.get("buckets", [])
        existing = next((b for b in buckets if b.get("id") == bucket_id), None)
        if existing:
            existing["target_weight_pct"] = float(target_weight_pct)
            existing["name"] = name
        else:
            buckets.append(
                {
                    "id": bucket_id,
                    "name": name,
                    "target_weight_pct": float(target_weight_pct),
                    "drift_tolerance_pct": 3.0,
                    "color": "#8B5CF6",
                    "rules": [],
                }
            )

        data["buckets"] = buckets
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, indent=2)

    def load_manual_assets(self) -> list[Asset]:
        """Loads manually configured assets (e.g. Bunq savings, private real estate)."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_assets = data.get("manual_assets", [])
        assets: list[Asset] = []
        for a in raw_assets:
            ac_str = str(a.get("asset_class", "CASH")).upper()
            try:
                ac = AssetClass(ac_str)
            except ValueError:
                ac = AssetClass.CASH

            val = Money.from_val(a.get("current_value", 0.0), a.get("currency", "EUR"))
            assets.append(
                Asset(
                    id=str(a.get("id", "manual")),
                    name=str(a.get("name", "Manual Asset")),
                    symbol=str(a.get("symbol", "")),
                    isin=a.get("isin"),
                    asset_class=ac,
                    current_value=val,
                    institution=str(a.get("institution", "Manual")),
                    currency=val.currency,
                )
            )
        return assets

    def load_manual_liabilities(self) -> list[Liability]:
        """Loads manually configured debts/mortgages."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_liabilities = data.get("manual_liabilities", [])
        liabilities: list[Liability] = []
        for item in raw_liabilities:
            lt_str = str(item.get("loan_type", "MORTGAGE")).upper()
            try:
                lt = LoanType(lt_str)
            except ValueError:
                lt = LoanType.MORTGAGE

            bal = Money.from_val(item.get("principal_balance", 0.0), item.get("currency", "EUR"))
            pmt = Money.from_val(item.get("monthly_payment", 0.0), item.get("currency", "EUR"))
            rate = Decimal(str(item.get("interest_rate_pct", 0.0)))
            liabilities.append(
                Liability(
                    id=str(item.get("id", "manual-debt")),
                    name=str(item.get("name", "Manual Debt")),
                    loan_type=lt,
                    principal_balance=bal,
                    interest_rate_pct=rate,
                    monthly_payment=pmt,
                    institution=str(item.get("institution", "Manual")),
                    account_reference=str(item.get("account_reference", "")),
                )
            )
        return liabilities

    def load_transaction_rules(self) -> list[dict[str, Any]]:
        """Loads custom learned classification rules."""
        if not self.rules_path.exists():
            return []
        with open(self.rules_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or []

    def save_transaction_rule(self, rule: dict[str, Any]) -> None:
        """Appends a learned transaction classification rule."""
        rules = self.load_transaction_rules()
        # Deduplicate by pattern
        existing = next((r for r in rules if r.get("pattern") == rule.get("pattern")), None)
        if existing:
            existing.update(rule)
        else:
            rules.append(rule)

        with open(self.rules_path, "w", encoding="utf-8") as f:
            yaml.dump(rules, f, sort_keys=False, indent=2)
