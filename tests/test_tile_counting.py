import pytest

from abscissa_ci.models import TileSpec
from abscissa_ci.calculators.tile_counting import count_needed_tiles


def test_count_needed_tiles_for_600_by_600_tile():
    result = count_needed_tiles(12, TileSpec(length_mm=600, width_mm=600), waste_percent=10)

    assert result.tile_area_sqm == 0.36
    assert result.base_tile_count == 34
    assert result.order_tile_count == 38


def test_count_needed_tiles_for_known_rectangular_plan_area():
    result = count_needed_tiles(112, waste_percent=10)

    assert result.base_tile_count == 312
    assert result.order_tile_count == 344


def test_reject_non_positive_total_area():
    with pytest.raises(ValueError):
        count_needed_tiles(0)


def test_reject_negative_waste_percent():
    with pytest.raises(ValueError):
        count_needed_tiles(10, waste_percent=-5)
