#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
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


def area_from_payload(payload: dict[str, Any]) -> float | None:
    value = payload.get("total_floor_area_sqm")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def count_tiles(
    total_floor_area_sqm: float,
    tile_length_mm: float = 600,
    tile_width_mm: float = 600,
    waste_percent: float = 10,
) -> dict[str, Any]:
    warnings: list[str] = []

    if total_floor_area_sqm <= 0:
        warnings.append("total_floor_area_sqm must be greater than zero.")
    if tile_length_mm <= 0 or tile_width_mm <= 0:
        warnings.append("tile_length_mm and tile_width_mm must be greater than zero.")
    if waste_percent < 0:
        warnings.append("waste_percent cannot be negative.")

    if warnings:
        return {
            "can_compute": False,
            "warnings": warnings,
        }

    tile_area_sqm = clean_float((tile_length_mm / 1000) * (tile_width_mm / 1000), places=6)
    base_tile_count = math.ceil(total_floor_area_sqm / tile_area_sqm)
    order_tile_count = math.ceil(base_tile_count * (1 + (waste_percent / 100)))

    return {
        "can_compute": True,
        "total_floor_area_sqm": clean_float(total_floor_area_sqm),
        "tile_length_mm": clean_float(tile_length_mm),
        "tile_width_mm": clean_float(tile_width_mm),
        "tile_area_sqm": tile_area_sqm,
        "base_tile_count": base_tile_count,
        "order_tile_count": order_tile_count,
        "waste_percent": clean_float(waste_percent),
        "calculation": (
            f"ceil({total_floor_area_sqm:g} sqm / {tile_area_sqm:g} sqm), "
            f"then ceil(base_tiles * {1 + (waste_percent / 100):g})"
        ),
        "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count needed floor tiles from total floor area.",
    )
    parser.add_argument("input", nargs="?", type=Path, help="Optional JSON area result input.")
    parser.add_argument("--area-sqm", type=float, help="Total floor area in square meters.")
    parser.add_argument("--tile-length-mm", type=float, default=600, help="Tile length in millimeters.")
    parser.add_argument("--tile-width-mm", type=float, default=600, help="Tile width in millimeters.")
    parser.add_argument("--waste-percent", type=float, default=10, help="Waste allowance percentage.")
    parser.add_argument("--output", type=Path, help="Optional path for JSON output.")
    args = parser.parse_args()

    area_sqm = args.area_sqm
    if area_sqm is None and args.input:
        area_sqm = area_from_payload(load_json(args.input))
    if area_sqm is None:
        print("Error: provide --area-sqm or a JSON input with total_floor_area_sqm.", file=sys.stderr)
        return 2

    result = count_tiles(area_sqm, args.tile_length_mm, args.tile_width_mm, args.waste_percent)
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")
    return 0 if result["can_compute"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
