"""Tenant-scoped envelope encryption secret vault using HKDF and AES-256-GCM."""

from __future__ import annotations

import base64
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class SecretVault:
    """Provides authenticated per-tenant secret encryption at rest."""

    def __init__(self, master_key: str | bytes) -> None:
        if isinstance(master_key, str):
            self.master_key = master_key.encode("utf-8")
        else:
            self.master_key = master_key

    def _derive_tenant_key(self, tenant_id: str) -> bytes:
        salt = tenant_id.encode("utf-8")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"paslood-secret-vault-v1",
        )
        return hkdf.derive(self.master_key)

    def encrypt(self, plaintext: str, tenant_id: str = "default") -> str:
        """Encrypts a plaintext secret into a base64 string."""
        if not plaintext:
            return ""
        key = self._derive_tenant_key(tenant_id)
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        bundle = nonce + ciphertext
        return "enc:" + base64.b64encode(bundle).decode("ascii")

    def decrypt(self, encoded: str, tenant_id: str = "default") -> str:
        """Decrypts a base64 ciphertext string back to plaintext."""
        if not encoded:
            return ""
        if not encoded.startswith("enc:"):
            # Plaintext fallback for legacy / unencrypted secrets
            return encoded
        try:
            raw_bundle = base64.b64decode(encoded.removeprefix("enc:"))
            if len(raw_bundle) < 28:
                return ""
            nonce = raw_bundle[:12]
            ciphertext = raw_bundle[12:]
            key = self._derive_tenant_key(tenant_id)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception:
            return ""
