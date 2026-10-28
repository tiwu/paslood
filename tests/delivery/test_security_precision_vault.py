"""Comprehensive tests for Milestone 2: Vault AES-256-GCM v2, cloud-sync sandbox, and Decimal precision."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import (
    ConfigRepository,
    decrypt_vault_payload,
    encrypt_vault_payload,
)
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.adapters.settings import AppSettings
from paslood.delivery.web.app import create_app
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.liability import Liability, LoanType
from paslood.domain.money import Money


def _create_legacy_v1_vault(payload: dict, passphrase: str) -> dict:
    """Helper to generate a valid legacy v1 CTR-XOR encrypted bundle."""
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=64)
    enc_key = derived[:32]
    mac_key = derived[32:]

    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    keystream = bytearray()
    block_count = (len(plaintext) + 31) // 32
    for counter in range(block_count):
        counter_bytes = nonce + counter.to_bytes(8, "big")
        keystream.extend(hmac.new(enc_key, counter_bytes, hashlib.sha256).digest())

    ciphertext = bytes(p ^ k for p, k in zip(plaintext, keystream[: len(plaintext)], strict=False))
    tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).hexdigest()

    return {
        "format": "paslood-encrypted-vault-v1",
        "encrypted": True,
        "kdf": "PBKDF2-HMAC-SHA256-200000",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "mac": tag,
    }


def test_vault_v2_encryption_and_decryption_roundtrip():
    payload = {"secret_notes": "Belgian fiscal shield 2026", "balance": 42000.55}
    passphrase = "CorrectHorseBatteryStaple!"

    bundle = encrypt_vault_payload(payload, passphrase)
    assert bundle["format"] == "paslood-encrypted-vault-v2"
    assert bundle["encrypted"] is True
    assert "salt" in bundle
    assert "nonce" in bundle
    assert "ciphertext" in bundle

    # Roundtrip decryption
    decrypted = decrypt_vault_payload(bundle, passphrase)
    assert decrypted == payload


def test_vault_v2_tamper_detection_and_invalid_passphrase():
    payload = {"data": "confidential"}
    passphrase = "ValidPassphrase123"

    bundle = encrypt_vault_payload(payload, passphrase)

    # Wrong passphrase fails
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_vault_payload(bundle, "WrongPassphrase456")

    # Tampered ciphertext fails authentication
    raw_ct = bytearray(base64.b64decode(bundle["ciphertext"]))
    raw_ct[0] ^= 0xFF
    tampered_bundle = dict(bundle)
    tampered_bundle["ciphertext"] = base64.b64encode(bytes(raw_ct)).decode("ascii")

    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_vault_payload(tampered_bundle, passphrase)


def test_vault_v1_backward_compatibility_and_mac_check():
    payload = {"legacy_data": "stored under v1"}
    passphrase = "LegacySecretKey999"

    v1_bundle = _create_legacy_v1_vault(payload, passphrase)
    assert v1_bundle["format"] == "paslood-encrypted-vault-v1"

    # Verify decryptor can read legacy v1 bundle
    restored = decrypt_vault_payload(v1_bundle, passphrase)
    assert restored == payload

    # Tampered legacy bundle fails MAC check
    tampered = dict(v1_bundle)
    tampered["mac"] = "0" * 64
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_vault_payload(tampered, passphrase)


@pytest.mark.asyncio
async def test_cloud_sync_sandbox_path_validation(tmp_path: Path):
    settings = AppSettings(mode="local", data_dir=tmp_path / "data", auth_mode="none")
    repo = ConfigRepository(config_path=tmp_path / "data" / "portfolio.yaml")
    db = LocalDbRepository(db_path=tmp_path / "data" / "paslood.db")
    app = create_app(config_repo=repo, local_db=db, app_settings=settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. System root path rejected
        res_root = await client.post(
            "/api/backup/cloud-sync",
            json={"sync_dir": "/", "passphrase": "test", "action": "push"},
        )
        assert res_root.status_code == 400
        assert "Invalid cloud sync directory" in res_root.json()["detail"]

        # 2. System /etc path rejected
        res_etc = await client.post(
            "/api/backup/cloud-sync",
            json={"sync_dir": "/etc", "passphrase": "test", "action": "push"},
        )
        assert res_etc.status_code == 400
        assert "Invalid cloud sync directory" in res_etc.json()["detail"]

        # 3. Path traversal attempting to escape allowed root rejected
        res_trav = await client.post(
            "/api/backup/cloud-sync",
            json={"sync_dir": "../../etc", "passphrase": "test", "action": "push"},
        )
        assert res_trav.status_code == 400
        assert "Invalid cloud sync directory" in res_trav.json()["detail"]

        # 4. Allowed directory inside tmp_path succeeds
        valid_sync = tmp_path / "cloud_sync_folder"
        res_valid = await client.post(
            "/api/backup/cloud-sync",
            json={
                "sync_dir": str(valid_sync),
                "passphrase": "SuperSecretPassphrase",
                "action": "push",
            },
        )
        assert res_valid.status_code == 200
        assert (valid_sync / "paslood_vault.wpbackup").exists()


@pytest.mark.asyncio
async def test_ai_models_endpoint_ignores_query_param_key(tmp_path: Path):
    settings = AppSettings(mode="local", data_dir=tmp_path, auth_mode="none")
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    app = create_app(config_repo=repo, app_settings=settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "paslood.adapters.ai.llm_client.UniversalAIAdvisorClient.fetch_available_models",
            new_callable=AsyncMock,
            return_value=[{"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"}],
        ) as mock_fetch:
            # Query param api_key must NOT be accepted or passed to client
            res = await client.get("/api/ai/models?provider=gemini&api_key=leaked-in-url")
            assert res.status_code == 200
            # mock_fetch was called with api_key="" (empty, not the query param)
            mock_fetch.assert_called_once_with(provider="gemini", api_key="")

        with patch(
            "paslood.adapters.ai.llm_client.UniversalAIAdvisorClient.fetch_available_models",
            new_callable=AsyncMock,
            return_value=[{"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"}],
        ) as mock_fetch:
            # Header X-AI-API-Key is accepted
            res = await client.get(
                "/api/ai/models?provider=gemini",
                headers={"X-AI-API-Key": "header-safe-key"},
            )
            assert res.status_code == 200
            mock_fetch.assert_called_once_with(provider="gemini", api_key="header-safe-key")

        with patch(
            "paslood.adapters.ai.llm_client.UniversalAIAdvisorClient.fetch_available_models",
            new_callable=AsyncMock,
            return_value=[{"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"}],
        ) as mock_fetch:
            # Authorization Bearer is accepted
            res = await client.get(
                "/api/ai/models?provider=gemini",
                headers={"Authorization": "Bearer bearer-safe-key"},
            )
            assert res.status_code == 200
            mock_fetch.assert_called_once_with(provider="gemini", api_key="bearer-safe-key")


@pytest.mark.asyncio
async def test_decimal_precision_in_models_and_local_db(tmp_path: Path):
    settings = AppSettings(mode="local", data_dir=tmp_path, auth_mode="none")
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    db = LocalDbRepository(db_path=tmp_path / "test.db")
    app = create_app(config_repo=repo, local_db=db, app_settings=settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Bucket targets with exact Decimal precision
        target_res = await client.post(
            "/api/buckets/targets",
            json={
                "targets": {
                    "bucket-world-equity": "33.3333",
                    "bucket-bonds": "66.6667",
                }
            },
        )
        assert target_res.status_code == 200

        # 2. Manual asset with exact Decimal precision
        asset_res = await client.post(
            "/api/assets/manual",
            json={
                "name": "Precision Test Real Estate",
                "asset_class": "REAL_ESTATE",
                "current_value": "450123.85",
                "institution": "Notary Deed",
                "currency": "EUR",
            },
        )
        assert asset_res.status_code == 200

        # 3. Manual liability with exact Decimal precision
        liab_res = await client.post(
            "/api/liabilities/manual",
            json={
                "name": "Precision Mortgage",
                "loan_type": "MORTGAGE",
                "principal_balance": "235456.78",
                "interest_rate_pct": "3.125",
                "monthly_payment": "1234.56",
            },
        )
        assert liab_res.status_code == 200

        # 4. Verify LocalDbRepository stores and reads exact Decimal amounts
        test_asset = Asset(
            id="db-test-asset",
            name="Exact Asset",
            current_value=Money(Decimal("1234567.89"), "EUR"),
            asset_class=AssetClass.REAL_ESTATE,
        )
        db.save_discovered_assets([test_asset])
        loaded_assets = db.get_discovered_assets()
        matched_asset = next(a for a in loaded_assets if a.id == "db-test-asset")
        assert matched_asset.current_value.amount == Decimal("1234567.89")

        test_liability = Liability(
            id="db-test-liab",
            name="Exact Liability",
            principal_balance=Money(Decimal("987654.32"), "EUR"),
            interest_rate_pct=Decimal("4.5678"),
            monthly_payment=Money(Decimal("3210.98"), "EUR"),
            loan_type=LoanType.MORTGAGE,
        )
        db.save_discovered_liabilities([test_liability])
        loaded_liabs = db.get_discovered_liabilities()
        matched_liab = next(liab for liab in loaded_liabs if liab.id == "db-test-liab")
        assert matched_liab.principal_balance.amount == Decimal("987654.32")
        assert matched_liab.interest_rate_pct == Decimal("4.5678")
        assert matched_liab.monthly_payment.amount == Decimal("3210.98")
