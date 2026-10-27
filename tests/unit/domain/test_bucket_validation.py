"""Unit tests for strategic allocation bucket target validation."""

from decimal import Decimal

import pytest

from paslood.domain.bucket import (
    Bucket,
    calculate_active_bucket_weight_sum,
    validate_bucket_weights,
)


def test_validate_bucket_weights_balanced():
    """Verify that buckets summing to exactly 100.0% pass validation."""
    buckets = [
        Bucket(id="b1", name="Core ETFs", target_weight_pct=Decimal("50.0")),
        Bucket(id="b2", name="Tech", target_weight_pct=Decimal("30.0")),
        Bucket(id="b3", name="Cash", target_weight_pct=Decimal("20.0")),
    ]
    validate_bucket_weights(buckets)
    assert calculate_active_bucket_weight_sum(buckets) == Decimal("100.0")


def test_validate_bucket_weights_overweight():
    """Verify that buckets summing to >100.0% raise ValueError."""
    buckets = [
        Bucket(id="b1", name="Core ETFs", target_weight_pct=Decimal("60.0")),
        Bucket(id="b2", name="Tech", target_weight_pct=Decimal("30.0")),
        Bucket(id="b3", name="Cash", target_weight_pct=Decimal("20.0")),
    ]
    with pytest.raises(ValueError, match="Active bucket target weights must sum to 100%"):
        validate_bucket_weights(buckets)


def test_validate_bucket_weights_underweight():
    """Verify that buckets summing to <100.0% raise ValueError."""
    buckets = [
        Bucket(id="b1", name="Core ETFs", target_weight_pct=Decimal("40.0")),
        Bucket(id="b2", name="Tech", target_weight_pct=Decimal("30.0")),
        Bucket(id="b3", name="Cash", target_weight_pct=Decimal("20.0")),
    ]
    with pytest.raises(ValueError, match="Active bucket target weights must sum to 100%"):
        validate_bucket_weights(buckets)


def test_validate_bucket_weights_ignores_excluded():
    """Verify that buckets excluded from rebalancing are ignored in sum calculation."""
    buckets = [
        Bucket(id="b1", name="Core ETFs", target_weight_pct=Decimal("60.0")),
        Bucket(id="b2", name="Cash", target_weight_pct=Decimal("40.0")),
        Bucket(
            id="b3",
            name="Real Estate",
            target_weight_pct=Decimal("25.0"),
            include_in_rebalancing=False,
        ),
    ]
    validate_bucket_weights(buckets)
    assert calculate_active_bucket_weight_sum(buckets) == Decimal("100.0")


def test_validate_bucket_weights_empty():
    """Verify that an empty bucket list does not raise."""
    validate_bucket_weights([])
    assert calculate_active_bucket_weight_sum([]) == Decimal("0.0")
