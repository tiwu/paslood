"""Backward-compatible authentication exports for Paslood web delivery."""

from __future__ import annotations

from paslood.adapters.security.auth_manager import (
    AuthManager,
    hash_password,
    verify_password,
)

__all__ = ["AuthManager", "hash_password", "verify_password"]
