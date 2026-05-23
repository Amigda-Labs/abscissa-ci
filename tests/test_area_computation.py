import pytest
from pydantic import ValidationError

from abscissa_ci.models import RectangleDraft
from abscissa_ci.calculators.area_computation import (
    compute_rectangle_area,
    compute_room_areas,
    compute_total_area,
)


def test_compute_rectangle_area():
    room = RectangleDraft(name="Living Area", length_m=3, width_m=4)

    result = compute_rectangle_area(room)

    assert result.area_sqm == 12
    assert result.signed_area_sqm == 12
    assert result.calculation == "add (3m * 4m)"


def test_compute_total_area_from_multiple_rectangles():
    rooms = [
        RectangleDraft(name="Room A", length_m=3, width_m=4),
        RectangleDraft(name="Room B", length_m=2.5, width_m=2),
    ]

    room_areas = compute_room_areas(rooms)

    assert compute_total_area(room_areas) == 17


def test_compute_total_area_with_subtractive_void():
    rooms = [
        RectangleDraft(name="Outer", length_m=16, width_m=10),
        RectangleDraft(name="Void", length_m=5, width_m=3, operation="subtract"),
    ]

    room_areas = compute_room_areas(rooms)

    assert compute_total_area(room_areas) == 145


@pytest.mark.parametrize(
    "length_m,width_m",
    [(0, 4), (-1, 4), (4, 0), (4, -1)],
)
def test_reject_invalid_dimensions(length_m, width_m):
    with pytest.raises(ValidationError):
        RectangleDraft(name="Invalid", length_m=length_m, width_m=width_m)
