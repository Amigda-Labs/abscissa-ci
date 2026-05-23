from __future__ import annotations

from math import ceil

from abscissa_ci.models import TileCountResult, TileSpec, clean_float


def count_needed_tiles(
    total_floor_area_sqm: float,
    tile_spec: TileSpec | None = None,
    waste_percent: float = 10,
) -> TileCountResult:
    if total_floor_area_sqm <= 0:
        raise ValueError("total_floor_area_sqm must be greater than zero")
    if waste_percent < 0:
        raise ValueError("waste_percent cannot be negative")

    spec = tile_spec or TileSpec()
    tile_area_sqm = spec.area_sqm
    base_tile_count = ceil(total_floor_area_sqm / tile_area_sqm)
    order_tile_count = ceil(base_tile_count * (1 + (waste_percent / 100)))

    return TileCountResult(
        tile_length_mm=spec.length_mm,
        tile_width_mm=spec.width_mm,
        tile_area_sqm=tile_area_sqm,
        base_tile_count=base_tile_count,
        order_tile_count=order_tile_count,
        waste_percent=clean_float(waste_percent),
        calculation=(
            f"ceil({total_floor_area_sqm:g} sqm / {tile_area_sqm:g} sqm), "
            f"then ceil(base_tiles * {1 + (waste_percent / 100):g})"
        ),
    )
