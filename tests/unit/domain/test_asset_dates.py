"""Unit tests for Asset acquisition and date properties."""

from paslood.domain.asset import Asset, AssetClass
from paslood.domain.money import Money


def test_asset_acquisition_date():
    asset = Asset(
        id="prop-1",
        name="Leuven House",
        asset_class=AssetClass.REAL_ESTATE,
        current_value=Money.from_val(450000.0),
        cost_basis=Money.from_val(320000.0),
        acquisition_date="2018-06-15",
    )
    assert asset.acquisition_date == "2018-06-15"
    assert asset.start_date == "2018-06-15"


def test_asset_start_date_none_by_default():
    asset = Asset(
        id="stock-1",
        name="VWCE",
        current_value=Money.from_val(5000.0),
    )
    assert asset.acquisition_date is None
    assert asset.start_date is None
