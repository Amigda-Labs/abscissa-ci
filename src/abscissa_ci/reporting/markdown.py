from __future__ import annotations

from abscissa_ci.models import TileEstimateResult


def render_tile_estimate_markdown(result: TileEstimateResult) -> str:
    lines: list[str] = [
        f"# {result.project_name}",
        "",
        "## Tile Estimate Draft",
        "",
        f"- Review status: `{result.review_status}`",
        f"- Input source: `{result.input_source}`",
    ]

    if result.source_image_path:
        lines.append(f"- Source image: `{result.source_image_path}`")

    lines.extend(
        [
            f"- Tile size: `{result.tile_spec.length_mm:g}mm x {result.tile_spec.width_mm:g}mm`",
            f"- Tile area: `{result.tile_area_sqm:g} sqm`",
            f"- Waste allowance: `{result.waste_percent:g}%`",
            "",
        ]
    )

    if result.can_compute:
        lines.extend(
            [
                f"Total floor area: **{result.total_floor_area_sqm:g} sqm**",
                f"Base tiles needed: **{result.base_tile_count} pcs**",
                f"Order quantity with waste: **{result.order_tile_count} pcs**",
                "",
                "## Room Areas",
                "",
                "| Area | Operation | Dimensions | Net area | Source |",
                "| --- | --- | ---: | ---: | --- |",
            ]
        )
        for room in result.rooms:
            source = room.source_text or ""
            lines.append(
                f"| {room.name} | {room.operation} | {room.length_m:g}m x {room.width_m:g}m | "
                f"{room.signed_area_sqm:g} sqm | {source} |"
            )
        lines.append("")
    else:
        lines.extend(
            [
                "The tile estimate could not be computed because no valid rectangular dimensions were available.",
                "",
            ]
        )

    lines.extend(["## Assumptions", ""])
    if result.assumptions:
        lines.extend(f"- {item}" for item in result.assumptions)
    else:
        lines.append("- No additional assumptions recorded.")

    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {item}" for item in result.warnings)
    else:
        lines.append("- No warnings recorded.")

    lines.extend(
        [
            "",
            "This is a draft construction calculation for human evaluation. It is not a final estimate or installation instruction.",
            "",
        ]
    )
    return "\n".join(lines)
