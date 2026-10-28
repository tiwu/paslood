"""Domain model for user-configured known accounts and external destinations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountType(StrEnum):
    INVESTMENT = "INVESTMENT"
    SAVINGS = "SAVINGS"
    CHECKING = "CHECKING"
    CREDIT_CARD = "CREDIT_CARD"
    OTHER = "OTHER"


@dataclass(frozen=True)
class KnownAccount:
    """A known account belonging to the user or an external destination (e.g. Saxo, Bunq Savings)."""

    id: str
    account_number: str
    label: str
    account_type: str = AccountType.CHECKING.value
    institution: str = ""
