import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(script: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_tile_area_computation_skill_script(tmp_path):
    input_path = tmp_path / "l_shape.json"
    input_path.write_text(
        json.dumps(
            {
                "rectangles": [
                    {"name": "Main", "length_m": 12, "width_m": 5, "operation": "add"},
                    {"name": "Wing", "length_m": 7, "width_m": 4, "operation": "add"},
                ]
            }
        )
    )

    result = run_script(
        ROOT / ".agents/skills/tile-area-computation/scripts/compute_area.py",
        str(input_path),
    )
    payload = json.loads(result.stdout)

    assert payload["can_compute"] is True
    assert payload["total_floor_area_sqm"] == 88
    assert payload["rooms"][0]["calculation"] == "add (12m * 5m)"


def test_tile_counting_skill_script_from_area_json(tmp_path):
    input_path = tmp_path / "area.json"
    input_path.write_text(json.dumps({"total_floor_area_sqm": 88}))

    result = run_script(
        ROOT / ".agents/skills/tile-counting/scripts/count_tiles.py",
        str(input_path),
    )
    payload = json.loads(result.stdout)

    assert payload["can_compute"] is True
    assert payload["tile_area_sqm"] == 0.36
    assert payload["base_tile_count"] == 245
    assert payload["order_tile_count"] == 270
