from __future__ import annotations

from abscissa_ci.models import TileEstimateInput, TileEstimateResult, clean_float
from abscissa_ci.calculators.area_computation import compute_room_areas, compute_total_area
from abscissa_ci.calculators.polygon_geometry import (
    compute_polygon_areas,
    compute_total_polygon_area,
    validate_dimension_coverage,
    validate_polygon_set,
)
from abscissa_ci.calculators.tile_counting import count_needed_tiles


DEFAULT_ASSUMPTIONS = [
    "Included floor areas are axis-aligned rectangles or simple rectilinear polygons.",
    "Tile size is fixed at 600mm x 600mm for this checkpoint.",
    "Waste allowance is 10% for a simple straight tile layout placeholder.",
    "Generated results are draft-only and require human evaluation.",
]


def estimate_tiles(estimate_input: TileEstimateInput) -> TileEstimateResult:
    assumptions = [*DEFAULT_ASSUMPTIONS, *estimate_input.assumptions]
    warnings = [*estimate_input.warnings]

    # Extraction-time validation errors (traverse misclosures, station
    # misalignment) cannot be re-derived from the shapes alone, so they carry
    # over explicitly and gate computation.
    extraction_errors = [*estimate_input.validation_errors]
    warnings.extend(extraction_errors)

    rooms = compute_room_areas(estimate_input.rectangles)
    polygon_zones = compute_polygon_areas(estimate_input.polygons)

    base_fields = dict(
        project_name=estimate_input.project_name,
        input_source=estimate_input.input_source,
        source_image_path=estimate_input.source_image_path,
        extracted_rectangles=estimate_input.rectangles,
        extracted_polygons=estimate_input.polygons,
        rooms=rooms,
        polygons=polygon_zones,
        tile_spec=estimate_input.tile_spec,
        tile_area_sqm=estimate_input.tile_spec.area_sqm,
        waste_percent=estimate_input.waste_percent,
        assumptions=assumptions,
        warnings=warnings,
    )

    if not estimate_input.rectangles and not estimate_input.polygons:
        warnings.append(
            "No valid rectangle or polygon dimensions were available, so tile count was not computed."
        )
        return TileEstimateResult(
            can_compute=False,
            total_floor_area_sqm=None,
            base_tile_count=None,
            order_tile_count=None,
            **base_fields,
        )

    for zone in polygon_zones:
        warnings.extend(zone.errors)
        warnings.extend(zone.warnings)

    valid_polygon_drafts = [
        draft
        for draft, zone in zip(estimate_input.polygons, polygon_zones)
        if zone.is_valid
    ]
    cross_polygon_errors = validate_polygon_set(valid_polygon_drafts)
    cross_polygon_errors.extend(
        validate_dimension_coverage(estimate_input.dimension_inventory, valid_polygon_drafts)
    )
    warnings.extend(cross_polygon_errors)

    if (
        any(not zone.is_valid for zone in polygon_zones)
        or cross_polygon_errors
        or extraction_errors
    ):
        warnings.append("Polygon validation failed, so tile count was not computed.")
        return TileEstimateResult(
            can_compute=False,
            total_floor_area_sqm=None,
            base_tile_count=None,
            order_tile_count=None,
            **base_fields,
        )

    total_area = clean_float(
        compute_total_area(rooms) + compute_total_polygon_area(polygon_zones)
    )
    if total_area <= 0:
        warnings.append("Net floor area must be greater than zero after subtractive areas.")
        return TileEstimateResult(
            can_compute=False,
            total_floor_area_sqm=total_area,
            base_tile_count=None,
            order_tile_count=None,
            **base_fields,
        )

    tile_count = count_needed_tiles(total_area, estimate_input.tile_spec, estimate_input.waste_percent)

    for room in rooms:
        warnings.extend(room.warnings)

    base_fields["tile_area_sqm"] = tile_count.tile_area_sqm
    base_fields["waste_percent"] = tile_count.waste_percent
    return TileEstimateResult(
        can_compute=True,
        total_floor_area_sqm=total_area,
        base_tile_count=tile_count.base_tile_count,
        order_tile_count=tile_count.order_tile_count,
        **base_fields,
    )
