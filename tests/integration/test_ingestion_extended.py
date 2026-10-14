"""Extended integration tests for Ingestion Gateways and PDT Auth."""

from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from wealth_pilot.adapters.ingestion.generic_csv import GenericCsvGateway
from wealth_pilot.adapters.ingestion.pdt_auth import PdtAuthManager, generate_pkce_pair
from wealth_pilot.adapters.ingestion.pdt_mcp import PdtMcpGateway
from wealth_pilot.domain.asset import AssetClass


def test_pkce_generation():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert "=" not in challenge


@pytest.mark.asyncio
@respx.mock
async def test_pdt_auth_endpoints():
    # 1. Register Client
    respx.post("https://mcp.portfoliodividendtracker.com/oauth/register").respond(
        200, json={"client_id": "test-client-123"}
    )
    cid = await PdtAuthManager.register_client("http://localhost:8000/callback")
    assert cid == "test-client-123"

    # 2. Build Authorization URL
    auth_url = PdtAuthManager.build_authorization_url(
        client_id="test-client-123",
        redirect_uri="http://localhost:8000/callback",
        state="state-abc",
        challenge="chal-xyz",
    )
    assert "https://auth.portfoliodividendtracker.com/oauth/authorize" in auth_url
    assert "code_challenge=chal-xyz" in auth_url
    assert "state=state-abc" in auth_url

    # 3. Exchange Code
    respx.post("https://auth.portfoliodividendtracker.com/oauth/token").respond(
        200, json={"access_token": "token-xyz", "expires_in": 3600}
    )
    tokens = await PdtAuthManager.exchange_code(
        client_id="test-client-123",
        code="code-abc",
        verifier="verifier-123",
        redirect_uri="http://localhost:8000/callback",
    )
    assert tokens["access_token"] == "token-xyz"
    assert tokens["client_id"] == "test-client-123"

    # 4. Refresh Tokens
    new_tokens = await PdtAuthManager.refresh_tokens(
        client_id="test-client-123",
        refresh_token="ref-abc",
    )
    assert new_tokens["access_token"] == "token-xyz"


@pytest.mark.asyncio
async def test_pdt_mcp_fetch_portfolio_assets_various_formats():
    gateway = PdtMcpGateway(auth_token="test-token")

    # MCP tool response with wrapped content text block and diverse asset types
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        content = {
            "result": {
                "holdings": [
                    {
                        "symbolName": "Vanguard FTSE All-World UCITS ETF",
                        "isin": "IE00BK5BQT80",
                        "unrealisedBoughtShares": 50.0,
                        "currentWorth": {"value": 6000.0, "currency": "EUR"},
                    },
                    {
                        "symbolName": "Physical Gold ETC",
                        "isin": "JE00B1VS3770",
                        "unrealisedBoughtShares": 20.0,
                        "currentWorth": {"value": 3500.0, "currency": "EUR"},
                    },
                    {
                        "symbolName": "Bitcoin Track",
                        "isin": "SE0007525332",
                        "unrealisedBoughtShares": 1.0,
                        "currentWorth": {"value": 500.0, "currency": "EUR"},
                    },
                    {
                        "symbolName": "Cash EUR",
                        "isCash": True,
                        "currentWorth": {"value": 1500.0, "currency": "EUR"},
                    },
                ]
            }
        }
        return httpx.Response(200, text=f"data: {httpx.Response(200, json=content).text}")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        assets = await gateway.fetch_portfolio_assets(client=client)
        assert len(assets) == 4
        # Check classifications
        assert assets[0].asset_class == AssetClass.ETF
        assert assets[1].asset_class == AssetClass.COMMODITY
        assert assets[2].asset_class == AssetClass.CRYPTO
        assert assets[3].asset_class == AssetClass.CASH


def test_generic_csv_gateway_edge_cases(tmp_path: Path):
    gateway = GenericCsvGateway()

    # File not found
    with pytest.raises(FileNotFoundError):
        gateway.parse_assets_file("non_existent.csv")

    # Fallback price calculation and alternate headers
    csv_file = tmp_path / "alternate.csv"
    csv_file.write_text(
        "security;ticker;type;quantity;price;currency\n"
        "MSCI Emerging Markets Index;EMERG;INDEX;100;45,50;USD\n"
        "Silver Bullion;SILV;COMMODITY;50;28,00;EUR\n"
        "Emergency Savings;;SAVINGS;1;2500,00;EUR\n"
        "Malformed Item;MAL;OTHER;bad_num;;EUR\n",
        encoding="utf-8",
    )

    assets = gateway.parse_assets_file(csv_file)
    assert len(assets) == 4
    # First item: 100 * 45.50 = 4550.00 USD, classified as ETF
    assert assets[0].asset_class == AssetClass.ETF
    assert assets[0].current_value.amount == Decimal("4550.00")
    assert assets[0].current_value.currency == "USD"

    # Second item: 50 * 28.00 = 1400.00 EUR, classified as COMMODITY
    assert assets[1].asset_class == AssetClass.COMMODITY
    assert assets[1].current_value.amount == Decimal("1400.00")

    # Third item: SAVINGS classified as CASH
    assert assets[2].asset_class == AssetClass.CASH
    assert assets[2].current_value.amount == Decimal("2500.00")

    # Fourth item: bad_num defaults to 1.0 shares without crashing
    assert assets[3].quantity == Decimal("1.0")
