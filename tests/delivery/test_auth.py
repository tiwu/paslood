"""Delivery integration tests for Authentication and Authorization."""

from pathlib import Path

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.adapters.settings import AppSettings
from wealth_pilot.delivery.web.app import create_app
from wealth_pilot.delivery.web.auth import hash_password


@pytest.fixture
def auth_app(tmp_path: Path):
    pwd_hash = hash_password("secret-master-pass")
    settings = AppSettings(
        mode="self_host",
        data_dir=tmp_path,
        secret_key="test-auth-secret-key-abcdef",
        auth_mode="password",
        admin_password_hash=pwd_hash,
        google_client_id="g-id",
        google_client_secret="g-secret",
        github_client_id="gh-id",
        github_client_secret="gh-secret",
        meta_client_id="meta-id",
        meta_client_secret="meta-secret",
        allowed_emails={"owner@example.com"},
    )
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    return create_app(config_repo=repo, app_settings=settings)


@pytest.mark.asyncio
async def test_unauthenticated_access_is_blocked(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # API request returns 401
        res_api = await client.get("/api/overview")
        assert res_api.status_code == 401

        # Page request redirects to /login
        res_page = await client.get("/")
        assert res_page.status_code == 307
        assert res_page.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_password_login_flow(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Invalid password
        res_fail = await client.post(
            "/auth/login", data={"password": "wrong-password"}, follow_redirects=False
        )
        assert res_fail.status_code == 303
        assert "error=Invalid" in res_fail.headers["location"]

        # 2. Valid password
        res_ok = await client.post(
            "/auth/login", data={"password": "secret-master-pass"}, follow_redirects=False
        )
        assert res_ok.status_code == 303
        assert res_ok.headers["location"] == "/"
        assert "wp_session=" in res_ok.headers.get("set-cookie", "")

        # Extract cookie
        cookie_val = res_ok.cookies.get("wp_session")
        assert cookie_val is not None

        # 3. Access authenticated endpoints with cookie
        res_authed_page = await client.get("/", cookies={"wp_session": cookie_val})
        assert res_authed_page.status_code == 200

        res_authed_api = await client.get("/api/overview", cookies={"wp_session": cookie_val})
        assert res_authed_api.status_code == 200
        assert "net_worth_value" in res_authed_api.json()

        # 4. Logout
        res_logout = await client.get(
            "/auth/logout", cookies={"wp_session": cookie_val}, follow_redirects=False
        )
        assert res_logout.status_code == 303
        assert "/login" in res_logout.headers["location"]


@pytest.mark.asyncio
async def test_google_oauth_callback(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initiate login to obtain state token
        res_login = await client.get("/auth/google/login", follow_redirects=False)
        assert res_login.status_code == 303
        loc = res_login.headers["location"]
        assert "accounts.google.com" in loc
        import urllib.parse

        parsed = urllib.parse.urlparse(loc)
        qs = urllib.parse.parse_qs(parsed.query)
        state_token = qs["state"][0]

        # Mock token & profile exchange with respx
        with respx.mock(assert_all_called=False) as respx_mock:
            respx_mock.post("https://oauth2.googleapis.com/token").mock(
                return_value=Response(200, json={"access_token": "g-tok", "id_token": "g-id-tok"})
            )
            respx_mock.get("https://www.googleapis.com/oauth2/v3/userinfo").mock(
                return_value=Response(
                    200,
                    json={"sub": "g-12345", "email": "owner@example.com", "name": "Google Owner"},
                )
            )

            res_cb = await client.get(
                f"/auth/google/callback?code=mock-code&state={state_token}", follow_redirects=False
            )
            assert res_cb.status_code == 303
            assert "#dashboard" in res_cb.headers["location"]
            assert "wp_session=" in res_cb.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_oauth_unauthorized_email_rejected(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.get("/auth/google/login", follow_redirects=False)
        import urllib.parse

        parsed = urllib.parse.urlparse(res_login.headers["location"])
        state_token = urllib.parse.parse_qs(parsed.query)["state"][0]

        with respx.mock(assert_all_called=False) as respx_mock:
            respx_mock.post("https://oauth2.googleapis.com/token").mock(
                return_value=Response(200, json={"access_token": "g-tok"})
            )
            respx_mock.get("https://www.googleapis.com/oauth2/v3/userinfo").mock(
                return_value=Response(
                    200,
                    json={"sub": "g-999", "email": "stranger@not-allowed.com", "name": "Stranger"},
                )
            )

            res_cb = await client.get(
                f"/auth/google/callback?code=mock-code&state={state_token}", follow_redirects=False
            )
            assert res_cb.status_code == 303
            assert "error=Email+not+authorized" in res_cb.headers["location"]


@pytest.mark.asyncio
async def test_github_oauth_callback(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.get("/auth/github/login", follow_redirects=False)
        assert res_login.status_code == 303
        import urllib.parse

        parsed = urllib.parse.urlparse(res_login.headers["location"])
        state_token = urllib.parse.parse_qs(parsed.query)["state"][0]

        with respx.mock(assert_all_called=False) as respx_mock:
            respx_mock.post("https://github.com/login/oauth/access_token").mock(
                return_value=Response(200, json={"access_token": "gh-tok"})
            )
            respx_mock.get("https://api.github.com/user").mock(
                return_value=Response(
                    200, json={"id": 777, "email": "owner@example.com", "login": "ghuser"}
                )
            )

            res_cb = await client.get(
                f"/auth/github/callback?code=mock-gh-code&state={state_token}",
                follow_redirects=False,
            )
            assert res_cb.status_code == 303
            assert "#dashboard" in res_cb.headers["location"]


@pytest.mark.asyncio
async def test_meta_oauth_callback(auth_app):
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.get("/auth/meta/login", follow_redirects=False)
        assert res_login.status_code == 303
        import urllib.parse

        parsed = urllib.parse.urlparse(res_login.headers["location"])
        state_token = urllib.parse.parse_qs(parsed.query)["state"][0]

        with respx.mock(assert_all_called=False) as respx_mock:
            respx_mock.get("https://graph.facebook.com/v19.0/oauth/access_token").mock(
                return_value=Response(200, json={"access_token": "meta-tok"})
            )
            respx_mock.get("https://graph.facebook.com/me").mock(
                return_value=Response(
                    200, json={"id": "meta-888", "email": "owner@example.com", "name": "Meta User"}
                )
            )

            res_cb = await client.get(
                f"/auth/meta/callback?code=mock-meta-code&state={state_token}",
                follow_redirects=False,
            )
            assert res_cb.status_code == 303
            assert "#dashboard" in res_cb.headers["location"]


def test_auth_manager_unit(tmp_path: Path):
    from wealth_pilot.adapters.settings import AppSettings
    from wealth_pilot.delivery.web.auth import AuthManager

    settings = AppSettings(
        data_dir=tmp_path,
        secret_key="super-secret-key-123",
        mode="self_host",
        auth_mode="password",
    )
    am = AuthManager(settings=settings)

    # Session creation & verification
    tok = am.create_session(user_id="user-1", tenant_id="tenant-1")
    ctx = am.verify_session(tok)
    assert ctx is not None
    assert ctx.tenant_id == "tenant-1"

    # Invalid session tokens
    assert am.verify_session("tampered.token.abc") is None
    assert am.verify_session("invalid") is None

    # Deletion
    am.delete_session(tok)
    assert am.verify_session(tok) is None

    # Rate limiting
    ip = "192.168.1.100"
    for _ in range(5):
        assert am.check_rate_limit(ip, max_attempts=5) is True
    assert am.check_rate_limit(ip, max_attempts=5) is False

    # User creation and lookup
    u1, t1 = am.get_or_create_user(
        provider="google", sub="g-sub-1", email="u1@example.com", display_name="User One"
    )
    u2, t2 = am.get_or_create_user(
        provider="google", sub="g-sub-1", email="u1@example.com", display_name="User One"
    )
    assert u1.id == u2.id
    assert u1.email == "u1@example.com"
    assert t1 == t2
