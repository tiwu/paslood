"""Helper utilities and consolidated state builders for Paslood web delivery."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

import httpcore
from httpcore._backends.auto import AutoBackend

from paslood.domain.balance_sheet import BalanceSheet
from paslood.domain.liability import Liability
from paslood.domain.money import Money
from paslood.use_cases.build_overview import BuildPortfolioOverviewUseCase
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
    return BuildPortfolioOverviewUseCase.consolidate_balance_sheet(repo, db)


def enrich_liability_dict(liab_dict: dict[str, Any]) -> dict[str, Any]:
    """Applies Decimal-accurate amortization estimation to manual liability dict if fields are missing."""
    cur = str(liab_dict.get("currency", "EUR"))
    bal = Money(Decimal(str(liab_dict.get("principal_balance", 0.0) or 0.0)), cur)
    pmt = Money(Decimal(str(liab_dict.get("monthly_payment", 0.0) or 0.0)), cur)
    rate = Decimal(str(liab_dict.get("interest_rate_pct", 0.0) or 0.0))
    start_cap_raw = liab_dict.get("start_capital")
    start_cap = Money(Decimal(str(start_cap_raw)), cur) if start_cap_raw is not None else None
    start_date = liab_dict.get("start_date")
    end_date = liab_dict.get("end_date")
    dur_months = liab_dict.get("duration_months")
    pmt_pct_raw = liab_dict.get("monthly_payment_pct")
    pmt_pct = Decimal(str(pmt_pct_raw)) if pmt_pct_raw is not None else None

    if (
        bal.amount <= Decimal("0.00")
        and start_cap is not None
        and start_cap.amount > Decimal("0.00")
        and start_date
    ):
        est_bal, est_pmt = Liability.calculate_amortized_state(
            start_capital=start_cap,
            interest_rate_pct=rate,
            start_date=str(start_date),
            duration_months=int(dur_months) if dur_months is not None else None,
            end_date=str(end_date) if end_date else None,
        )
        bal = est_bal
        liab_dict["principal_balance"] = float(bal.amount)
        if pmt.amount <= Decimal("0.00"):
            pmt = est_pmt
            liab_dict["monthly_payment"] = float(pmt.amount)

    if pmt.amount <= Decimal("0.00") and pmt_pct is not None and pmt_pct > Decimal("0.00"):
        pmt = bal * (pmt_pct / Decimal("100.0"))
        liab_dict["monthly_payment"] = float(pmt.amount)

    return liab_dict
