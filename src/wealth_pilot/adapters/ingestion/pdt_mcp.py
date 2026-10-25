"""PDT MCP Server Ingestion Gateway."""

from __future__ import annotations

import contextlib
import json
from decimal import Decimal
from typing import Any

import httpx

from wealth_pilot import __version__
from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.money import Money

DEFAULT_MCP_URL = "https://mcp.portfoliodividendtracker.com"
USER_AGENT = f"WealthPilot/{__version__} (Strategic Wealth Guidance Platform; Python httpx)"


class PdtMcpGateway:
    """Connects to the Portfolio Dividend Tracker (PDT) MCP server and imports assets."""

    def __init__(self, mcp_url: str = DEFAULT_MCP_URL, auth_token: str | None = None) -> None:
        self.mcp_url = mcp_url
        self.auth_token = auth_token

    async def fetch_portfolio_assets(
        self, client: httpx.AsyncClient | None = None, raise_on_auth_error: bool = False
    ) -> list[Asset]:
        """Queries PDT MCP server for current holdings and converts to domain Assets."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "pdt-get-portfolio-holdings", "arguments": {}},
        }

        async def _call(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await c.post(self.mcp_url, json=payload, headers=headers, timeout=15.0)
            resp.raise_for_status()
            raw = resp.text.strip()
            if raw.startswith("data:"):
                raw = raw[5:].strip()

            return json.loads(raw)

        try:
            if client:
                data = await _call(client)
            else:
                async with httpx.AsyncClient() as c:
                    data = await _call(c)
            return self._parse_holdings_response(data)
        except httpx.HTTPStatusError as exc:
            if raise_on_auth_error and exc.response.status_code in (401, 403):
                raise
            return []
        except Exception:
            # Fallback empty or offline
            return []

    def _parse_holdings_response(self, data: dict[str, Any]) -> list[Asset]:
        result = data.get("result", {})
        # If response content is wrapped in MCP content text block
        content = result.get("content", [])
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                with contextlib.suppress(Exception):
                    result = json.loads(first["text"])
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

    async def lookup_historical_price(
        self,
        symbol: str,
        date: str = "2025-12-31",
        quote_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> Money | None:
        """Looks up closing price for a security on a specific historical date via PDT timetravel or market data."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        # 1. Try PDT MCP timetravel query
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "pdt-get-portfolio-holdings",
                "arguments": {"date": date, "as_of_date": date},
            },
        }

        async def _call_mcp(c: httpx.AsyncClient) -> dict[str, Any]:
            resp = await c.post(self.mcp_url, json=payload, headers=headers, timeout=10.0)
            resp.raise_for_status()
            raw = resp.text.strip()
            if raw.startswith("data:"):
                raw = raw[5:].strip()
            return json.loads(raw)

        try:
            if client:
                data = await _call_mcp(client)
            else:
                async with httpx.AsyncClient() as c:
                    data = await _call_mcp(c)

            assets = self._parse_holdings_response(data)
            symbol_up = symbol.strip().upper()
            match = next(
                (
                    a
                    for a in assets
                    if a.symbol.upper() == symbol_up
                    or (quote_id and quote_id in a.id)
                    or symbol_up in a.name.upper()
                ),
                None,
            )
            if match and match.quantity > Decimal("0.0"):
                price_amt = (match.current_value.amount / match.quantity).quantize(Decimal("0.01"))
                return Money(price_amt, match.currency)
        except Exception:
            pass

        return None
