"""Unit tests for AppSettings configuration."""

from pathlib import Path

from paslood.adapters.settings import AppSettings


def test_settings_defaults(tmp_path: Path):
    s = AppSettings(data_dir=tmp_path)
    assert s.mode == "local"
    assert s.auth_mode == "none"
    assert s.data_dir == tmp_path
    assert len(s.secret_key) > 0
    assert not s.has_oauth
    assert not s.has_password


def test_settings_allowed_emails():
    s = AppSettings(allowed_emails={"alice@example.com", "bob@example.com"})
    assert s.is_email_allowed("alice@example.com")
    assert s.is_email_allowed("ALICE@EXAMPLE.COM")
    assert s.is_email_allowed("bob@example.com")
    assert not s.is_email_allowed("mallory@example.com")


def test_settings_from_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PASLOOD_MODE", "self_host")
    monkeypatch.setenv("PASLOOD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PASLOOD_AUTH_MODE", "password")
    monkeypatch.setenv("PASLOOD_ALLOWED_EMAILS", "user1@test.com, user2@test.com ")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")

    s = AppSettings.from_env()
    assert s.mode == "self_host"
    assert s.auth_mode == "password"
    assert s.data_dir == tmp_path
    assert s.has_google_oauth
    assert not s.has_github_oauth
    assert s.is_email_allowed("user1@test.com")
    assert not s.is_email_allowed("intruder@test.com")


def test_paslood_env_variables_take_precedence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PASLOOD_MODE", "self_host")
    monkeypatch.setenv("PASLOOD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PASLOOD_AUTH_MODE", "hybrid")
    monkeypatch.setenv("PASLOOD_ALLOWED_EMAILS", "tim@paslood.be")
    monkeypatch.setenv("PASLOOD_SECRET_KEY", "super-secret-paslood-key")

    s = AppSettings.from_env()
    assert s.mode == "self_host"
    assert s.auth_mode == "hybrid"
    assert s.data_dir == tmp_path
    assert s.secret_key == "super-secret-paslood-key"
    assert s.is_email_allowed("tim@paslood.be")
