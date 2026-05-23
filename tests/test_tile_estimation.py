from abscissa_ci.models import RectangleDraft, TileEstimateInput
from abscissa_ci.workflows.tile_estimation import estimate_tiles


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
    assert "No valid rectangular dimensions" in result.warnings[-1]


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
