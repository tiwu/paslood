"""Repository ports and application interfaces for Paslood.

Adheres to Clean Architecture: use cases depend on abstract protocols (ports),
implemented by infrastructure adapters (repositories).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from paslood.domain.account import KnownAccount
from paslood.domain.asset import Asset
from paslood.domain.balance_sheet import MonthlyCashflow, Transaction
from paslood.domain.bucket import Bucket
from paslood.domain.liability import Liability


@runtime_checkable
class StatementGatewayPort(Protocol):
    """Port contract for bank and statement CSV ingestion gateways."""

    def parse_file(self, file_path: str | Path) -> dict[str, Any]: ...


@runtime_checkable
class AIAdvisorPort(Protocol):
    """Port contract for AI LLM providers (Gemini, OpenAI, Anthropic, Ollama)."""

    async def generate_advice(self, prompt: str, system_prompt: str | None = None) -> str: ...


@runtime_checkable
class PortfolioRepository(Protocol):
    """Protocol for managing user portfolio configuration, buckets, manual assets, and liabilities."""

    def load_buckets(self) -> list[Bucket]: ...

    def save_bucket(self, bucket_data: dict[str, Any]) -> str: ...

    def delete_bucket(self, bucket_id: str) -> bool: ...

    def save_bucket_target(self, bucket_id: str, name: str, target_weight_pct: Decimal) -> None: ...

    def save_bucket_targets(self, targets: dict[str, Decimal | float]) -> None: ...

    def assign_asset_to_bucket(
        self,
        bucket_id: str,
        symbol: str | None = None,
        isin: str | None = None,
        asset_id: str | None = None,
        name: str | None = None,
    ) -> None: ...

    def load_known_accounts(self) -> list[KnownAccount]: ...

    def save_known_account(self, account: KnownAccount) -> None: ...

    def delete_known_account(self, account_id: str) -> None: ...

    def load_manual_assets(self) -> list[Asset]: ...

    def save_manual_asset(self, asset_dict: dict[str, Any]) -> None: ...

    def delete_manual_asset(self, asset_id: str) -> None: ...

    def load_manual_liabilities(self) -> list[Liability]: ...

    def save_manual_liability(self, liability_dict: dict[str, Any]) -> None: ...

    def delete_manual_liability(self, liability_id: str) -> None: ...

    def load_transaction_rules(self) -> list[dict[str, Any]]: ...

    def save_transaction_rule(self, rule: dict[str, Any]) -> None: ...

    def load_milestones(self) -> list[dict[str, Any]]: ...

    def save_milestones(self, milestones: list[dict[str, Any]]) -> None: ...

    def load_settings(self) -> dict[str, Any]: ...

    def save_settings(self, settings_dict: dict[str, Any]) -> None: ...


@runtime_checkable
class TransactionRepository(Protocol):
    """Protocol for transaction ledger, discovered balance sheet items, and cashflow."""

    def save_transactions(
        self, transactions: list[Transaction], source: str = "kbc_csv"
    ) -> int: ...

    def get_transactions(
        self,
        limit: int = 1000,
        category: str | None = None,
        account_id: str | None = None,
    ) -> list[Transaction]: ...

    def update_transaction_category(self, transaction_id: str, new_category: str) -> bool: ...

    def apply_rule_to_transactions(
        self,
        pattern: str,
        category: str,
        exclude_overrides: bool = True,
        amount: Decimal | float | None = None,
    ) -> int: ...

    def apply_known_account_to_transactions(
        self,
        account_number: str,
        label: str,
        account_type: str,
    ) -> int: ...

    def save_discovered_assets(self, assets: list[Asset], source: str = "kbc_csv") -> None: ...

    def get_discovered_assets(self) -> list[Asset]: ...

    def delete_discovered_assets_by_source(self, source: str) -> None: ...

    def get_discovered_account_summaries(self) -> list[dict[str, Any]]: ...

    def save_discovered_liabilities(self, liabilities: list[Liability]) -> None: ...

    def get_discovered_liabilities(self) -> list[Liability]: ...

    def update_liability(self, liability_id: str, updates: dict[str, Any]) -> bool: ...

    def delete_liability(self, liability_id: str) -> bool: ...

    def get_monthly_cashflow(self, period: str = "all") -> MonthlyCashflow: ...

    def get_oldest_transaction_date(self) -> str | None: ...

    def clear_all_cached_data(self) -> None: ...
