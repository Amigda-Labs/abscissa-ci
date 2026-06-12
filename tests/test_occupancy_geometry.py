from abscissa_ci.calculators.occupancy_geometry import (
    attach_inventory_labels,
    grid_to_polygons,
)
from abscissa_ci.calculators.polygon_geometry import (
    compute_polygon_area,
    compute_polygon_areas,
    compute_total_polygon_area,
    validate_polygon_set,
)


def test_single_cell_grid_traces_a_rectangle():
    polygons, errors = grid_to_polygons([0, 10], [0, 4], [[True]])

    assert errors == []
    assert len(polygons) == 1
    assert polygons[0].operation == "add"
    assert compute_polygon_area(polygons[0]).area_sqm == 40


def test_l_shape_grid_merges_straight_runs():
    # Stations x {0, 7, 12}, y {0, 5, 9}; top row only covers the left column.
    occupied_rows = [
        [True, False],
        [True, True],
    ]
    polygons, errors = grid_to_polygons([0, 7, 12], [0, 5, 9], occupied_rows)

    assert errors == []
    assert len(polygons) == 1
    result = compute_polygon_area(polygons[0])
    assert result.area_sqm == 88
    # The bottom edge spans both columns but must be one merged 12m edge.
    assert len(polygons[0].points) == 6


def test_offset_cross_grid_reproduces_the_cross():
    # Stations x {0, 5, 9, 16}, y {0, 4, 8.5, 13}.
    occupied_rows = [
        [False, True, False],
        [True, True, True],
        [False, True, False],
    ]
    polygons, errors = grid_to_polygons([0, 5, 9, 16], [0, 4, 8.5, 13], occupied_rows)

    assert errors == []
    assert len(polygons) == 1
    result = compute_polygon_area(polygons[0])
    assert result.area_sqm == 106
    assert len(polygons[0].points) == 12


def test_interior_hole_becomes_a_subtract_polygon():
    # 3x3 grid fully occupied except the center cell.
    occupied_rows = [
        [True, True, True],
        [True, False, True],
        [True, True, True],
    ]
    polygons, errors = grid_to_polygons([0, 4, 8, 12], [0, 3, 6, 9], occupied_rows)

    assert errors == []
    operations = sorted(polygon.operation for polygon in polygons)
    assert operations == ["add", "subtract"]
    assert validate_polygon_set(polygons) == []
    assert compute_total_polygon_area(compute_polygon_areas(polygons)) == 96


def test_grid_shape_mismatch_is_an_error():
    polygons, errors = grid_to_polygons([0, 5, 9, 16], [0, 4, 8.5, 13], [[True, True]])

    assert polygons == []
    assert "3 rows x 3 columns" in errors[0]


def test_empty_grid_is_an_error():
    polygons, errors = grid_to_polygons([0, 10], [0, 4], [[False]])

    assert polygons == []
    assert "no occupied cells" in errors[0]


def test_attach_inventory_labels_matches_edges_by_length():
    occupied_rows = [
        [True, False],
        [True, True],
    ]
    polygons, errors = grid_to_polygons([0, 7, 12], [0, 5, 9], occupied_rows)
    assert errors == []

    attach_inventory_labels(polygons, ["12.00 m", "9.00 m", "5.00 m", "99.00 m"])

    labels = polygons[0].edge_labels
    attached = {label.source_text for label in labels}
    assert "12.00 m" in attached
    assert "9.00 m" in attached
    assert "5.00 m" in attached
    # No 99m edge exists, so that label stays unattached for coverage to flag.
    assert "99.00 m" not in attached


def test_occupancy_consistency_mismatch_is_flagged():
    from abscissa_ci.agents.tile_agent import occupancy_consistency_errors
    from abscissa_ci.models import OccupancyExtraction, OccupiedCell

    extraction = OccupancyExtraction(
        occupied_cells=[OccupiedCell(row=1, col=2)],
        occupied_rows=[
            [True, False, True],
            [True, True, True],
            [False, True, False],
        ],
    )

    errors = occupancy_consistency_errors(extraction, rows=3, columns=3)

    assert any("(row 1, col 2) is in occupied_cells" in error for error in errors)
    assert any("(row 1, col 1) is true in occupied_rows" in error for error in errors)


def test_occupancy_consistency_agreement_passes():
    from abscissa_ci.agents.tile_agent import occupancy_consistency_errors
    from abscissa_ci.models import OccupancyExtraction, OccupiedCell

    extraction = OccupancyExtraction(
        occupied_cells=[
            OccupiedCell(row=1, col=2),
            OccupiedCell(row=2, col=1),
            OccupiedCell(row=2, col=2),
            OccupiedCell(row=2, col=3),
            OccupiedCell(row=3, col=2),
        ],
        occupied_rows=[
            [False, True, False],
            [True, True, True],
            [False, True, False],
        ],
    )

    assert occupancy_consistency_errors(extraction, rows=3, columns=3) == []


def test_occupancy_cell_out_of_grid_is_flagged():
    from abscissa_ci.agents.tile_agent import occupancy_consistency_errors
    from abscissa_ci.models import OccupancyExtraction, OccupiedCell

    extraction = OccupancyExtraction(
        occupied_cells=[OccupiedCell(row=4, col=1)],
        occupied_rows=[[True]],
    )

    errors = occupancy_consistency_errors(extraction, rows=1, columns=1)

    assert any("outside the 1x1 station grid" in error for error in errors)


def test_partially_covered_cell_blocks_the_draft():
    from abscissa_ci.agents.tile_agent import validate_occupancy_extraction
    from abscissa_ci.models import DimensionSurvey, OccupancyExtraction, OccupiedCell

    extraction = OccupancyExtraction(
        occupied_cells=[OccupiedCell(row=1, col=1)],
        occupied_rows=[[True]],
        partially_covered_cells=[OccupiedCell(row=1, col=1)],
    )

    polygons, errors = validate_occupancy_extraction(
        extraction, [], [0, 10], [0, 4], DimensionSurvey()
    )

    assert polygons == []
    assert any("partially" in error for error in errors)
