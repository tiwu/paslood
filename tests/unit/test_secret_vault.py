"""Unit tests for SecretVault envelope encryption."""

from paslood.adapters.security.secret_vault import SecretVault


def test_secret_vault_roundtrip():
    vault = SecretVault("master-super-secret-key-1234567890")
    secret = "sk-live-123456789-abcdef"
    enc = vault.encrypt(secret, tenant_id="tenant-1")
    assert enc.startswith("enc:")
    assert secret not in enc

    decrypted = vault.decrypt(enc, tenant_id="tenant-1")
    assert decrypted == secret


def test_secret_vault_tenant_isolation():
    vault = SecretVault("master-super-secret-key-1234567890")
    secret = "sk-live-123456789-abcdef"
    enc = vault.encrypt(secret, tenant_id="tenant-1")

    # Decrypting with wrong tenant must fail
    decrypted_wrong_tenant = vault.decrypt(enc, tenant_id="tenant-2")
    assert decrypted_wrong_tenant == ""


def test_secret_vault_plaintext_fallback():
    vault = SecretVault("master-super-secret-key-1234567890")
    assert vault.decrypt("plain-api-key") == "plain-api-key"
    assert vault.decrypt("") == ""
    assert vault.encrypt("") == ""
