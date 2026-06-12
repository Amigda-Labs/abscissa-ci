import pytest
from pydantic import ValidationError

from abscissa_ci.models import PolygonTraverse, TraverseMove
from abscissa_ci.calculators.polygon_geometry import compute_polygon_area
from abscissa_ci.calculators.traverse_geometry import (
    traverse_closure_errors,
    traverse_derivation_notes,
    traverse_to_polygon,
)


def make_traverse(moves, **kwargs):
    return PolygonTraverse(
        moves=[
            TraverseMove(direction=direction, length_m=length, **extra)
            for direction, length, extra in moves
        ],
        **kwargs,
    )


L_SHAPE_MOVES = [
    ("E", 12, {"source_text": "12.00 m"}),
    ("N", 5, {"source_text": "5.00 m"}),
    ("W", 5, {"source_text": "5.00 m"}),
    ("N", 4, {"source_text": "4.00 m"}),
    ("W", 7, {"source_text": "7.00 m"}),
    ("S", 9, {"source_text": "9.00 m"}),
]


def test_l_shape_traverse_converts_to_polygon():
    polygon, errors = traverse_to_polygon(make_traverse(L_SHAPE_MOVES, name="L Shape"))

    assert errors == []
    assert [(p.x_m, p.y_m) for p in polygon.points] == [
        (0, 0),
        (12, 0),
        (12, 5),
        (7, 5),
        (7, 9),
        (0, 9),
    ]
    assert len(polygon.edge_labels) == 6
    assert polygon.edge_labels[0].edge_index == 0
    assert polygon.edge_labels[0].source_text == "12.00 m"

    result = compute_polygon_area(polygon)
    assert result.is_valid is True
    assert result.area_sqm == 88


def test_traverse_starting_away_from_origin_normalizes_to_nonnegative():
    # Walking W and S first sends raw coordinates negative; the converter
    # shifts the ring so the bottom-left of the footprint lands at (0, 0).
    polygon, errors = traverse_to_polygon(
        make_traverse([("W", 4, {}), ("S", 3, {}), ("E", 4, {}), ("N", 3, {})])
    )

    assert errors == []
    assert all(p.x_m >= 0 and p.y_m >= 0 for p in polygon.points)
    assert compute_polygon_area(polygon).area_sqm == 12


def test_east_west_misclosure_reports_both_totals():
    polygon, errors = traverse_to_polygon(
        make_traverse(
            [
                ("E", 12, {}),
                ("N", 5, {}),
                ("W", 5, {}),
                ("N", 4, {}),
                ("W", 3, {}),
                ("S", 9, {}),
            ],
            name="Open Shape",
        )
    )

    assert polygon is None
    assert len(errors) == 1
    assert "east moves total 12m" in errors[0]
    assert "west moves total 8m" in errors[0]
    assert "+4m" in errors[0]


def test_north_south_misclosure_reports_both_totals():
    errors = traverse_closure_errors(
        make_traverse(
            [("E", 10, {}), ("N", 5, {}), ("W", 10, {}), ("S", 4, {})],
            name="Open Shape",
        )
    )

    assert len(errors) == 1
    assert "north moves total 5m" in errors[0]
    assert "south moves total 4m" in errors[0]


def test_derived_move_gets_no_edge_label_but_a_note():
    moves = [
        ("E", 12, {"source_text": "12.00 m"}),
        ("N", 5, {"source_text": "5.00 m"}),
        ("W", 5, {"derivation": "12.00 - 7.00"}),
        ("N", 4, {"source_text": "4.00 m"}),
        ("W", 7, {"source_text": "7.00 m"}),
        ("S", 9, {"source_text": "9.00 m"}),
    ]
    traverse = make_traverse(moves, name="L Shape")
    polygon, errors = traverse_to_polygon(traverse)

    assert errors == []
    assert [label.edge_index for label in polygon.edge_labels] == [0, 1, 3, 4, 5]

    notes = traverse_derivation_notes(traverse)
    assert len(notes) == 1
    assert "west 5m" in notes[0]
    assert "12.00 - 7.00" in notes[0]


def test_chained_same_direction_moves_keep_separate_labeled_edges():
    # A straight run dimensioned as a chain (5.00 + 4.00) stays two edges so
    # each printed label attaches to its own edge.
    polygon, errors = traverse_to_polygon(
        make_traverse(
            [
                ("E", 5, {"source_text": "5.00 m"}),
                ("E", 4, {"source_text": "4.00 m"}),
                ("N", 3, {}),
                ("W", 9, {}),
                ("S", 3, {}),
            ]
        )
    )

    assert errors == []
    assert len(polygon.points) == 5
    assert [label.edge_index for label in polygon.edge_labels] == [0, 1]

    result = compute_polygon_area(polygon)
    assert result.is_valid is True
    assert result.area_sqm == 27


def test_bounding_dimensions_carry_over_and_validate():
    polygon, errors = traverse_to_polygon(
        make_traverse(L_SHAPE_MOVES, bounding_width_m=12, bounding_height_m=9)
    )

    assert errors == []
    assert polygon.bounding_width_m == 12
    assert polygon.bounding_height_m == 9
    assert compute_polygon_area(polygon).is_valid is True


def test_traverse_requires_at_least_four_moves():
    with pytest.raises(ValidationError):
        make_traverse([("E", 4, {}), ("N", 3, {}), ("W", 4, {})])


def test_zero_length_move_is_rejected():
    with pytest.raises(ValidationError):
        make_traverse([("E", 4, {}), ("N", 0, {}), ("W", 4, {}), ("S", 3, {})])


def test_validate_traverse_extraction_flags_uncovered_inventory():
    from abscissa_ci.agents.tile_agent import validate_traverse_extraction
    from abscissa_ci.models import TraverseExtraction

    extraction = TraverseExtraction(
        traverses=[
            make_traverse(
                [
                    ("E", 10, {"source_text": "10.00 m"}),
                    ("N", 4, {"source_text": "4.00 m"}),
                    ("W", 10, {}),
                    ("S", 4, {}),
                ],
                name="Main Floor",
            )
        ]
    )

    polygons, errors = validate_traverse_extraction(
        extraction, ["10.00 m", "4.00 m", "3.00 m"]
    )

    assert len(polygons) == 1
    assert len(errors) == 1
    assert "'3.00 m'" in errors[0]


def test_validate_traverse_extraction_passes_clean_traverse():
    from abscissa_ci.agents.tile_agent import validate_traverse_extraction
    from abscissa_ci.models import TraverseExtraction

    extraction = TraverseExtraction(
        traverses=[
            make_traverse(
                [
                    ("E", 10, {"source_text": "10.00 m"}),
                    ("N", 4, {"source_text": "4.00 m"}),
                    ("W", 10, {}),
                    ("S", 4, {}),
                ],
                name="Main Floor",
                bounding_width_m=10,
                bounding_height_m=4,
            )
        ]
    )

    polygons, errors = validate_traverse_extraction(extraction, ["10.00 m", "4.00 m"])

    assert errors == []
    assert len(polygons) == 1
    assert compute_polygon_area(polygons[0]).area_sqm == 40
