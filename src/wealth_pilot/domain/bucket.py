"""Bucket, AllocationRule, and Drift domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wealth_pilot.domain.asset import Asset, AssetClass


class DriftStatus(str, Enum):
    BALANCED = "BALANCED"
    OVERWEIGHT = "OVERWEIGHT"
    UNDERWEIGHT = "UNDERWEIGHT"


@dataclass(frozen=True)
class AllocationRule:
    """Rule for mapping assets into an allocation bucket."""

    symbols: set[str] = field(default_factory=set)
    isins: set[str] = field(default_factory=set)
    asset_classes: set[AssetClass] = field(default_factory=set)
    institutions: set[str] = field(default_factory=set)
    name_keywords: set[str] = field(default_factory=set)

    def matches(self, asset: Asset) -> bool:
        """Evaluate whether an asset satisfies this rule."""
        if self.symbols and asset.symbol.upper() in {s.upper() for s in self.symbols}:
            return True
        if self.isins and asset.isin and asset.isin.upper() in {i.upper() for i in self.isins}:
            return True
        if self.asset_classes and asset.asset_class in self.asset_classes:
            return True
        if self.institutions and asset.institution.upper() in {
            inst.upper() for inst in self.institutions
        }:
            return True
        if self.name_keywords:
            upper_name = asset.name.upper()
            if any(k.upper() in upper_name for k in self.name_keywords):
                return True
        return False


@dataclass
class Bucket:
    """An asset allocation pillar or financial goal category."""

    id: str
    name: str
    target_weight_pct: Decimal = Decimal("0.0")
    drift_tolerance_pct: Decimal = Decimal("3.0")
    rules: list[AllocationRule] = field(default_factory=list)
    description: str = ""
    color: str = "#3B82F6"  # Hex color for UI charts
    include_in_rebalancing: bool = True
    include_in_net_worth: bool = True

    @property
    def target_weight(self) -> Decimal:
        """Target weight as a fraction (0.0 - 1.0)."""
        return self.target_weight_pct / Decimal("100.0")

    def matches(self, asset: Asset) -> bool:
        """Check if an asset belongs in this bucket according to rules."""
        if not self.rules:
            return False
        return any(rule.matches(asset) for rule in self.rules)


@dataclass(frozen=True)
class BucketAllocationResult:
    """Evaluated current vs target state for a specific bucket."""

    bucket_id: str
    name: str
    current_value: Decimal
    current_weight_pct: Decimal
    target_weight_pct: Decimal
    target_value: Decimal
    diff_value: Decimal  # current_value - target_value (+: excess/sell, -: deficit/buy)
    diff_weight_pct: Decimal  # current_weight_pct - target_weight_pct
    drift_status: DriftStatus
    drift_tolerance_pct: Decimal
    color: str = "#3B82F6"
    include_in_rebalancing: bool = True
    include_in_net_worth: bool = True
