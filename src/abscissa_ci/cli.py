from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from abscissa_ci.agents.area_agent import analyze_area_from_image
from abscissa_ci.area.models import MeasurementBasis, PlanAreaExtraction
from abscissa_ci.area.validation import solve_area_takeoff
from abscissa_ci.evaluation.sample_eval import run_evaluation_sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abscissa-area")
    subparsers = parser.add_subparsers(dest="command", required=True)

    image_parser = subparsers.add_parser("image", help="Analyze a floor-plan image.")
    image_parser.add_argument("image_path", type=Path)
    image_parser.add_argument("--model", default=None)
    image_parser.add_argument(
        "--basis",
        default="net_internal_room_area",
        choices=["net_internal_room_area", "gross_floor_area", "centerline_area", "unknown"],
    )
    image_parser.add_argument("--output", type=Path, default=None)

    validate_parser = subparsers.add_parser(
        "validate-json",
        help="Compute and validate area from a structured extraction JSON file.",
    )
    validate_parser.add_argument("json_path", type=Path)
    validate_parser.add_argument(
        "--basis",
        default="net_internal_room_area",
        choices=["net_internal_room_area", "gross_floor_area", "centerline_area", "unknown"],
    )
    validate_parser.add_argument("--output", type=Path, default=None)

    eval_parser = subparsers.add_parser(
        "eval-samples",
        help="Run the Area Agent against generated synthetic sample plans.",
    )
    eval_parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("samples/floorplans/manifest.json"),
    )
    eval_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("samples/floorplans/agent_outputs"),
    )
    eval_parser.add_argument("--model", default=None)
    eval_parser.add_argument("--limit", type=int, default=None)
    eval_parser.add_argument("--output", type=Path, default=None)
    eval_parser.add_argument(
        "--force",
        action="store_true",
        help="Call the Area Agent again even when saved reports already exist.",
    )

    args = parser.parse_args(argv)

    if args.command == "image":
        report = asyncio.run(
            analyze_area_from_image(
                args.image_path,
                requested_measurement_basis=args.basis,
                model=args.model,
            )
        )
        payload = report.model_dump(mode="json", exclude_none=True)
    elif args.command == "validate-json":
        extraction = PlanAreaExtraction.model_validate(_read_json(args.json_path))
        report = solve_area_takeoff(
            extraction,
            requested_measurement_basis=_basis(args.basis),
        )
        payload = report.model_dump(mode="json", exclude_none=True)
    else:
        payload = run_evaluation_sync(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            model=args.model,
            limit=args.limit,
            force=args.force,
        )

    output_text = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(output_text + "\n", encoding="utf-8")
    else:
        print(output_text)
    return 0


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _basis(value: str) -> MeasurementBasis:
    return value  # type: ignore[return-value]


if __name__ == "__main__":
    raise SystemExit(main())
