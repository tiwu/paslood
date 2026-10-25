"""PDT OAuth 2.0 with PKCE Authentication Manager."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse
from typing import Any

import httpx

from wealth_pilot import __version__

AUTH_ENDPOINT = "https://auth.portfoliodividendtracker.com/oauth/authorize"
TOKEN_ENDPOINT = "https://auth.portfoliodividendtracker.com/oauth/token"
REGISTER_ENDPOINT = "https://mcp.portfoliodividendtracker.com/oauth/register"
USER_AGENT = (
    f"WealthPilot/{__version__} (Strategic Wealth & Allocation Guidance Platform; Python httpx)"
)


def generate_pkce_pair() -> tuple[str, str]:
    """Generate code_verifier and code_challenge for OAuth PKCE (RFC 7636)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


class PdtAuthManager:
    """Manages dynamic OAuth client registration, authorization URLs, and token exchange for PDT MCP."""

    @staticmethod
    async def register_client(redirect_uri: str, additional_uris: list[str] | None = None) -> str:
        """Dynamically registers an OAuth client with the PDT MCP service."""
        uris = [redirect_uri]
        if additional_uris:
            for u in additional_uris:
                if u not in uris:
                    uris.append(u)
        payload = {
            "client_name": "Wealth Pilot Financial Planner",
            "redirect_uris": uris,
            "scope": "mcp:use",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                REGISTER_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("client_id", ""))

    @staticmethod
    def build_authorization_url(
        client_id: str, redirect_uri: str, state: str, challenge: str
    ) -> str:
        """Builds the PDT OAuth 2.0 authorization URL with PKCE parameters."""
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "mcp:use",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    @staticmethod
    async def exchange_code(
        client_id: str, code: str, verifier: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchanges authorization code and PKCE verifier for bearer tokens."""
        payload = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                TOKEN_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            tokens = resp.json()
            tokens["client_id"] = client_id
            tokens["expires_at"] = time.time() + float(tokens.get("expires_in", 3600))
            return tokens

    @staticmethod
    async def refresh_tokens(client_id: str, refresh_token: str) -> dict[str, Any]:
        """Refreshes expired access tokens using a valid refresh token."""
        payload = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                TOKEN_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            new_tokens = resp.json()
            new_tokens["client_id"] = client_id
            new_tokens["expires_at"] = time.time() + float(new_tokens.get("expires_in", 3600))
            return new_tokens
