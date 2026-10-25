"""Domain entities for multi-tenant accounts, users, and identity contexts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TenantRole(StrEnum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


@dataclass(frozen=True)
class User:
    id: str
    email: str
    display_name: str
    avatar_url: str | None = None


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str
    email: str
    role: TenantRole = TenantRole.OWNER
