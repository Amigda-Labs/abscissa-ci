from abscissa_ci.models import RectangleDraft, TileEstimateInput
from abscissa_ci.reporting.markdown import render_tile_estimate_markdown
from abscissa_ci.workflows.tile_estimation import estimate_tiles


def test_markdown_report_contains_summary_and_review_status():
    result = estimate_tiles(
        TileEstimateInput(
            project_name="Report Test",
            rectangles=[RectangleDraft(name="Main", length_m=3, width_m=4)],
        )
    )

    markdown = render_tile_estimate_markdown(result)

    assert "# Report Test" in markdown
    assert "draft_for_human_evaluation" in markdown
    assert "Order quantity with waste: **38 pcs**" in markdown
