"""Integration tests for Ingestion Gateways and Repositories (Layer 3 - Interface Adapters)."""

from decimal import Decimal
from pathlib import Path

from wealth_pilot.adapters.ingestion.generic_csv import GenericCsvGateway
from wealth_pilot.adapters.ingestion.kbc_csv import KbcCsvGateway
from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.domain.asset import AssetClass

SAMPLE_KBC_CSV_CONTENT = """Rekeningnummer;Rubrieknaam;Naam;Munt;Afschriftnummer;Datum;Omschrijving;Valuta;Bedrag;Saldo;credit;debet;rekeningnummer tegenpartij;BIC tegenpartij;Naam tegenpartij;Adres tegenpartij;gestructureerde mededeling;Vrije mededeling
BE00123456789012; ;ALICE EXAMPLE;EUR; 02026213;02/10/2026;OVERSCHRIJVING NAAR 02-10 BE45 0000 0000 0000;02/10/2026;-50,00;822,36; ;-50,00;BE45 0000 0000 0000;BIBLBE21XXX;BOB RECIPIENT; ; ;inst01336810
BE00123456789012; ;ALICE EXAMPLE;EUR; 02026212;01/10/2026;TERUGBETALING 01-10 WONINGKREDIET REFERENTIE 420-3625993-43;01/10/2026;-579,68;872,36; ;-579,68; ; ; ; ; ;
BE00123456789012; ;ALICE EXAMPLE;EUR; 02026212;01/10/2026;TERUGBETALING 01-10 WONINGKREDIET REFERENTIE 420-3116262-47;01/10/2026;-664,64;1452,04; ;-664,64; ; ; ; ; ;
BE00123456789012; ;ALICE EXAMPLE;EUR; 02026212;01/10/2026;AUTOMATISCHE BETALING 01-10 FLEX BUDGET 420-5415889-95;01/10/2026;-309,60;2116,68; ;-309,60; ; ; ; ; ;
BE00123456789012; ;ALICE EXAMPLE;EUR; 02026210;25/09/2026;OVERSCHRIJVING VAN 25-09 SALARIS GLOBAL TECH CORP;25/09/2026;4800,00;2426,28;4800,00; ;NL26 CITI 0000 00;CITINL2A;GLOBAL TECH CORP; ; ;Salaris September 2026
"""


def test_kbc_csv_gateway_parsing(tmp_path: Path):
    file_path = tmp_path / "kbc_test_export.csv"
    file_path.write_text(SAMPLE_KBC_CSV_CONTENT, encoding="iso-8859-1")

    gateway = KbcCsvGateway()
    data = gateway.parse_file(file_path)

    assert data["account_number"] == "BE00123456789012"
    assert data["account_holder"] == "ALICE EXAMPLE"
    assert data["latest_balance"].amount == Decimal("822.36")
    assert len(data["transactions"]) == 5

    # Check Cash asset created
    cash_asset = data["cash_asset"]
    assert cash_asset.asset_class == AssetClass.CASH
    assert cash_asset.current_value.amount == Decimal("822.36")

    # Check liabilities discovered
    liabilities = data["discovered_liabilities"]
    assert len(liabilities) >= 2
    mortgage_refs = [liab.account_reference for liab in liabilities]
    assert any("420-3625993-43" in ref for ref in mortgage_refs)
    assert any("420-3116262-47" in ref for ref in mortgage_refs)

    # Check cashflow calculation
    cashflow = data["cashflow"]
    assert cashflow.monthly_income.amount == Decimal("4800.00")
    assert cashflow.debt_payments.amount == Decimal("1553.92")  # 579.68 + 664.64 + 309.60


def test_generic_csv_gateway(tmp_path: Path):
    file_path = tmp_path / "generic_portfolio.csv"
    file_path.write_text(
        "name,symbol,isin,asset_class,shares,current_price,current_value,institution\n"
        "Microsoft Corp,MSFT,US5949181045,EQUITY,25,400.00,10000.00,Broker\n"
        "Vanguard All-World,VWCE,IE00BK5BQT80,ETF,300,120.00,36000.00,DEGIRO\n",
        encoding="utf-8",
    )

    gateway = GenericCsvGateway()
    assets = gateway.parse_assets_file(file_path)

    assert len(assets) == 2
    assert assets[0].symbol == "MSFT"
    assert assets[0].current_value.amount == Decimal("10000.00")
    assert assets[1].symbol == "VWCE"
    assert assets[1].asset_class == AssetClass.ETF


def test_config_repository_persistence(tmp_path: Path):
    config_file = tmp_path / "portfolio.yaml"
    repo = ConfigRepository(config_path=config_file)

    # Verify default buckets created
    buckets = repo.load_buckets()
    assert len(buckets) >= 3

    # Add custom bucket and save
    repo.save_bucket_target(
        bucket_id="crypto", name="Crypto Buffer", target_weight_pct=Decimal("5.0")
    )
    reloaded_buckets = repo.load_buckets()
    crypto = next((b for b in reloaded_buckets if b.id == "crypto"), None)
    assert crypto is not None
    assert crypto.target_weight_pct == Decimal("5.00")

    # Test saving custom transaction classification rule
    repo.save_transaction_rule(
        {
            "match_field": "counterparty_name",
            "pattern": "BASIC-FIT",
            "target_category": "SUBSCRIPTION",
        }
    )
    rules = repo.load_transaction_rules()
    assert len(rules) >= 1
    assert rules[0]["pattern"] == "BASIC-FIT"
