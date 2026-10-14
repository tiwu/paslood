"""Tests for Bucket Management, Loan Editing, and Multi-CSV Ingestion Accumulation."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.adapters.repositories.local_db import LocalDbRepository
from wealth_pilot.delivery.web.app import create_app

SAMPLE_CSV_JAN = """Rekeningnummer;Rubrieknaam;Naam;Munt;Afschriftnummer;Datum;Omschrijving;Valuta;Bedrag;Saldo;credit;debet;rekeningnummer tegenpartij;BIC tegenpartij;Naam tegenpartij;Adres tegenpartij;gestructureerde mededeling;Vrije mededeling
BE00123456789012; ;USER;EUR; 02026101;15/01/2026;SALARIS JANUARI;15/01/2026;4500,00;4500,00;4500,00; ; ; ;EMPLOYER; ; ;
BE00123456789012; ;USER;EUR; 02026102;18/01/2026;TERUGBETALING WONINGKREDIET 420-1111111-22;18/01/2026;-600,00;3900,00; ;-600,00; ; ; ; ; ;
"""

SAMPLE_CSV_FEB = """Rekeningnummer;Rubrieknaam;Naam;Munt;Afschriftnummer;Datum;Omschrijving;Valuta;Bedrag;Saldo;credit;debet;rekeningnummer tegenpartij;BIC tegenpartij;Naam tegenpartij;Adres tegenpartij;gestructureerde mededeling;Vrije mededeling
BE00123456789012; ;USER;EUR; 02026201;15/02/2026;SALARIS FEBRUARI;15/02/2026;4500,00;5200,00;4500,00; ; ; ;EMPLOYER; ; ;
BE00123456789012; ;USER;EUR; 02026202;18/02/2026;TERUGBETALING WONINGKREDIET 420-1111111-22;18/02/2026;-600,00;4600,00; ;-600,00; ; ; ; ; ;
"""


@pytest.fixture
def app_with_db(tmp_path: Path):
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    local_db = LocalDbRepository(db_path=tmp_path / "wealth_pilot.db")
    return create_app(config_repo=repo, local_db=local_db)


@pytest.mark.asyncio
async def test_add_and_rename_bucket(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Add a new bucket
        add_resp = await client.post(
            "/api/buckets",
            json={
                "id": "crypto-alternatives",
                "name": "Crypto & Alternatives",
                "target_weight_pct": 5.0,
                "color": "#8B5CF6",
                "drift_tolerance_pct": 2.0,
            },
        )
        assert add_resp.status_code == 200
        data = add_resp.json()
        assert data["status"] == "success"

        # 2. Verify bucket exists in overview
        ov = await client.get("/api/overview")
        allocs = ov.json()["allocations"]
        assert any(
            b["bucket_id"] == "crypto-alternatives" and b["name"] == "Crypto & Alternatives"
            for b in allocs
        )

        # 3. Rename / update bucket
        update_resp = await client.put(
            "/api/buckets/crypto-alternatives",
            json={
                "name": "Digital Assets & Crypto",
                "target_weight_pct": 7.5,
                "color": "#EC4899",
                "drift_tolerance_pct": 2.5,
            },
        )
        assert update_resp.status_code == 200

        # Verify rename reflected
        ov2 = await client.get("/api/overview")
        allocs2 = ov2.json()["allocations"]
        matched = next(b for b in allocs2 if b["bucket_id"] == "crypto-alternatives")
        assert matched["name"] == "Digital Assets & Crypto"
        assert matched["target_weight_pct"] == 7.5
        assert matched["color"] == "#EC4899"

        # 4. Delete bucket
        del_resp = await client.delete("/api/buckets/crypto-alternatives")
        assert del_resp.status_code == 200

        ov3 = await client.get("/api/overview")
        assert not any(b["bucket_id"] == "crypto-alternatives" for b in ov3.json()["allocations"])


@pytest.mark.asyncio
async def test_multi_csv_uploads_accumulate_transactions(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload Month 1 (Jan)
        files_jan = {"file": ("kbc_jan.csv", SAMPLE_CSV_JAN.encode("iso-8859-1"), "text/csv")}
        res1 = await client.post("/api/ingest/kbc", files=files_jan)
        assert res1.status_code == 200
        assert res1.json()["transaction_count"] == 2

        # Upload Month 2 (Feb)
        files_feb = {"file": ("kbc_feb.csv", SAMPLE_CSV_FEB.encode("iso-8859-1"), "text/csv")}
        res2 = await client.post("/api/ingest/kbc", files=files_feb)
        assert res2.status_code == 200
        # Cumulative total should now be 4 transactions!
        assert res2.json()["total_cumulative_transactions"] == 4

        # Overview should return all 4 transactions across both months
        ov = await client.get("/api/overview")
        txs = ov.json()["transactions"]
        assert len(txs) == 4
        dates = {t["date"] for t in txs}
        assert "2026-01-15" in dates
        assert "2026-02-15" in dates


@pytest.mark.asyncio
async def test_kbc_detected_loans_have_zero_fake_balance_and_are_editable(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("kbc_jan.csv", SAMPLE_CSV_JAN.encode("iso-8859-1"), "text/csv")}
        await client.post("/api/ingest/kbc", files=files)

        ov = await client.get("/api/overview")
        liabs = ov.json()["liabilities"]
        assert len(liabs) >= 1
        mortgage = next(liab for liab in liabs if "420-1111111-22" in liab["name"])

        # Monthly payment is known from CSV:
        assert mortgage["monthly_payment"] == 600.0
        # Principal balance and APR are not fabricated!
        assert mortgage["principal_balance"] == 0.0
        assert mortgage["interest_rate_pct"] == 0.0

        # User edits liability with their real numbers
        edit_resp = await client.post(
            "/api/liabilities/manual",
            json={
                "id": mortgage["id"],
                "name": mortgage["name"],
                "loan_type": "MORTGAGE",
                "principal_balance": 175000.0,
                "interest_rate_pct": 1.95,
                "monthly_payment": 600.0,
                "institution": "KBC Bank",
                "account_reference": "420-1111111-22",
            },
        )
        assert edit_resp.status_code == 200

        # Verify updated in overview
        ov2 = await client.get("/api/overview")
        updated_mortgage = next(
            liab for liab in ov2.json()["liabilities"] if liab["id"] == mortgage["id"]
        )
        assert updated_mortgage["principal_balance"] == 175000.0
        assert updated_mortgage["interest_rate_pct"] == 1.95
