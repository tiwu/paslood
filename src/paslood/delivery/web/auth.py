"""Authentication and authorization module for Paslood (OAuth2/OIDC + Local Passphrase)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import time
from typing import Any

from paslood.adapters.settings import AppSettings
from paslood.domain.identity import TenantContext, TenantRole, User


def hash_password(password: str) -> str:
    """Generates a PBKDF2-HMAC-SHA256 password hash."""
    import secrets

    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000, dklen=32)
    return f"pbkdf2:sha256:100000${base64.b64encode(salt).decode('ascii')}${base64.b64encode(derived).decode('ascii')}"


def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against PBKDF2 or plaintext (for legacy bootstrap)."""
    if not hashed:
        return False
    if not hashed.startswith("pbkdf2:sha256:"):
        # Direct comparison fallback if user set plaintext via env var
        return hmac.compare_digest(password, hashed)
    try:
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        iterations = int(parts[0].split(":")[2])
        salt = base64.b64decode(parts[1])
        expected = base64.b64decode(parts[2])
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


class AuthManager:
    """Manages identity storage, OAuth state, and session tokens."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.db_path = self.settings.data_dir / "auth.db"
        self._rate_limits: dict[str, list[float]] = {}
        self._init_db()

    def _init_db(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE,
                    display_name TEXT,
                    avatar_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_identities (
                    provider TEXT,
                    provider_sub TEXT,
                    user_id TEXT,
                    email TEXT,
                    PRIMARY KEY (provider, provider_sub),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    tenant_id TEXT,
                    expires_at REAL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_token TEXT PRIMARY KEY,
                    data_json TEXT,
                    expires_at REAL
                )
                """
            )
            conn.commit()

    def check_rate_limit(
        self, client_ip: str, max_attempts: int = 10, window_secs: int = 300
    ) -> bool:
        """Returns True if within rate limit, False if rate limited."""
        now = time.time()
        attempts = self._rate_limits.setdefault(client_ip, [])
        self._rate_limits[client_ip] = [t for t in attempts if t > (now - window_secs)]
        if len(self._rate_limits[client_ip]) >= max_attempts:
            return False
        self._rate_limits[client_ip].append(now)
        return True

    def is_owner_email(self, email: str) -> bool:
        """Only enable OAuth for one explicitly configured owner identity."""
        return len(self.settings.allowed_emails) == 1 and self.settings.is_email_allowed(email)

    def is_owner_context(self, tenant: TenantContext) -> bool:
        """Reject legacy sessions that do not belong to the configured owner."""
        if tenant.user_id == "admin" and self.settings.has_password:
            return True
        return self.is_owner_email(tenant.email)

    def create_session(
        self, user_id: str, tenant_id: str | None = None, duration_secs: int = 86400 * 30
    ) -> str:
        session_id = hashlib.sha256(
            f"{user_id}:{time.time()}:{self.settings.secret_key}".encode()
        ).hexdigest()
        expires_at = time.time() + duration_secs
        effective_tenant = tenant_id or user_id or "default"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, user_id, tenant_id, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, user_id, effective_tenant, expires_at),
            )
            conn.commit()

        # Sign token
        payload = f"{session_id}:{int(expires_at)}"
        sig = hmac.new(
            self.settings.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"{payload}:{sig}"

    def verify_session(self, token: str) -> TenantContext | None:
        if not token:
            return None
        parts = token.split(":")
        if len(parts) != 3:
            return None
        session_id, expires_str, sig = parts
        try:
            expires_at = float(expires_str)
        except ValueError:
            return None

        if expires_at < time.time():
            return None

        payload = f"{session_id}:{expires_str}"
        expected_sig = hmac.new(
            self.settings.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT s.user_id, s.tenant_id, u.email FROM sessions s LEFT JOIN users u ON s.user_id = u.id WHERE s.session_id = ? AND s.expires_at > ?",
                (session_id, time.time()),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return TenantContext(
                tenant_id=row["tenant_id"] or "default",
                user_id=row["user_id"] or "default",
                email=row["email"] or "local@paslood",
                role=TenantRole.OWNER,
            )

    def delete_session(self, token: str) -> None:
        parts = token.split(":")
        if parts:
            session_id = parts[0]
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()

    def save_oauth_state(self, state_token: str, data: dict[str, Any], ttl_secs: int = 600) -> None:
        """Stores temporary OAuth state in SQLite with expiration."""
        expires_at = time.time() + ttl_secs
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO oauth_states (state_token, data_json, expires_at) VALUES (?, ?, ?)",
                (state_token, json.dumps(data), expires_at),
            )
            conn.commit()

    def pop_oauth_state(self, state_token: str) -> dict[str, Any] | None:
        """Retrieves and deletes OAuth state if valid and not expired."""
        if not state_token:
            return None
        now = time.time()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_json FROM oauth_states WHERE state_token = ? AND expires_at > ?",
                (state_token, now),
            )
            row = cursor.fetchone()
            conn.execute(
                "DELETE FROM oauth_states WHERE state_token = ? OR expires_at <= ?",
                (state_token, now),
            )
            conn.commit()
            if row:
                try:
                    return json.loads(row["data_json"])
                except Exception:
                    return None
            return None

    def get_or_create_user(
        self, provider: str, sub: str, email: str, display_name: str, avatar_url: str | None = None
    ) -> tuple[User, str]:
        """Resolves an OAuth user, creating or linking as needed. Returns (User, tenant_id)."""
        clean_email = email.lower().strip()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Existing OAuth identity?
            cursor.execute(
                "SELECT u.* FROM oauth_identities oi JOIN users u ON oi.user_id = u.id WHERE oi.provider = ? AND oi.provider_sub = ?",
                (provider, str(sub)),
            )
            row = cursor.fetchone()
            if row:
                user = User(
                    id=row["id"],
                    email=row["email"],
                    display_name=row["display_name"],
                    avatar_url=row["avatar_url"],
                )
                return user, user.id

            # 2. Existing user by email?
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean_email,))
            row = cursor.fetchone()
            if row:
                user = User(
                    id=row["id"],
                    email=row["email"],
                    display_name=row["display_name"],
                    avatar_url=row["avatar_url"],
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO oauth_identities (provider, provider_sub, user_id, email) VALUES (?, ?, ?, ?)",
                    (provider, str(sub), user.id, clean_email),
                )
                conn.commit()
                return user, user.id

            # 3. Create new user
            user_id = hashlib.sha256(f"{clean_email}:{time.time()}".encode()).hexdigest()[:16]
            cursor.execute(
                "INSERT INTO users (id, email, display_name, avatar_url) VALUES (?, ?, ?, ?)",
                (user_id, clean_email, display_name, avatar_url),
            )
            cursor.execute(
                "INSERT INTO oauth_identities (provider, provider_sub, user_id, email) VALUES (?, ?, ?, ?)",
                (provider, str(sub), user_id, clean_email),
            )
            conn.commit()
            return User(
                id=user_id, email=clean_email, display_name=display_name, avatar_url=avatar_url
            ), user_id

    def authenticate_local_password(self, password: str) -> TenantContext | None:
        if not self.settings.has_password:
            return None
        if verify_password(password, self.settings.admin_password_hash):
            return TenantContext(
                tenant_id="default",
                user_id="admin",
                email="admin@paslood",
                role=TenantRole.OWNER,
            )
        return None
