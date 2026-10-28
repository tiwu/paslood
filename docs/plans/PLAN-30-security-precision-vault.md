# Architecture Plan — Issue #30: Security Hardening, Decimal Precision & AES-256-GCM Vault v2

- **Issue**: [#30](https://github.com/tiwu/paslood/issues/30)
- **Status**: Implemented (Review Ready)
- **Author**: Antigravity Assistant
- **Target Release**: v0.9.1

---

## 1. Context & Motivation

In historical reviews `docs/reviews/ARCHITECTURE-REVIEW.md` and `docs/reviews/UX-REVIEW.md`, findings **ARCH-01**, **ARCH-08**, **ARCH-09**, and **ARCH-11** identified critical and medium-severity security and precision items:
1. **ARCH-01 (Arbitrary Host Filesystem Sync)**: `/api/backup/cloud-sync` allowed arbitrary filesystem paths in local mode, without sandboxing against directory traversal (`..`) or system roots (`/`, `/etc`, `/usr`).
2. **ARCH-08 (Precision Loss in Currency/Weights)**: Pydantic request models used floating-point types (`float`) for monetary values and target weights; SQLite columns used `REAL` storage instead of exact numeric types.
3. **ARCH-09 (Cryptographic Vault v2)**: The local vault backup used a custom CTR-XOR stream cipher with HMAC-SHA256 (`paslood-encrypted-vault-v1`). Industry standard authenticated encryption (AES-256-GCM) was required while preserving backward-compatible decryption of v1 backups.
4. **ARCH-11 (AI Key Exposure in Query Parameters)**: `GET /api/ai/models` accepted `api_key` as a URL query parameter, risking credential leakage into browser histories and HTTP server access logs.

---

## 2. Architectural Design & Implementation

### 2.1 AES-256-GCM Vault v2 (`config_repo.py`)
- Standardized authenticated encryption using `cryptography.hazmat.primitives.ciphers.aead.AESGCM` with a 96-bit random nonce and 200,000-iteration PBKDF2-HMAC-SHA256 key derivation.
- Emits backup bundles with format tag `"paslood-encrypted-vault-v2"`.
- `decrypt_vault_payload()` supports both v2 AES-256-GCM and legacy v1 CTR-XOR authenticated bundles for seamless backward compatibility.
- Added custom YAML `Decimal` scalar representer to eliminate `!python/object/apply:decimal.Decimal` serialization artifacts in `portfolio.yaml`.

### 2.2 Cloud Sync Filesystem Sandbox (`settings.py`)
- Implemented `_is_safe_cloud_sync_path()`:
  - Requires absolute paths or user home-relative paths starting with `~`.
  - Sandboxes backup sync directories within the user's home directory (`Path.home()`), application data directory (`settings.data_dir`), or system temp directory (`tempfile.gettempdir()`).
  - Forbids syncing directly to bare root directories (`/`, `~`).
  - Strictly blocks system directories (`/etc`, `/usr`, `/bin`, `/sbin`, `/System`, `/dev`, `/proc`, `/sys`, `C:\Windows`, `C:\Program Files`).
  - Rejects traversal escapes (`..`) with HTTP 400.

### 2.3 Strict Decimal Financial Precision (`local_db.py`, `portfolio.py`, `planning.py`)
- Upgraded SQLite table column definitions from `REAL` to `NUMERIC(18,2)` / `NUMERIC(8,4)` and writes formatted as exact numeric strings.
- Upgraded Pydantic request models in `routers/portfolio.py` (`BucketCreateOrUpdateRequest`, `TargetWeightRequest`, `BatchTargetWeightsRequest`, `ManualAssetRequest`, `ManualLiabilityRequest`) and `routers/planning.py` (`ContributionAdviceRequest`, `TaxCalculationRequest`) from `float` to `Decimal`.

### 2.4 Removal of AI Key Query Parameter (`ai.py`)
- Removed `api_key: str | None = None` query parameter from `GET /api/ai/models`.
- Keys are transmitted exclusively via HTTP request headers (`X-AI-API-Key` or `Authorization: Bearer <key>`) or retrieved locally from the decrypted server-side `SecretVault`.

---

## 3. Verification & Metrics

- 199/199 unit, integration, and delivery tests passing.
- 14/14 frontend integrity and Playwright headless E2E browser tests passing.
- 92% total test coverage across `src/paslood/`.
- 100% ruff lint and format check compliance.
- Strict mkdocs documentation build passes with zero warnings.
