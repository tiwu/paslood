"""Tests for FastAPI Web Application Endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot import __version__
from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app

SAMPLE_KBC_CSV = """Rekeningnummer;Rubrieknaam;Naam;Munt;Afschriftnummer;Datum;Omschrijving;Valuta;Bedrag;Saldo;credit;debet;rekeningnummer tegenpartij;BIC tegenpartij;Naam tegenpartij;Adres tegenpartij;gestructureerde mededeling;Vrije mededeling
BE00987654321098; ;TEST HOLDER;EUR; 02026213;02/10/2026;OVERSCHRIJVING NAAR 02-10 BE45 0000 0000 0000;02/10/2026;-50,00;822,36; ;-50,00;BE45 0000 0000 0000;BIBLBE21XXX;COUNTERPARTY CORP; ; ;inst01336810
BE00987654321098; ;TEST HOLDER;EUR; 02026212;01/10/2026;TERUGBETALING 01-10 WONINGKREDIET REFERENTIE 420-3625993-43;01/10/2026;-579,68;872,36; ;-579,68; ; ; ; ; ;
"""


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


async def test_web_index_and_overview(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check root page
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Wealth Pilot" in resp.text
        assert f"v{__version__}" in resp.text

        # Check version API
        ver_resp = await client.get("/api/version")
        assert ver_resp.status_code == 200
        assert ver_resp.json() == {"version": __version__}

        # Header brand must be shrink-0 to prevent overlap with nav items
        assert "flex items-center space-x-2.5 shrink-0" in resp.text
        # Section labels must be hidden on compact viewports to prevent overflow
        assert 'data-i18n="nav.explore" class="hidden 2xl:inline' in resp.text
        assert 'data-i18n="nav.manage" class="hidden 2xl:inline' in resp.text
        # Secondary quick action buttons hidden on < xl to avoid header overflow
        assert 'openSetupWizard()" class="hidden xl:flex' in resp.text
        assert (
            'href="/guide/index.html" target="_blank" rel="noopener" class="hidden xl:flex'
            in resp.text
        )
        # Ensure numerical values and currency fields in tables never wrap onto multiple lines
        assert "td.font-mono, th.font-mono" in resp.text
        assert "white-space: nowrap !important;" in resp.text

        # Check overview API
        overview_resp = await client.get("/api/overview")
        assert overview_resp.status_code == 200
        data = overview_resp.json()
        assert "net_worth_formatted" in data
        assert "allocations" in data
        assert len(data["allocations"]) >= 3
        assert "trajectory" in data
        assert len(data["trajectory"]) == 31


async def test_kbc_file_upload_and_rebucketing(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("kbc-export.csv", SAMPLE_KBC_CSV.encode("iso-8859-1"), "text/csv")}
        upload_resp = await client.post("/api/ingest/kbc", files=files)
        assert upload_resp.status_code == 200
        res = upload_resp.json()
        assert res["account_number"] == "BE00987654321098"
        assert res["transaction_count"] == 2

        # Check overview shows new transactions
        overview_resp = await client.get("/api/overview")
        data = overview_resp.json()
        assert len(data["transactions"]) == 2

        # Rebucket transaction with learned rule
        tx_id = data["transactions"][0]["id"]
        rebucket_resp = await client.post(
            "/api/transactions/rebucket",
            json={
                "transaction_id": tx_id,
                "target_category": "INVESTMENTS",
                "counterparty_name": "COUNTERPARTY CORP",
                "remember_rule": True,
            },
        )
        assert rebucket_resp.status_code == 200

        # Verify overview shows updated category
        ov2 = (await client.get("/api/overview")).json()
        updated_tx = next(t for t in ov2["transactions"] if t["id"] == tx_id)
        assert updated_tx["category"] == "INVESTMENTS"


async def test_update_target_and_ai_consultation(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Update target weight
        tgt_resp = await client.post(
            "/api/buckets/target",
            json={"bucket_id": "core-etf", "name": "Core World ETFs", "target_weight_pct": 55.0},
        )
        assert tgt_resp.status_code == 200

        # Run AI consultation
        ai_resp = await client.post(
            "/api/ai/advise",
            json={"provider": "gemini", "api_key": "", "question": "How to reach FI faster?"},
        )
        assert ai_resp.status_code == 200
        ai_data = ai_resp.json()
        assert "advice" in ai_data
        assert "Wealth Pilot" in ai_data["advice"]

        # Download generic CSV template
        tmpl_resp = await client.get("/api/template/generic")
        assert tmpl_resp.status_code == 200
        assert "asset_class" in tmpl_resp.text


async def test_settings_and_mcp_endpoints(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch settings
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        settings = resp.json()
        assert "pdt" in settings
        assert "mcp_servers" in settings
        assert "tax" in settings

        # 2. Update settings
        up_resp = await client.post(
            "/api/settings",
            json={
                "tax": {"annual_exemption": 12000.0, "benchmark_date": "2025-12-31"},
                "ai": {"provider": "gemini", "model": "gemini-1.5-pro", "api_key": "secret12345"},
            },
        )
        assert up_resp.status_code == 200

        # Check masked api key
        s2 = (await client.get("/api/settings")).json()
        assert s2["tax"]["annual_exemption"] == 12000.0
        assert "••••" in s2["ai"]["api_key"]

        # 3. Custom MCP Server CRUD
        add_mcp = await client.post(
            "/api/settings/mcp/servers",
            json={
                "name": "Crypto MCP",
                "url": "http://localhost:4000/mcp",
                "transport": "http",
                "auth_token": "token-xyz",
            },
        )
        assert add_mcp.status_code == 200
        server_id = add_mcp.json()["server"]["id"]

        s3 = (await client.get("/api/settings")).json()
        assert any(s["id"] == server_id for s in s3["mcp_servers"])

        # Delete MCP server
        del_resp = await client.delete(f"/api/settings/mcp/servers/{server_id}")
        assert del_resp.status_code == 200

        # 4. PDT Manual Token
        tok_resp = await client.post(
            "/api/auth/pdt/manual",
            json={"auth_token": "test-pdt-token", "mcp_url": "http://localhost:3000/mcp"},
        )
        assert tok_resp.status_code == 200
        s4 = (await client.get("/api/settings")).json()
        assert s4["pdt"]["connected"] is True

        # Disconnect PDT
        disc_resp = await client.post("/api/auth/pdt/disconnect")
        assert disc_resp.status_code == 200
        s5 = (await client.get("/api/settings")).json()
        assert s5["pdt"]["connected"] is False


async def test_built_in_docs_serving(test_app, tmp_path):
    # 1. Test fallback when site is not built
    fallback_app = create_app(
        config_repo=ConfigRepository(config_path=tmp_path / "cfg.yaml"),
        docs_dir=tmp_path / "nonexistent_site",
    )
    fallback_transport = ASGITransport(app=fallback_app)
    async with AsyncClient(transport=fallback_transport, base_url="http://test") as client:
        resp = await client.get("/guide/index.html")
        assert resp.status_code == 200
        assert "Wealth Pilot Documentation" in resp.text
        assert "not been pre-built" in resp.text

        resp_root = await client.get("/guide")
        assert resp_root.status_code == 200
        assert "Wealth Pilot Documentation" in resp_root.text

    # 2. Test mounted static documentation when site/index.html exists
    custom_site = tmp_path / "custom_site"
    custom_site.mkdir(parents=True)
    (custom_site / "index.html").write_text("<html><body>Wealth Pilot Static Docs</body></html>")

    mounted_app = create_app(
        config_repo=ConfigRepository(config_path=tmp_path / "cfg2.yaml"),
        docs_dir=custom_site,
    )
    mounted_transport = ASGITransport(app=mounted_app)
    async with AsyncClient(transport=mounted_transport, base_url="http://test") as client:
        resp = await client.get("/guide/index.html")
        assert resp.status_code == 200
        assert "Wealth Pilot Static Docs" in resp.text


async def test_tax_endpoints(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Tax historical price lookup
        lookup_resp = await client.get("/api/tax/lookup-price?symbol=ASML&date=2025-12-31")
        assert lookup_resp.status_code == 200
        l_data = lookup_resp.json()
        assert "price" in l_data
        assert l_data["symbol"] == "ASML"

        # 2. Tax calculation endpoint
        calc_resp = await client.post(
            "/api/tax/calculate",
            json={
                "symbol": "ASML",
                "current_price": 1200.0,
                "benchmark_price": 900.0,
                "actual_purchase_price": 1050.0,
                "shares_pre_benchmark": 10.0,
                "shares_post_benchmark": 5.0,
                "shares_to_sell": 12.0,
                "annual_exemption": 10000.0,
                "tax_rate_pct": 10.0,
            },
        )
        assert calc_resp.status_code == 200
        c_data = calc_resp.json()
        # 10 shares pre * (1200 - 900) = 3000
        # 2 shares post * (1200 - 1050) = 300
        # Total gain = 3300 <= 10000 -> 0 tax due
        assert c_data["gain_pre_benchmark"] == 3000.0
        assert c_data["gain_post_benchmark"] == 300.0
        assert c_data["total_taxable_gain"] == 3300.0
        assert c_data["tax_due"] == 0.0

        # 3. EquatePlus Zurich forensic sale calculation via API
        eq_resp = await client.post(
            "/api/tax/calculate",
            json={
                "symbol": "ASML",
                "current_price": 1646.0,
                "benchmark_price": 921.40,
                "pre_benchmark_purchase_price": 271.55,
                "shares_pre_benchmark": 4.0,
                "shares_post_benchmark": 0.0,
                "shares_to_sell": 4.0,
                "broker_profile": "EQUATEPLUS_CH",
                "tob_tier": "0.35",
            },
        )
        assert eq_resp.status_code == 200
        eq_data = eq_resp.json()
        assert eq_data["gross_proceeds"] == 6584.0
        assert eq_data["broker_commission"] == 23.04
        assert eq_data["foreign_stamp_tax"] == 9.88
        assert eq_data["broker_payout_before_belgian_tax"] == 6551.08
        assert eq_data["tob_tax"] == 23.04
        assert eq_data["tob_self_declaration_required"] is True
        assert eq_data["historical_fmv_gain"] == 5497.80
        assert eq_data["total_taxable_gain"] == 2898.40
        assert eq_data["fotomoment_exemption_saved"] == 2599.40
        assert eq_data["net_proceeds"] == 6528.04
        assert len(eq_data["legal_citations"]) >= 3
        assert c_data["remaining_exemption"] == 6700.0
