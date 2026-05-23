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


def compute_area(payload: dict[str, Any]) -> dict[str, Any]:
    rectangles = payload.get("rectangles")
    if not isinstance(rectangles, list) or not rectangles:
        return {
            "can_compute": False,
            "rooms": [],
            "total_floor_area_sqm": None,
            "warnings": ["Input must include a non-empty rectangles array."],
        }

    rooms: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, rectangle in enumerate(rectangles, start=1):
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

    total_area = clean_float(sum(room["signed_area_sqm"] for room in rooms))
    can_compute = bool(rooms) and total_area > 0
    if rooms and total_area <= 0:
        warnings.append("Net floor area must be greater than zero after subtractive rectangles.")

    return {
        "can_compute": can_compute,
        "rooms": rooms,
        "total_floor_area_sqm": total_area if rooms else None,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute floor area from add/subtract rectangular floor-plan parts.",
    )
    parser.add_argument("input", nargs="?", type=Path, help="JSON file containing a rectangles array.")
    parser.add_argument("--json", help="Inline JSON payload containing a rectangles array.")
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
