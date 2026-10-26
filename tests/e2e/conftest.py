"""Playwright E2E fixtures for testing the live Paslood web application in headless Chromium."""

from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.adapters.repositories.local_db import LocalDbRepository
from wealth_pilot.delivery.web.app import create_app


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live_server(tmp_path):
    """Launch a live FastAPI/Uvicorn server on an ephemeral port with seeded portfolio data."""
    config_file = tmp_path / "e2e_portfolio.yaml"
    repo = ConfigRepository(config_path=config_file)
    repo.save_manual_asset(
        {
            "id": "asset-etf-world",
            "name": "Vanguard FTSE All-World",
            "asset_class": "ETF",
            "current_value": 45000.00,
            "symbol": "VWCE",
            "institution": "Degiro",
        }
    )
    repo.save_manual_asset(
        {
            "id": "asset-cash-emergency",
            "name": "High-Yield Savings Buffer",
            "asset_class": "CASH",
            "current_value": 15000.00,
            "institution": "KBC",
        }
    )
    repo.save_manual_liability(
        {
            "id": "liab-home-mortgage",
            "name": "Primary Residence Mortgage",
            "loan_type": "MORTGAGE",
            "principal_balance": 180000.00,
            "interest_rate_pct": 2.45,
            "monthly_payment": 920.00,
            "institution": "KBC",
        }
    )

    local_db = LocalDbRepository(db_path=tmp_path / "e2e_wealth_pilot.db")
    app = create_app(config_repo=repo, local_db=local_db)
    port = _get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10.0
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)

    yield base_url

    server.should_exit = True
    thread.join(timeout=5.0)


@pytest.fixture
def app_page(page, live_server):
    """Playwright page with strict zero-tolerance listeners for JS pageerrors, console.error, and local 4xx/5xx."""
    js_errors: list[str] = []
    console_errors: list[str] = []
    http_errors: list[str] = []

    page.on("pageerror", lambda exc: js_errors.append(str(exc)))

    def _on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    def _on_response(response):
        if response.url.startswith(live_server) and response.status >= 400:
            http_errors.append(f"{response.status} {response.url}")

    page.on("console", _on_console)
    page.on("response", _on_response)

    yield page

    assert not js_errors, f"Uncaught browser JavaScript errors: {js_errors}"
    assert not console_errors, f"Browser console.error messages: {console_errors}"
    assert not http_errors, f"Failed local HTTP responses: {http_errors}"
