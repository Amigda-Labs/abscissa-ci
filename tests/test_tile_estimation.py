from abscissa_ci.models import (
    EdgeDimensionLabel,
    PolygonDraft,
    PolygonPoint,
    RectangleDraft,
    TileEstimateInput,
)
from abscissa_ci.workflows.tile_estimation import estimate_tiles


def make_polygon(coords, **kwargs):
    return PolygonDraft(points=[PolygonPoint(x_m=x, y_m=y) for x, y in coords], **kwargs)


def test_estimate_tiles_result_contract():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Simple House",
            input_source="json",
            rectangles=[RectangleDraft(name="Main", length_m=3, width_m=4, source_text="3m x 4m")],
        )
    )

    assert result.can_compute is True
    assert result.review_status == "draft_for_human_evaluation"
    assert result.total_floor_area_sqm == 12
    assert result.tile_area_sqm == 0.36
    assert result.base_tile_count == 34
    assert result.order_tile_count == 38
    assert result.rooms[0].calculation == "add (3m * 4m)"
    assert result.extracted_rectangles[0].source_text == "3m x 4m"


def test_estimate_tiles_handles_missing_rectangles_as_uncomputable():
    result = estimate_tiles(TileEstimateInput(project_name="Missing", input_source="image"))

    assert result.can_compute is False
    assert result.total_floor_area_sqm is None
    assert result.base_tile_count is None
    assert result.order_tile_count is None
    assert "No valid rectangle or polygon dimensions" in result.warnings[-1]


def test_estimate_tiles_supports_l_shape_as_multiple_rectangles():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="L Shape",
            rectangles=[
                RectangleDraft(name="Top Wing", length_m=12, width_m=5),
                RectangleDraft(name="Bottom Wing", length_m=7, width_m=4),
            ],
        )
    )

    assert result.total_floor_area_sqm == 88
    assert result.base_tile_count == 245
    assert result.order_tile_count == 270


def test_estimate_tiles_supports_subtractive_voids():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Void",
            rectangles=[
                RectangleDraft(name="Outer", length_m=16, width_m=10),
                RectangleDraft(name="Void", length_m=5, width_m=3, operation="subtract"),
            ],
        )
    )

    assert result.total_floor_area_sqm == 145
    assert result.base_tile_count == 403
    assert result.order_tile_count == 444


def test_estimate_tiles_from_l_shape_polygon_matches_rectangle_decomposition():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="L Shape Polygon",
            polygons=[
                make_polygon(
                    [(0, 0), (12, 0), (12, 5), (7, 5), (7, 9), (0, 9)],
                    name="L Shape Footprint",
                    edge_labels=[
                        EdgeDimensionLabel(edge_index=0, length_m=12, source_text="12.00 m"),
                        EdgeDimensionLabel(edge_index=3, length_m=4, source_text="4.00 m"),
                        EdgeDimensionLabel(edge_index=5, length_m=9, source_text="9.00 m"),
                    ],
                )
            ],
        )
    )

    assert result.can_compute is True
    assert result.total_floor_area_sqm == 88
    assert result.base_tile_count == 245
    assert result.order_tile_count == 270
    assert result.polygons[0].perimeter_m == 42


def test_estimate_tiles_supports_polygon_voids():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Polygon Void",
            polygons=[
                make_polygon([(0, 0), (16, 0), (16, 10), (0, 10)], name="Outer"),
                make_polygon(
                    [(5, 3), (10, 3), (10, 6), (5, 6)], name="Void", operation="subtract"
                ),
            ],
        )
    )

    assert result.can_compute is True
    assert result.total_floor_area_sqm == 145
    assert result.base_tile_count == 403


def test_estimate_tiles_combines_rectangles_and_polygons():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Mixed",
            rectangles=[RectangleDraft(name="Annex", length_m=3, width_m=4)],
            polygons=[make_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], name="Main")],
        )
    )

    assert result.can_compute is True
    assert result.total_floor_area_sqm == 112


def test_estimate_tiles_gates_on_label_mismatch():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Bad Label",
            polygons=[
                make_polygon(
                    [(0, 0), (12, 0), (12, 5), (7, 5), (7, 9), (0, 9)],
                    name="L Shape Footprint",
                    edge_labels=[EdgeDimensionLabel(edge_index=0, length_m=11)],
                )
            ],
        )
    )

    assert result.can_compute is False
    assert result.total_floor_area_sqm is None
    assert any("labeled 11m" in warning for warning in result.warnings)
    assert "Polygon validation failed" in result.warnings[-1]


def test_estimate_tiles_gates_on_overlapping_floor_polygons():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Overlap",
            polygons=[
                make_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], name="First"),
                make_polygon([(5, 5), (15, 5), (15, 15), (5, 15)], name="Second"),
            ],
        )
    )

    assert result.can_compute is False
    assert any("double-counted" in warning for warning in result.warnings)


def test_extraction_validation_errors_block_computation():
    from abscissa_ci.models import PolygonDraft, PolygonPoint

    estimate_input = TileEstimateInput(
        polygons=[
            PolygonDraft(
                name="Plausible but unverified",
                points=[
                    PolygonPoint(x_m=0, y_m=0),
                    PolygonPoint(x_m=10, y_m=0),
                    PolygonPoint(x_m=10, y_m=8),
                    PolygonPoint(x_m=0, y_m=8),
                ],
            )
        ],
        validation_errors=[
            "Floor: corner x position(s) 4m do not align with the printed "
            "dimension stations on the x axis (0, 5, 9, 16m)."
        ],
    )

    result = estimate_tiles(estimate_input)

    assert result.can_compute is False
    assert result.base_tile_count is None
    assert any("do not align" in warning for warning in result.warnings)
