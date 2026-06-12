from pathlib import Path

from abscissa_ci.cli import output_paths


def test_example_floor_plan_outputs_are_organized():
    json_path, markdown_path = output_paths(Path("example_floor_plans/training/images/rectangular_floor_plan.png"))

    assert json_path == Path("example_floor_plans/json/tile_estimates/rectangular_floor_plan.tile_estimate.json")
    assert markdown_path == Path("example_floor_plans/reports/tile_estimates/rectangular_floor_plan.tile_estimate.md")


def test_non_example_outputs_stay_beside_source():
    json_path, markdown_path = output_paths(Path("tmp/floor_plan.png"))

    assert json_path == Path("tmp/floor_plan.tile_estimate.json")
    assert markdown_path == Path("tmp/floor_plan.tile_estimate.md")
