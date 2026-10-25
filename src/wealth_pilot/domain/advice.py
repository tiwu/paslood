"""Strategic Advice domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from wealth_pilot.domain.money import Money


class AdviceType(StrEnum):
    DEPOSIT_REBALANCE = "DEPOSIT_REBALANCE"
    DEBT_AVALANCHE = "DEBT_AVALANCHE"
    DEBT_SNOWBALL = "DEBT_SNOWBALL"
    BUFFER_BUILD = "BUFFER_BUILD"
    TAX_OPTIMIZATION = "TAX_OPTIMIZATION"
    PORTFOLIO_DRIFT = "PORTFOLIO_DRIFT"
    GENERAL = "GENERAL"


class Priority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass(frozen=True)
class AdviceItem:
    """A strategic financial recommendation."""

    title: str
    message: str
    priority: Priority = Priority.MEDIUM
    advice_type: AdviceType = AdviceType.GENERAL
    action_amount: Money | None = None


@dataclass(frozen=True)
class RebalanceAction:
    """An asset or bucket level rebalancing instruction."""

    bucket_id: str
    bucket_name: str
    action_type: str  # "BUY", "SELL", "HOLD"
    amount: Money
    target_weight_pct: Decimal
    current_weight_pct: Decimal
    reason: str = ""


@dataclass(frozen=True)
class ContributionAllocation:
    """Allocation of an incoming cash deposit across underweight buckets."""

    bucket_id: str
    bucket_name: str
    amount: Money
    percentage_of_deposit: Decimal


@dataclass(frozen=True)
class DebtPayoffRecommendation:
    """Recommendation on prioritizing debt payoff over investing."""

    liability_id: str
    liability_name: str
    interest_rate_pct: Decimal
    current_balance: Money
    recommended_extra_payment: Money
    strategy: str  # "Avalanche" or "Snowball"
    reason: str
