from __future__ import annotations

from abscissa_ci.models import TileEstimateInput, TileEstimateResult
from abscissa_ci.calculators.area_computation import compute_room_areas, compute_total_area
from abscissa_ci.calculators.tile_counting import count_needed_tiles


DEFAULT_ASSUMPTIONS = [
    "All included floor areas are rectangular.",
    "Tile size is fixed at 600mm x 600mm for this checkpoint.",
    "Waste allowance is 10% for a simple straight tile layout placeholder.",
    "Generated results are draft-only and require human evaluation.",
]


def estimate_tiles(estimate_input: TileEstimateInput) -> TileEstimateResult:
    assumptions = [*DEFAULT_ASSUMPTIONS, *estimate_input.assumptions]
    warnings = [*estimate_input.warnings]

    if not estimate_input.rectangles:
        warnings.append("No valid rectangular dimensions were available, so tile count was not computed.")
        return TileEstimateResult(
            can_compute=False,
            project_name=estimate_input.project_name,
            input_source=estimate_input.input_source,
            source_image_path=estimate_input.source_image_path,
            extracted_rectangles=[],
            rooms=[],
            total_floor_area_sqm=None,
            tile_spec=estimate_input.tile_spec,
            tile_area_sqm=estimate_input.tile_spec.area_sqm,
            base_tile_count=None,
            order_tile_count=None,
            waste_percent=estimate_input.waste_percent,
            assumptions=assumptions,
            warnings=warnings,
        )

    rooms = compute_room_areas(estimate_input.rectangles)
    total_area = compute_total_area(rooms)
    if total_area <= 0:
        warnings.append("Net floor area must be greater than zero after subtractive rectangles.")
        return TileEstimateResult(
            can_compute=False,
            project_name=estimate_input.project_name,
            input_source=estimate_input.input_source,
            source_image_path=estimate_input.source_image_path,
            extracted_rectangles=estimate_input.rectangles,
            rooms=rooms,
            total_floor_area_sqm=total_area,
            tile_spec=estimate_input.tile_spec,
            tile_area_sqm=estimate_input.tile_spec.area_sqm,
            base_tile_count=None,
            order_tile_count=None,
            waste_percent=estimate_input.waste_percent,
            assumptions=assumptions,
            warnings=warnings,
        )

    tile_count = count_needed_tiles(total_area, estimate_input.tile_spec, estimate_input.waste_percent)

    for room in rooms:
        warnings.extend(room.warnings)

    return TileEstimateResult(
        can_compute=True,
        project_name=estimate_input.project_name,
        input_source=estimate_input.input_source,
        source_image_path=estimate_input.source_image_path,
        extracted_rectangles=estimate_input.rectangles,
        rooms=rooms,
        total_floor_area_sqm=total_area,
        tile_spec=estimate_input.tile_spec,
        tile_area_sqm=tile_count.tile_area_sqm,
        base_tile_count=tile_count.base_tile_count,
        order_tile_count=tile_count.order_tile_count,
        waste_percent=tile_count.waste_percent,
        assumptions=assumptions,
        warnings=warnings,
    )
