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


def infer_institution_from_account(account_id: str) -> str:
    """Infers banking institution name from an IBAN or masked card/account reference."""
    clean = account_id.replace(" ", "").upper()
    if "BUNQ" in clean or (clean.startswith("NL") and "BUNQ" in clean):
        return "bunq"
    if (
        clean.startswith("BE")
        or "KRED" in clean
        or "XXXX" in clean
        or clean.startswith("5489")
        or clean.startswith("5176")
    ):
        return "KBC"
    return "Unknown"
