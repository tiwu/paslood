"""Tests for safe defaults in the config repository."""

from paslood.adapters.repositories.config_repo import ConfigRepository


def test_new_portfolio_starts_without_assumed_assets(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")

    assert repo.load_manual_assets() == []
