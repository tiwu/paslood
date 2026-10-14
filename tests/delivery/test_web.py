"""Tests for FastAPI Web Application Endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app

SAMPLE_KBC_CSV = """Rekeningnummer;Rubrieknaam;Naam;Munt;Afschriftnummer;Datum;Omschrijving;Valuta;Bedrag;Saldo;credit;debet;rekeningnummer tegenpartij;BIC tegenpartij;Naam tegenpartij;Adres tegenpartij;gestructureerde mededeling;Vrije mededeling
BE90735017192832; ;WUYTENS TIM;EUR; 02026213;02/10/2026;OVERSCHRIJVING NAAR 02-10 BE45 5871 6272 7289;02/10/2026;-50,00;822,36; ;-50,00;BE45 5871 6272 7289;BIBLBE21XXX;TIM WUYTENS; ; ;saxoinst01336810
BE90735017192832; ;WUYTENS TIM;EUR; 02026212;01/10/2026;TERUGBETALING 01-10 WONINGKREDIET REFERENTIE 420-3625993-43;01/10/2026;-579,68;872,36; ;-579,68; ; ; ; ; ;
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
        assert res["account_number"] == "BE90735017192832"
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
                "counterparty_name": "TIM WUYTENS",
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
