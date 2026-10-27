"""Unit tests for CLI web bind security guard."""

from unittest.mock import patch

from typer.testing import CliRunner

from paslood.cli import app

runner = CliRunner()


def test_cli_bind_guard_blocks_external_host_without_auth(monkeypatch):
    monkeypatch.setenv("PASLOOD_AUTH_MODE", "none")
    monkeypatch.setenv("PASLOOD_ADMIN_PASSWORD_HASH", "")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "")
    monkeypatch.setenv("META_CLIENT_ID", "")

    result = runner.invoke(app, ["web", "--host", "0.0.0.0"])
    assert result.exit_code == 1
    assert "SECURITY REFUSAL" in result.output


def test_cli_bind_guard_allows_with_override(monkeypatch):
    monkeypatch.setenv("PASLOOD_AUTH_MODE", "none")
    monkeypatch.setenv("PASLOOD_ADMIN_PASSWORD_HASH", "")

    with patch("uvicorn.run") as mock_uvicorn:
        result = runner.invoke(app, ["web", "--host", "0.0.0.0", "--allow-unauthenticated"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once()


def test_cli_bind_guard_allows_localhost_by_default(monkeypatch):
    monkeypatch.setenv("PASLOOD_AUTH_MODE", "none")
    with patch("uvicorn.run") as mock_uvicorn:
        result = runner.invoke(app, ["web", "--host", "127.0.0.1"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once()
