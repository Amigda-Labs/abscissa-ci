from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from abscissa_ci.agents.area_agent import analyze_area_from_image
from abscissa_ci.area.models import AreaReport


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / "samples" / "floorplans" / "manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "samples" / "floorplans" / "agent_outputs"
ROOM_TOLERANCE_SQM = 0.35
ROOM_TOLERANCE_PERCENT = 0.04
TOTAL_TOLERANCE_PERCENT = 0.03
TOTAL_TOLERANCE_SQM = 0.75


@dataclass(frozen=True)
class EvalResult:
    plan_id: str
    passed: bool
    total_expected_sqm: float
    total_actual_sqm: float | None
    failures: list[str]
    output_path: Path


async def evaluate_samples(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    model: str | None = None,
    limit: int | None = None,
    force: bool = False,
) -> list[EvalResult]:
    manifest_path = absolute_path(manifest_path)
    output_dir = absolute_path(output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_entries = manifest["plans"]
    if limit is not None:
        plan_entries = plan_entries[:limit]

    results: list[EvalResult] = []
    for entry in plan_entries:
        image_path = ROOT / entry["image"]
        answer_path = ROOT / entry["answer_sheet"]
        answer = json.loads(answer_path.read_text(encoding="utf-8"))
        output_path = output_dir / f"{entry['plan_id']}.area_report.json"
        if output_path.exists() and not force:
            report = AreaReport.model_validate(json.loads(output_path.read_text(encoding="utf-8")))
        else:
            report = await analyze_area_from_image(image_path, model=model)
            output_path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
        results.append(compare_report(entry["plan_id"], answer, report, output_path))
    return results


def compare_report(
    plan_id: str,
    answer: dict[str, Any],
    report: AreaReport,
    output_path: Path,
) -> EvalResult:
    failures: list[str] = []
    expected_total = float(answer["total_area_sqm"])
    actual_total = report.total_area_sqm

    if not report.can_compute:
        failures.append("Agent report returned can_compute=false.")
    if actual_total is None:
        failures.append("Agent report did not include total_area_sqm.")
    elif not within_tolerance(
        expected_total,
        float(actual_total),
        absolute_tolerance=TOTAL_TOLERANCE_SQM,
        percent_tolerance=TOTAL_TOLERANCE_PERCENT,
    ):
        failures.append(
            f"Total area mismatch: expected {expected_total:.2f} sqm, got {actual_total:.2f} sqm."
        )

    expected_rooms = {normalize_name(room["name"]): room for room in answer["rooms"]}
    actual_rooms = {normalize_name(room.name): room for room in report.rooms}

    for normalized_name, expected_room in expected_rooms.items():
        actual_room = actual_rooms.get(normalized_name)
        if actual_room is None:
            actual_room = find_fuzzy_room(normalized_name, actual_rooms)
        if actual_room is None:
            failures.append(f"Missing room: {expected_room['name']}.")
            continue
        if actual_room.area_sqm is None:
            failures.append(f"Room {expected_room['name']} has no computed area.")
            continue
        expected_area = float(expected_room["area_sqm"])
        if not within_tolerance(
            expected_area,
            float(actual_room.area_sqm),
            absolute_tolerance=ROOM_TOLERANCE_SQM,
            percent_tolerance=ROOM_TOLERANCE_PERCENT,
        ):
            failures.append(
                f"Room area mismatch for {expected_room['name']}: expected "
                f"{expected_area:.2f} sqm, got {actual_room.area_sqm:.2f} sqm."
            )

    return EvalResult(
        plan_id=plan_id,
        passed=not failures,
        total_expected_sqm=expected_total,
        total_actual_sqm=float(actual_total) if actual_total is not None else None,
        failures=failures,
        output_path=output_path,
    )


def summarize_results(results: list[EvalResult]) -> dict[str, Any]:
    return {
        "passed": all(result.passed for result in results),
        "plans_evaluated": len(results),
        "plans_passed": sum(1 for result in results if result.passed),
        "results": [
            {
                "plan_id": result.plan_id,
                "passed": result.passed,
                "total_expected_sqm": result.total_expected_sqm,
                "total_actual_sqm": result.total_actual_sqm,
                "failures": result.failures,
                "output_path": str(relative_to_root(result.output_path)),
            }
            for result in results
        ],
    }


def within_tolerance(
    expected: float,
    actual: float,
    *,
    absolute_tolerance: float,
    percent_tolerance: float,
) -> bool:
    return abs(expected - actual) <= max(absolute_tolerance, abs(expected) * percent_tolerance)


def find_fuzzy_room(normalized_name: str, actual_rooms: dict[str, Any]) -> Any | None:
    expected_tokens = set(normalized_name.split())
    best_room = None
    best_score = 0.0
    for actual_name, room in actual_rooms.items():
        actual_tokens = set(actual_name.split())
        if not actual_tokens:
            continue
        overlap = len(expected_tokens & actual_tokens)
        score = overlap / max(len(expected_tokens), len(actual_tokens))
        if score > best_score:
            best_score = score
            best_room = room
    return best_room if best_score >= 0.5 else None


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(normalized.split())


def absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def relative_to_root(path: Path) -> Path:
    path = path.resolve()
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def run_evaluation_sync(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    model: str | None = None,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    results = asyncio.run(
        evaluate_samples(
            manifest_path=manifest_path,
            output_dir=output_dir,
            model=model,
            limit=limit,
            force=force,
        )
    )
    return summarize_results(results)
