"""Use Case: Find earliest known financial date across assets, debts, and transactions."""

from __future__ import annotations

import re
from typing import Any

from paslood.domain.balance_sheet import BalanceSheet


class FindOldestDateUseCase:
    """Discovers the earliest financial milestone/record date for portfolio inception."""

    def execute(
        self,
        balance_sheet: BalanceSheet,
        oldest_tx_date: str | None = None,
    ) -> dict[str, Any]:
        dates: list[str] = []

        if oldest_tx_date and self._is_valid_date(oldest_tx_date):
            dates.append(oldest_tx_date[:10])

        for liab in balance_sheet.liabilities:
            if liab.start_date and self._is_valid_date(liab.start_date):
                dates.append(liab.start_date[:10])

        for asset in balance_sheet.assets:
            if asset.acquisition_date and self._is_valid_date(asset.acquisition_date):
                dates.append(asset.acquisition_date[:10])

        if not dates:
            return {"oldest_date": None, "oldest_year": None}

        oldest = min(dates)
        try:
            year = int(oldest[:4])
        except (ValueError, IndexError):
            year = None

        return {"oldest_date": oldest, "oldest_year": year}

    @staticmethod
    def _is_valid_date(val: str) -> bool:
        if not val or not isinstance(val, str):
            return False
        clean = val.strip()
        # YYYY-MM-DD or YYYY
        return bool(re.match(r"^\d{4}(-\d{2}-\d{2})?$", clean))
