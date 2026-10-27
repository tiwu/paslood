"""Application configuration and environment settings for Paslood."""

from __future__ import annotations

import contextlib
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppSettings:
    mode: str = "local"  # "local", "self_host", "saas"
    data_dir: Path = field(default_factory=lambda: Path.home() / ".paslood")
    secret_key: str = ""
    auth_mode: str = "none"  # "none", "password", "hybrid", "oauth"
    allowed_emails: set[str] = field(default_factory=set)
    trusted_origins: set[str] = field(default_factory=set)
    admin_password_hash: str = ""

    # OAuth Providers
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    meta_client_id: str = ""
    meta_client_secret: str = ""

    def __post_init__(self) -> None:
        if not self.secret_key:
            secret_file = self.data_dir / ".secret_key"
            if secret_file.exists():
                with contextlib.suppress(Exception):
                    self.secret_key = secret_file.read_text(encoding="utf-8").strip()
            if not self.secret_key:
                self.secret_key = secrets.token_hex(32)
                if self.mode != "saas":
                    with contextlib.suppress(Exception):
                        self.data_dir.mkdir(parents=True, exist_ok=True)
                        secret_file.write_text(self.secret_key, encoding="utf-8")
                        if os.name != "nt":
                            secret_file.chmod(0o600)

    @property
    def has_google_oauth(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def has_github_oauth(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def has_meta_oauth(self) -> bool:
        return bool(self.meta_client_id and self.meta_client_secret)

    @property
    def has_oauth(self) -> bool:
        return self.has_google_oauth or self.has_github_oauth or self.has_meta_oauth

    @property
    def has_password(self) -> bool:
        return bool(self.admin_password_hash)

    def is_email_allowed(self, email: str) -> bool:
        if not self.allowed_emails:
            return True
        return email.lower().strip() in {e.lower().strip() for e in self.allowed_emails}

    @classmethod
    def from_env(cls) -> AppSettings:
        raw_data_dir = os.getenv("PASLOOD_DATA_DIR")
        data_dir = (
            Path(raw_data_dir).expanduser().resolve() if raw_data_dir else Path.home() / ".paslood"
        )

        raw_allowed = os.getenv("PASLOOD_ALLOWED_EMAILS") or ""
        allowed_emails = {e.strip() for e in raw_allowed.split(",") if e.strip()}

        raw_origins = os.getenv("PASLOOD_TRUSTED_ORIGINS") or ""
        trusted_origins = {o.strip() for o in raw_origins.split(",") if o.strip()}

        return cls(
            mode=(os.getenv("PASLOOD_MODE") or "local").lower(),
            data_dir=data_dir,
            secret_key=os.getenv("PASLOOD_SECRET_KEY") or "",
            auth_mode=(os.getenv("PASLOOD_AUTH_MODE") or "none").lower(),
            allowed_emails=allowed_emails,
            trusted_origins=trusted_origins,
            admin_password_hash=os.getenv("PASLOOD_ADMIN_PASSWORD_HASH") or "",
            google_client_id=(
                os.getenv("PASLOOD_GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID") or ""
            ),
            google_client_secret=(
                os.getenv("PASLOOD_GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or ""
            ),
            github_client_id=(
                os.getenv("PASLOOD_GITHUB_CLIENT_ID") or os.getenv("GITHUB_CLIENT_ID") or ""
            ),
            github_client_secret=(
                os.getenv("PASLOOD_GITHUB_CLIENT_SECRET") or os.getenv("GITHUB_CLIENT_SECRET") or ""
            ),
            meta_client_id=(
                os.getenv("PASLOOD_META_CLIENT_ID") or os.getenv("META_CLIENT_ID") or ""
            ),
            meta_client_secret=(
                os.getenv("PASLOOD_META_CLIENT_SECRET") or os.getenv("META_CLIENT_SECRET") or ""
            ),
        )
