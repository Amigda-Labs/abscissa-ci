import pytest
from pydantic import ValidationError

from abscissa_ci.models import EdgeDimensionLabel, PolygonDraft, PolygonPoint
from abscissa_ci.calculators.polygon_geometry import (
    compute_polygon_area,
    compute_polygon_areas,
    compute_total_polygon_area,
    shoelace_area,
    validate_dimension_coverage,
    validate_polygon_set,
)


def make_polygon(coords, **kwargs):
    return PolygonDraft(points=[PolygonPoint(x_m=x, y_m=y) for x, y in coords], **kwargs)


L_SHAPE = [(0, 0), (12, 0), (12, 5), (7, 5), (7, 9), (0, 9)]


def test_shoelace_signed_area_orientation():
    counter_clockwise = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
    assert shoelace_area(counter_clockwise) == 12
    assert shoelace_area(list(reversed(counter_clockwise))) == -12


def test_l_shape_area_and_perimeter():
    result = compute_polygon_area(make_polygon(L_SHAPE, name="L Shape"))

    assert result.is_valid is True
    assert result.area_sqm == 88
    assert result.signed_area_sqm == 88
    assert result.perimeter_m == 42


def test_clockwise_ring_gives_same_positive_area():
    result = compute_polygon_area(make_polygon(list(reversed(L_SHAPE))))

    assert result.is_valid is True
    assert result.area_sqm == 88


def test_subtract_polygon_has_negative_signed_area():
    result = compute_polygon_area(
        make_polygon([(2, 2), (7, 2), (7, 5), (2, 5)], operation="subtract")
    )

    assert result.signed_area_sqm == -15


def test_closed_ring_with_repeated_first_point_is_normalized():
    polygon = make_polygon([(0, 0), (4, 0), (4, 3), (0, 3), (0, 0)])

    assert len(polygon.points) == 4
    assert compute_polygon_area(polygon).area_sqm == 12


def test_too_few_distinct_points_is_rejected():
    with pytest.raises(ValidationError):
        make_polygon([(0, 0), (4, 0), (0, 0)])


def test_matching_edge_labels_pass_validation():
    polygon = make_polygon(
        L_SHAPE,
        edge_labels=[
            EdgeDimensionLabel(edge_index=0, length_m=12, source_text="12.00 m"),
            EdgeDimensionLabel(edge_index=4, length_m=7, source_text="7.00 m"),
            EdgeDimensionLabel(edge_index=5, length_m=9, source_text="9.00 m"),
        ],
    )

    result = compute_polygon_area(polygon)

    assert result.is_valid is True
    assert result.errors == []


def test_mismatched_edge_label_blocks_computation():
    polygon = make_polygon(
        L_SHAPE,
        name="L Shape",
        edge_labels=[EdgeDimensionLabel(edge_index=0, length_m=11, source_text="11.00 m")],
    )

    result = compute_polygon_area(polygon)

    assert result.is_valid is False
    assert result.area_sqm is None
    assert "measures 12m" in result.errors[0]
    assert "labeled 11m" in result.errors[0]


def test_out_of_range_edge_label_blocks_computation():
    polygon = make_polygon(L_SHAPE, edge_labels=[EdgeDimensionLabel(edge_index=6, length_m=3)])

    result = compute_polygon_area(polygon)

    assert result.is_valid is False
    assert "out of range" in result.errors[0]


def test_self_intersecting_ring_blocks_computation():
    bowtie = make_polygon([(0, 0), (4, 4), (4, 0), (0, 4)])

    result = compute_polygon_area(bowtie)

    assert result.is_valid is False
    assert "intersects itself" in result.errors[0]


def test_collinear_points_block_computation():
    flat = make_polygon([(0, 0), (2, 0), (4, 0)])

    result = compute_polygon_area(flat)

    assert result.is_valid is False


def test_non_axis_aligned_edge_warns_but_computes():
    triangle = make_polygon([(0, 0), (4, 0), (0, 3)])

    result = compute_polygon_area(triangle)

    assert result.is_valid is True
    assert result.area_sqm == 6
    assert any("not axis-aligned" in warning for warning in result.warnings)


def test_matching_bounding_dimensions_pass_validation():
    polygon = make_polygon(L_SHAPE, bounding_width_m=12, bounding_height_m=9)

    result = compute_polygon_area(polygon)

    assert result.is_valid is True
    assert result.area_sqm == 88


def test_mismatched_bounding_width_blocks_computation():
    polygon = make_polygon(L_SHAPE, name="L Shape", bounding_width_m=16, bounding_height_m=9)

    result = compute_polygon_area(polygon)

    assert result.is_valid is False
    assert any("span 12m wide" in error and "labeled 16m" in error for error in result.errors)


def test_mismatched_bounding_height_blocks_computation():
    polygon = make_polygon(L_SHAPE, name="L Shape", bounding_height_m=13)

    result = compute_polygon_area(polygon)

    assert result.is_valid is False
    assert any("span 9m tall" in error and "labeled 13m" in error for error in result.errors)


def test_void_inside_floor_polygon_passes_set_validation():
    floor = make_polygon([(0, 0), (16, 0), (16, 10), (0, 10)], name="Outer")
    void = make_polygon([(5, 3), (10, 3), (10, 6), (5, 6)], name="Void", operation="subtract")

    assert validate_polygon_set([floor, void]) == []
    assert compute_total_polygon_area(compute_polygon_areas([floor, void])) == 145


def test_void_outside_floor_polygon_fails_set_validation():
    floor = make_polygon([(0, 0), (16, 0), (16, 10), (0, 10)], name="Outer")
    stray_void = make_polygon(
        [(20, 20), (22, 20), (22, 22), (20, 22)], name="Stray", operation="subtract"
    )

    errors = validate_polygon_set([floor, stray_void])

    assert len(errors) == 1
    assert "not contained" in errors[0]


def test_overlapping_floor_polygons_fail_set_validation():
    first = make_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], name="First")
    second = make_polygon([(5, 5), (15, 5), (15, 15), (5, 15)], name="Second")

    errors = validate_polygon_set([first, second])

    assert len(errors) == 1
    assert "double-counted" in errors[0]


def test_identical_floor_polygons_fail_set_validation():
    coords = [(0, 0), (10, 0), (10, 10), (0, 10)]

    errors = validate_polygon_set([make_polygon(coords, name="A"), make_polygon(coords, name="B")])

    assert len(errors) == 1


def test_dimension_coverage_passes_when_all_labels_are_used():
    polygon = make_polygon(
        L_SHAPE,
        bounding_width_m=12,
        bounding_height_m=9,
        edge_labels=[
            EdgeDimensionLabel(edge_index=1, length_m=5, source_text="5.00 m"),
            EdgeDimensionLabel(edge_index=2, length_m=5, source_text="5.00 m"),
            EdgeDimensionLabel(edge_index=3, length_m=4, source_text="4.00 m"),
            EdgeDimensionLabel(edge_index=4, length_m=7, source_text="7.00 m"),
        ],
    )
    inventory = ["12.00 m", "9.00 m", "5.00 m", "5.00 m", "4.00 m", "7.00 m"]

    assert validate_dimension_coverage(inventory, [polygon]) == []


def test_dimension_coverage_flags_unassigned_printed_label():
    # A simplified wrong shape that has no edge for the printed "8.00 m".
    polygon = make_polygon(
        [(0, 0), (18, 0), (18, 12), (0, 12)],
        bounding_width_m=18,
        bounding_height_m=12,
        edge_labels=[EdgeDimensionLabel(edge_index=0, length_m=18, source_text="18.00 m")],
    )
    inventory = ["18.00 m", "12.00 m", "8.00 m"]

    errors = validate_dimension_coverage(inventory, [polygon])

    assert len(errors) == 1
    assert "'8.00 m'" in errors[0]


def test_dimension_coverage_counts_duplicate_labels_separately():
    polygon = make_polygon(
        [(0, 0), (10, 0), (10, 4), (0, 4)],
        edge_labels=[EdgeDimensionLabel(edge_index=1, length_m=4, source_text="4.00 m")],
    )
    # Two printed "4.00 m" labels, only one attached anywhere.
    inventory = ["4.00 m", "4.00 m"]

    errors = validate_dimension_coverage(inventory, [polygon])

    assert len(errors) == 1


def test_floor_polygons_sharing_an_edge_pass_set_validation():
    left = make_polygon([(0, 0), (7, 0), (7, 9), (0, 9)], name="Left Wing")
    right = make_polygon([(7, 0), (12, 0), (12, 5), (7, 5)], name="Right Wing")

    assert validate_polygon_set([left, right]) == []
    assert compute_total_polygon_area(compute_polygon_areas([left, right])) == 88
