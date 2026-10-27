"""Helper utilities and consolidated state builders for Paslood web delivery."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

import httpcore
from httpcore._backends.auto import AutoBackend

from paslood.domain.asset import Asset
from paslood.domain.balance_sheet import BalanceSheet
from paslood.domain.liability import Liability
from paslood.domain.money import Money
from paslood.use_cases.ports import PortfolioRepository, TransactionRepository


class _PinnedMcpNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, hostname: str, addresses: list[str]) -> None:
        self._hostname = hostname
        self._addresses = tuple(addresses)
        self._backend = AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if host.lower() != self._hostname:
            raise httpcore.ConnectError("Connection to an unvalidated host was blocked.")

        last_error: Exception | None = None
        for address in self._addresses:
            try:
                # Preserve the URL hostname for Host and TLS while pinning the TCP destination.
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise httpcore.ConnectError("No validated address is available.")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


def get_consolidated_balance_sheet(
    repo: PortfolioRepository, db: TransactionRepository
) -> BalanceSheet:
    """Builds the consolidated BalanceSheet from manual config and discovered items in SQLite."""
    assets: list[Asset] = []
    # Manual assets (e.g. Bunq savings, Real Estate)
    manual_assets = repo.load_manual_assets()
    assets.extend(manual_assets)
    existing_asset_ids = {a.id for a in manual_assets}

    # Cached discovered assets from SQLite DB (KBC CSV, PDT MCP)
    for a in db.get_discovered_assets():
        if a.id not in existing_asset_ids:
            assets.append(a)
            existing_asset_ids.add(a.id)

    liabilities: list[Liability] = []
    manual_liabs = repo.load_manual_liabilities()
    liabilities.extend(manual_liabs)
    existing_liab_ids = {liab.id for liab in manual_liabs}
    existing_liab_refs = {liab.account_reference for liab in manual_liabs if liab.account_reference}

    for liab in db.get_discovered_liabilities():
        if liab.id not in existing_liab_ids and (
            not liab.account_reference or liab.account_reference not in existing_liab_refs
        ):
            liabilities.append(liab)

    cashflow = db.get_monthly_cashflow()

    return BalanceSheet(assets=assets, liabilities=liabilities, cashflow=cashflow)


def enrich_liability_dict(liab_dict: dict[str, Any]) -> dict[str, Any]:
    """Applies amortization estimation to manual liability dict if fields are missing."""
    cur = liab_dict.get("currency", "EUR")
    bal_val = float(liab_dict.get("principal_balance", 0.0))
    pmt_val = float(liab_dict.get("monthly_payment", 0.0))
    rate_val = float(liab_dict.get("interest_rate_pct", 0.0))
    start_cap = liab_dict.get("start_capital")
    start_date = liab_dict.get("start_date")
    end_date = liab_dict.get("end_date")
    dur_months = liab_dict.get("duration_months")
    pmt_pct = liab_dict.get("monthly_payment_pct")

    if bal_val <= 0.0 and start_cap and float(start_cap) > 0.0 and start_date:
        est_bal, est_pmt = Liability.calculate_amortized_state(
            start_capital=Money.from_val(start_cap, cur),
            interest_rate_pct=Decimal(str(rate_val)),
            start_date=str(start_date),
            duration_months=int(dur_months) if dur_months is not None else None,
            end_date=str(end_date) if end_date else None,
        )
        liab_dict["principal_balance"] = float(est_bal.amount)
        bal_val = float(est_bal.amount)
        if pmt_val <= 0.0:
            liab_dict["monthly_payment"] = float(est_pmt.amount)
            pmt_val = float(est_pmt.amount)

    if pmt_val <= 0.0 and pmt_pct is not None and float(pmt_pct) > 0.0:
        liab_dict["monthly_payment"] = round(bal_val * (float(pmt_pct) / 100.0), 2)

    return liab_dict
