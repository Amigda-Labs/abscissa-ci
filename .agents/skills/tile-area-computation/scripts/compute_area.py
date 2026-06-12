#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def clean_float(value: float, places: int = 4) -> float:
    rounded = round(float(value), places)
    return 0.0 if rounded == -0.0 else rounded


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"Error: input file does not exist: {path}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)


def compute_polygon_zones(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], float, list[str], bool]:
    """Returns (zones, signed_total_sqm, warnings, had_errors).

    Polygon geometry and validation live in the abscissa_ci package so the
    rules cannot drift between the product code and this skill script. The
    restricted shell executor always runs this script with the project
    interpreter, where the package is importable.
    """

    polygons = payload.get("polygons")
    if not polygons:
        return [], 0.0, [], False
    if not isinstance(polygons, list):
        return [], 0.0, ["polygons must be an array."], True

    try:
        from abscissa_ci.calculators.polygon_geometry import (
            compute_polygon_areas,
            compute_total_polygon_area,
            validate_polygon_set,
        )
        from abscissa_ci.models import PolygonDraft
    except ImportError:
        return (
            [],
            0.0,
            ["Polygon input requires the abscissa_ci package, which is not importable here."],
            True,
        )

    drafts = []
    warnings: list[str] = []
    had_errors = False
    for index, item in enumerate(polygons, start=1):
        try:
            drafts.append(PolygonDraft.model_validate(item))
        except Exception as exc:
            warnings.append(f"Polygon {index} is invalid: {exc}")
            had_errors = True

    zones = compute_polygon_areas(drafts)
    for zone in zones:
        warnings.extend(zone.errors)
        warnings.extend(zone.warnings)
    valid_drafts = [draft for draft, zone in zip(drafts, zones) if zone.is_valid]
    cross_errors = validate_polygon_set(valid_drafts)
    warnings.extend(cross_errors)
    if any(not zone.is_valid for zone in zones) or cross_errors:
        had_errors = True

    total = 0.0 if had_errors else compute_total_polygon_area(zones)
    return [zone.model_dump(mode="json") for zone in zones], total, warnings, had_errors


def compute_area(payload: dict[str, Any]) -> dict[str, Any]:
    rectangles = payload.get("rectangles")
    has_polygons = bool(payload.get("polygons"))
    if (not isinstance(rectangles, list) or not rectangles) and not has_polygons:
        return {
            "can_compute": False,
            "rooms": [],
            "polygon_zones": [],
            "total_floor_area_sqm": None,
            "warnings": ["Input must include a non-empty rectangles or polygons array."],
        }

    rooms: list[dict[str, Any]] = []
    warnings: list[str] = []
    if rectangles is not None and not isinstance(rectangles, list):
        warnings.append("rectangles must be an array; it was ignored.")
        rectangles = []
    for index, rectangle in enumerate(rectangles or [], start=1):
        if not isinstance(rectangle, dict):
            warnings.append(f"Rectangle {index} must be an object.")
            continue

        name = str(rectangle.get("name") or f"Rectangle {index}")
        operation = rectangle.get("operation", "add")
        if operation not in {"add", "subtract"}:
            warnings.append(f"{name}: operation must be 'add' or 'subtract'.")
            continue

        try:
            length_m = float(rectangle["length_m"])
            width_m = float(rectangle["width_m"])
        except KeyError as exc:
            warnings.append(f"{name}: missing required field {exc}.")
            continue
        except (TypeError, ValueError):
            warnings.append(f"{name}: length_m and width_m must be numbers.")
            continue

        if length_m <= 0 or width_m <= 0:
            warnings.append(f"{name}: length_m and width_m must be greater than zero.")
            continue

        area_sqm = clean_float(length_m * width_m)
        signed_area_sqm = area_sqm if operation == "add" else -area_sqm
        rooms.append(
            {
                "name": name,
                "length_m": clean_float(length_m),
                "width_m": clean_float(width_m),
                "operation": operation,
                "area_sqm": area_sqm,
                "signed_area_sqm": signed_area_sqm,
                "calculation": f"{operation} ({length_m:g}m * {width_m:g}m)",
                "source_text": rectangle.get("source_text"),
            }
        )

    zones, polygon_total, polygon_warnings, polygon_errors = compute_polygon_zones(payload)
    warnings.extend(polygon_warnings)

    has_shapes = bool(rooms) or bool(zones)
    total_area = clean_float(sum(room["signed_area_sqm"] for room in rooms) + polygon_total)
    can_compute = has_shapes and not polygon_errors and total_area > 0
    if has_shapes and not polygon_errors and total_area <= 0:
        warnings.append("Net floor area must be greater than zero after subtractive areas.")

    return {
        "can_compute": can_compute,
        "rooms": rooms,
        "polygon_zones": zones,
        "total_floor_area_sqm": total_area if has_shapes and not polygon_errors else None,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute floor area from add/subtract rectangle or polygon floor-plan parts.",
    )
    parser.add_argument("input", nargs="?", type=Path, help="JSON file containing rectangles and/or polygons arrays.")
    parser.add_argument("--json", help="Inline JSON payload containing rectangles and/or polygons arrays.")
    parser.add_argument("--output", type=Path, help="Optional path for JSON output.")
    args = parser.parse_args()

    if args.json:
        try:
            payload = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid inline JSON: {exc}", file=sys.stderr)
            return 2
    elif args.input:
        payload = load_json(args.input)
    else:
        print("Error: provide an input file or --json payload.", file=sys.stderr)
        return 2

    result = compute_area(payload)
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")
    return 0 if result["can_compute"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
