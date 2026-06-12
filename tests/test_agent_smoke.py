import os
from pathlib import Path

import pytest

from abscissa_ci.agents.tile_agent import OPENAI_API_KEY_ENV, TILE_ENGINEER_API_KEY_ENV, estimate_tiles_from_image


@pytest.mark.agent
@pytest.mark.skipif(
    not (os.getenv(TILE_ENGINEER_API_KEY_ENV) or os.getenv(OPENAI_API_KEY_ENV)),
    reason=f"{TILE_ENGINEER_API_KEY_ENV} or {OPENAI_API_KEY_ENV} is not set",
)
def test_agent_image_smoke():
    image_path = Path("example_floor_plans/training/images/rectangular_floor_plan.png")
    if not image_path.exists():
        pytest.skip("example floor plan image is not available")

    import asyncio

    result = asyncio.run(estimate_tiles_from_image(image_path))

    assert result.review_status == "draft_for_human_evaluation"
    assert result.tile_area_sqm == 0.36
