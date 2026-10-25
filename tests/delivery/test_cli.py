"""CLI delivery tests for Wealth Pilot."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from wealth_pilot.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Wealth Pilot" in result.stdout
    assert "status" in result.stdout
    assert "advise" in result.stdout
    assert "ingest" in result.stdout
    assert "template" in result.stdout


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Wealth Pilot" in result.stdout
    assert "v0.4.0" in result.stdout


def test_cli_status(tmp_path: Path):
    cfg_file = tmp_path / "portfolio.yaml"
    result = runner.invoke(app, ["status", "--config", str(cfg_file)])
    assert result.exit_code == 0
    assert "Balance Sheet" in result.stdout or "Net Worth" in result.stdout
    assert "Strategic Allocation Buckets" in result.stdout


def test_cli_advise(tmp_path: Path):
    cfg_file = tmp_path / "portfolio.yaml"
    result = runner.invoke(app, ["advise", "--deposit", "2000.0", "--config", str(cfg_file)])
    assert result.exit_code == 0
    assert "Smart Buy-Only Rebalancing" in result.stdout
    assert "Debt vs. Investing Strategy" in result.stdout


def test_cli_template(tmp_path: Path):
    out_file = tmp_path / "test_template.csv"
    result = runner.invoke(app, ["template", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "name,symbol,isin,asset_class" in content


def test_cli_ingest_missing_file():
    result = runner.invoke(app, ["ingest", "non_existent_file.csv"])
    assert result.exit_code != 0
    assert "File not found" in result.stdout


def test_cli_ingest_generic_csv(tmp_path: Path):
    csv_file = tmp_path / "portfolio.csv"
    csv_file.write_text(
        "name,symbol,asset_class,shares,current_value,currency\n"
        "Vanguard All-World,VWCE,ETF,10,1200.00,EUR\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["ingest", str(csv_file)])
    assert result.exit_code == 0
    assert "Generic CSV Parsed Successfully" in result.stdout
    assert "Assets Loaded: 1" in result.stdout


def test_cli_ingest_kbc_csv(tmp_path: Path):
    csv_file = tmp_path / "kbc-export.csv"
    csv_file.write_text(
        "Rekeningnummer;Rubrieknaam;Naam;Munt;Afschriftnummer;Datum;Omschrijving;Valuta;Bedrag;Saldo;credit;debet;rekeningnummer tegenpartij;BIC tegenpartij;Naam tegenpartij;Adres tegenpartij;gestructureerde mededeling;Vrije mededeling\n"
        "BE00987654321098; ;TEST USER;EUR; 02026213;02/10/2026;SALARIS OVERBOEKING;02/10/2026;+3000,00;3000,00;+3000,00; ; ; ;EMPLOYER BV; ; ;\n",
        encoding="iso-8859-1",
    )
    result = runner.invoke(app, ["ingest", str(csv_file)])
    assert result.exit_code == 0
    assert "KBC Statement Parsed Successfully" in result.stdout
    assert "BE00987654321098" in result.stdout


def test_cli_web_dry_run():
    with patch("uvicorn.run") as mock_uvicorn:
        result = runner.invoke(app, ["web", "--port", "9999", "--host", "127.0.0.1"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once()
        assert "http://127.0.0.1:9999" in result.stdout


def test_cli_set_password(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WEALTH_PILOT_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["set-password"], input="newpass123\nnewpass123\n")
    assert result.exit_code == 0
    assert "Password set successfully!" in result.stdout
    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert "WEALTH_PILOT_ADMIN_PASSWORD_HASH=" in content
    hash_val = content.split("WEALTH_PILOT_ADMIN_PASSWORD_HASH=")[1].split("\n")[0].strip()
    from wealth_pilot.delivery.web.auth import verify_password

    assert verify_password("newpass123", hash_val) is True
