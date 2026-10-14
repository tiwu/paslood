"""PDT MCP Server Ingestion Gateway."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.money import Money


class PdtMcpGateway:
    """Connects to the Portfolio Dividend Tracker (PDT) MCP server and imports assets."""

    def __init__(
        self, mcp_url: str = "http://localhost:3000/mcp", auth_token: str | None = None
    ) -> None:
        self.mcp_url = mcp_url
        self.auth_token = auth_token

    async def fetch_portfolio_assets(self, client: httpx.AsyncClient | None = None) -> list[Asset]:
        """Queries PDT MCP server for current holdings and converts to domain Assets."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "pdt-get-portfolio-holdings", "arguments": {}},
        }

        async def _call(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await c.post(self.mcp_url, json=payload, headers=headers, timeout=10.0)
            resp.raise_for_status()
            return resp.json()

        try:
            if client:
                data = await _call(client)
            else:
                async with httpx.AsyncClient() as c:
                    data = await _call(c)
            return self._parse_holdings_response(data)
        except Exception:
            # Fallback empty or offline
            return []

    def _parse_holdings_response(self, data: dict[str, Any]) -> list[Asset]:
        result = data.get("result", {})
        holdings = result.get("holdings", [])
        assets: list[Asset] = []

        for h in holdings:
            name = h.get("symbolName", "Unknown")
            symbol = h.get("symbolName", "")
            isin = h.get("isin")
            quote_id = str(h.get("symbolQuoteId", ""))

            # Classify AssetClass
            name_up = name.upper()
            if h.get("isCash") or name_up == "CASH" or not isin:
                ac = AssetClass.CASH
            elif any(g in name_up for g in ("GOLD", "GOUD", "ETC")):
                ac = AssetClass.COMMODITY
            elif any(e in name_up for e in ("ETF", "UCITS", "VANGUARD", "ISHARES", "SPDR")):
                ac = AssetClass.ETF
            elif any(c in name_up for c in ("BTC", "BITCOIN", "ETH", "CRYPTO")):
                ac = AssetClass.CRYPTO
            else:
                ac = AssetClass.EQUITY

            worth_obj = h.get("currentWorth") or h.get("currentWorthLocal") or {}
            val_amt = Decimal(str(worth_obj.get("value", 0.0) or 0.0))
            curr = str(worth_obj.get("currency", "EUR") or "EUR")
            current_value = Money(val_amt, curr)

            shares_amt = Decimal(str(h.get("unrealisedBoughtShares", 1.0) or 1.0))

            assets.append(
                Asset(
                    id=f"pdt-{quote_id or symbol}",
                    name=name,
                    symbol=symbol,
                    isin=isin,
                    asset_class=ac,
                    current_value=current_value,
                    quantity=shares_amt,
                    institution="PDT Portfolio",
                    currency=curr,
                )
            )

        return assets
