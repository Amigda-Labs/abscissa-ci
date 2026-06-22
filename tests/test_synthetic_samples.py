import json
import re
from pathlib import Path

from abscissa_ci.area.models import PlanAreaExtraction
from abscissa_ci.area.validation import solve_area_takeoff


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "samples" / "floorplans" / "manifest.json"


def test_synthetic_manifest_has_five_complete_floor_plans() -> None:
    manifest = read_json(MANIFEST)

    assert len(manifest["plans"]) == 5
    for entry in manifest["plans"]:
        assert (ROOT / entry["image"]).is_file()
        assert (ROOT / entry["svg"]).is_file()
        assert (ROOT / entry["answer_sheet"]).is_file()
        assert (ROOT / entry["answer_markdown"]).is_file()
        assert (ROOT / entry["gold_extraction"]).is_file()
        assert entry["image"].endswith(".png")


def test_floor_plan_images_do_not_leak_area_answers() -> None:
    manifest = read_json(MANIFEST)
    forbidden_patterns = [
        r"\bsqm\b",
        r"\bsq\.?\s*m\b",
        r"\bsquare\s+meters?\b",
        r"\btotal\s+area\b",
        r"\barea\s*[:=]",
    ]

    for entry in manifest["plans"]:
        svg_text = (ROOT / entry["svg"]).read_text(encoding="utf-8").lower()
        for pattern in forbidden_patterns:
            assert re.search(pattern, svg_text) is None, entry["svg"]


def test_gold_extractions_match_answer_sheets() -> None:
    manifest = read_json(MANIFEST)

    for entry in manifest["plans"]:
        answer = read_json(ROOT / entry["answer_sheet"])
        extraction = PlanAreaExtraction.model_validate(read_json(ROOT / entry["gold_extraction"]))
        report = solve_area_takeoff(extraction)

        assert report.can_compute is True
        assert report.total_area_sqm == answer["total_area_sqm"]
        actual_rooms = {room.name: room.area_sqm for room in report.rooms}
        for expected_room in answer["rooms"]:
            assert actual_rooms[expected_room["name"]] == expected_room["area_sqm"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
