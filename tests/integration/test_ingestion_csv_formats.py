"""Integration and delivery tests for KBC Credit Card, KBC Position Overview, and Bunq CSV ingestion (#37)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.ingestion.generic_csv import GenericCsvGateway
from paslood.adapters.ingestion.kbc_csv import KbcCsvGateway
from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app
from paslood.domain.asset import AssetClass
from paslood.domain.balance_sheet import Money

KBC_CREDIT_CARD_SAMPLE = (
    "kredietkaart;kaarthouder;uitgavenstaat;datum verrichting;Datum verrekening;"
    "bedrag;credit;debet;munt;koers;bedrag in EUR;Kosten op verrichting;"
    "Handelaar;locatie;land;toelichting\r"
    "5489 49XX XXXX 9128;TIM WUYTS;03/04/2026;19/03/2026;19/03/2026;"
    "-881422,500000000;;-881422,500000000;MGA;4908,79093339;-179,56;2,87 EUR;"
    "LE GRAND BLEU;NOSY BE;Madagaskar;5489 49XX XXXX 9128 - AFREKENING VAN 03/04/2026\r"
    "                   ;         ;04/05/2026;10/04/2026;10/04/2026;"
    "318,01;318,01;;EUR;1,00000000;318,01;;"
    "TERUGBETALING VIA JE KBC FLEX BUDGET; ; ; - AFREKENING VAN 04/05/2026\r"
    "5489 49XX XXXX 9128;TIM WUYTS;04/05/2026;26/04/2026;27/04/2026;"
    "100,00;100,00;;EUR;1,00000000;100,00;;"
    "TENERIFE MOTO MUNDOISL;ADEJE;Spanje;5489 49XX XXXX 9128 - AFREKENING VAN 04/05/2026\r"
    "5489 49XX XXXX 9128;TIM WUYTS;04/05/2026;26/04/2026;27/04/2026;"
    "100,00;100,00;;EUR;1,00000000;100,00;;"
    "TENERIFE MOTO MUNDOISL;ADEJE;Spanje;5489 49XX XXXX 9128 - AFREKENING VAN 04/05/2026\r"
    "5489 49XX XXXX 9128;TIM WUYTS;03/07/2026;12/06/2026;15/06/2026;"
    "-5,99;;-5,99;EUR;1,00000000;-5,99;;"
    "GOOGLE*GOOGLE PLAY APP;DUBLIN;Ierland;5489 49XX XXXX 9128 - AFREKENING VAN 03/07/2026\r"
)

KBC_POSITION_OVERVIEW_SAMPLE = (
    "sep=;\n"
    "Positie-overzicht op 28-10-2026\n"
    "Portefeuille;KBC Easy Invest Service 740140811341\n"
    "Titularis;TIM WUYTS\n"
    "Meest recente waardering;12.409,07 EUR\n"
    "Cash (inclusief verworven intrest);370,31 EUR\n"
    "Beleggingsfondsen;12.038,76 EUR\n"
    "\n"
    "\n"
    "Productklasse;Waardeinfo/ISIN;Naam product;Aantal;Nominaal;Devies/percentage;"
    "Gemiddelde aankoopkoers;Devies/percentage;Huidige indicatieve koers;Devies/percentage;"
    "Huidige waarde in EUR;Devies/percentage;Verlopen rente in EUR;Devies/percentage;"
    "NGR in %;NGR in EUR;Begindatum;Eindvervaldag;Rentevoet;YTD;op rekening;productscore\n"
    "spaarrekening;BE63 7450 2071 3108 EUR;WUYTENS TIM;;364,29;EUR;;;;;364,29;EUR;"
    "6,02;EUR;0,00;0,00;;;0,40%;0,00%;J;1\n"
    "beleggingsfonds;BE0026535543;KBC PENSION SAVINGS FUND RESPONSIBLE INVESTING;"
    "19,5143;;;485,52;EUR;616,92;EUR;12.038,76;EUR;0,00;EUR;27,06;2.564,23;"
    "30-05-2017;;0,00%;3,37%;J;4\n"
)

BUNQ_CSV_SAMPLE = (
    '"Date","Interest Date","Amount","Account","Counterparty","Name","Description"\n'
    '"2023-07-17","2023-07-17","1.000,00","NL31BUNQ2093809982","BE90735017192832","WUYTS TIM","bunq geld"\n'
    '"2023-07-20","2023-07-20","-3,50","NL31BUNQ2093809982","","Burgers Zoo","Burgers Zoo, NLD"\n'
    '"2023-07-20","2023-07-20","-3,50","NL31BUNQ2093809982","","Burgers Zoo","Burgers Zoo, NLD"\n'
    '"2023-07-25","2023-07-25","0,29","NL28BUNQ2120824827","NL05BUNQ2025216006","bunq","bunq Payday 2023-07-25"\n'
    '"2023-07-26","2023-07-26","-2,99","NL31BUNQ2093809982","","GOOGLE *Google Play","GOOGLE *Google Play, IRL"\n'
)


def test_kbc_credit_card_csv_parsing(tmp_path: Path) -> None:
    """KbcCsvGateway parses credit card exports with MGA currency, skips settlement rows, and keeps duplicate refunds."""
    csv_file = tmp_path / "kbc_cc.csv"
    csv_file.write_text(KBC_CREDIT_CARD_SAMPLE, encoding="iso-8859-1")
    gw = KbcCsvGateway()
    res = gw.parse_file(csv_file)
    txs = res["transactions"]

    # 5 rows minus 1 settlement row ("TERUGBETALING VIA JE KBC FLEX BUDGET") = 4 transactions
    assert len(txs) == 4

    # Row 1: MGA foreign currency converted via 'bedrag in EUR'
    assert txs[0].amount == Money(Decimal("-179.56"), "EUR")
    assert txs[0].counterparty_name == "LE GRAND BLEU"
    assert txs[0].date == "2026-03-19"
    assert txs[0].account_id == "5489 49XX XXXX 9128"
    assert "NOSY BE" in txs[0].description

    # Rows 2 & 3: Two identical same-day €100 refunds from TENERIFE MOTO MUNDOISL have distinct deterministic IDs
    assert txs[1].amount == Money(Decimal("100.00"), "EUR")
    assert txs[2].amount == Money(Decimal("100.00"), "EUR")
    assert txs[1].id != txs[2].id

    # Row 4: Google Play App
    assert txs[3].amount == Money(Decimal("-5.99"), "EUR")
    assert txs[3].counterparty_name == "GOOGLE*GOOGLE PLAY APP"


def test_kbc_position_overview_csv_parsing(tmp_path: Path) -> None:
    """GenericCsvGateway parses KBC Positie-overzicht with sep=; preamble and Belgian decimal numbers."""
    csv_file = tmp_path / "positie.csv"
    csv_file.write_text(KBC_POSITION_OVERVIEW_SAMPLE, encoding="utf-8")
    gw = GenericCsvGateway()
    assets = gw.parse_assets_file(csv_file)

    assert len(assets) == 2

    cash_asset = next(a for a in assets if a.asset_class == AssetClass.CASH)
    assert cash_asset.id == "kbc-checking-BE63745020713108"
    assert cash_asset.current_value == Money(Decimal("364.29"), "EUR")

    pension_asset = next(a for a in assets if a.asset_class == AssetClass.FIXED_INCOME)
    assert pension_asset.isin == "BE0026535543"
    assert pension_asset.name == "KBC PENSION SAVINGS FUND RESPONSIBLE INVESTING"
    assert pension_asset.current_value == Money(Decimal("12038.76"), "EUR")


def test_bunq_csv_gateway_parsing(tmp_path: Path) -> None:
    """BunqCsvGateway parses Bunq CSV exports, preserves duplicate same-day transactions, and extracts accounts."""
    from paslood.adapters.ingestion.bunq_csv import BunqCsvGateway

    csv_file = tmp_path / "bunq.csv"
    csv_file.write_text(BUNQ_CSV_SAMPLE, encoding="utf-8")
    gw = BunqCsvGateway()
    res = gw.parse_file(csv_file)
    txs = res["transactions"]

    assert len(txs) == 5
    assert txs[0].amount == Money(Decimal("1000.00"), "EUR")
    assert txs[0].account_id == "NL31BUNQ2093809982"
    assert txs[0].counterparty_name == "WUYTS TIM"
    assert txs[0].date == "2023-07-17"

    # Two identical Burgers Zoo purchases on 2023-07-20 have distinct IDs
    assert txs[1].amount == Money(Decimal("-3.50"), "EUR")
    assert txs[2].amount == Money(Decimal("-3.50"), "EUR")
    assert txs[1].id != txs[2].id

    # Re-parsing produces identical IDs for idempotency
    res_again = gw.parse_file(csv_file)
    txs_again = res_again["transactions"]
    assert [t.id for t in txs] == [t.id for t in txs_again]


@pytest.mark.asyncio
async def test_ingest_endpoints_auto_detect_and_persist(tmp_path: Path) -> None:
    """Endpoints auto-detect KBC credit card, Positie-overzicht, and Bunq CSVs even if posted to another route."""
    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)
    test_app = create_app(config_repo=repo, local_db=db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload KBC credit card CSV to /api/ingest/kbc
        res_cc = await client.post(
            "/api/ingest/kbc",
            files={
                "file": (
                    "export_KBC-Kredietkaart.csv",
                    KBC_CREDIT_CARD_SAMPLE.encode("iso-8859-1"),
                    "text/csv",
                )
            },
        )
        assert res_cc.status_code == 200
        data_cc = res_cc.json()
        assert data_cc["transactions_processed"] == 4
        assert data_cc["new_transactions"] == 4

        # 2. Upload Bunq CSV to /api/ingest/bunq
        res_bunq = await client.post(
            "/api/ingest/bunq",
            files={"file": ("bunq-afschrift.csv", BUNQ_CSV_SAMPLE.encode("utf-8"), "text/csv")},
        )
        assert res_bunq.status_code == 200
        data_bunq = res_bunq.json()
        assert data_bunq["transactions_processed"] == 5
        assert data_bunq["new_transactions"] == 5

        # Re-uploading same Bunq CSV adds 0 new transactions (idempotent)
        res_bunq_dup = await client.post(
            "/api/ingest/bunq",
            files={"file": ("bunq-afschrift.csv", BUNQ_CSV_SAMPLE.encode("utf-8"), "text/csv")},
        )
        assert res_bunq_dup.status_code == 200
        assert res_bunq_dup.json()["new_transactions"] == 0

        # 3. Upload Positie-overzicht CSV to /api/ingest/generic
        res_pos = await client.post(
            "/api/ingest/generic",
            files={
                "file": (
                    "Positie-overzicht op 28-10-2026.csv",
                    KBC_POSITION_OVERVIEW_SAMPLE.encode("utf-8"),
                    "text/csv",
                )
            },
        )
        assert res_pos.status_code == 200
        data_pos = res_pos.json()
        assert data_pos["asset_count"] == 2
        assert abs(data_pos["total_value"] - 12403.05) < 0.01
