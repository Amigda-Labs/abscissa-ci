from __future__ import annotations

import argparse
import html
import json
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "samples" / "floorplans"
IMAGES_DIR = SAMPLE_ROOT / "images"
ANSWER_DIR = SAMPLE_ROOT / "answer_sheets"
GOLD_DIR = SAMPLE_ROOT / "gold_extractions"

PX_PER_M = 92
MARGIN_PX = 140
WALL_PX = 8
FONT_FAMILY = "Arial, Helvetica, sans-serif"


@dataclass(frozen=True)
class Component:
    name: str
    x: float
    y: float
    width: float
    height: float
    operation: Literal["add", "subtract"] = "add"

    @property
    def area_sqm(self) -> float:
        sign = 1 if self.operation == "add" else -1
        return sign * self.width * self.height


@dataclass(frozen=True)
class Room:
    name: str
    x: float
    y: float
    width: float
    height: float
    room_type: str
    components: tuple[Component, ...] = field(default_factory=tuple)
    outline: tuple[tuple[float, float], ...] | None = None
    label_x: float | None = None
    label_y: float | None = None

    @property
    def area_sqm(self) -> float:
        if self.components:
            return sum(component.area_sqm for component in self.components)
        return self.width * self.height

    @property
    def all_components(self) -> tuple[Component, ...]:
        if self.components:
            return self.components
        return (
            Component(
                name=self.name,
                x=self.x,
                y=self.y,
                width=self.width,
                height=self.height,
            ),
        )


@dataclass(frozen=True)
class Fixture:
    fixture_type: Literal[
        "bed",
        "bath",
        "toilet",
        "sink",
        "counter",
        "sofa",
        "table",
        "washer",
        "car",
        "desk",
        "wardrobe",
    ]
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class Plan:
    plan_id: str
    title: str
    rooms: tuple[Room, ...]
    fixtures: tuple[Fixture, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


def plans() -> tuple[Plan, ...]:
    return (
        Plan(
            plan_id="plan_01_compact_apartment",
            title="Compact Apartment",
            rooms=(
                Room("Living / Dining", 0.0, 0.0, 5.20, 3.80, "living"),
                Room("Kitchen", 5.20, 0.0, 2.80, 2.60, "kitchen"),
                Room("Entry", 5.20, 2.60, 2.80, 1.20, "hall"),
                Room("Bedroom 1", 0.0, 3.80, 3.40, 3.20, "bedroom"),
                Room("Bedroom 2", 3.40, 3.80, 3.20, 3.00, "bedroom"),
                Room("Bathroom", 6.60, 3.80, 1.80, 2.20, "bathroom"),
                Room("Storage", 6.60, 6.00, 1.80, 1.00, "storage"),
            ),
            fixtures=(
                Fixture("sofa", 0.35, 0.45, 1.80, 0.70),
                Fixture("table", 2.90, 1.25, 1.20, 0.85),
                Fixture("counter", 5.45, 0.30, 2.20, 0.55),
                Fixture("bed", 0.40, 4.30, 1.80, 1.90),
                Fixture("bed", 3.80, 4.25, 1.70, 1.80),
                Fixture("bath", 6.85, 4.10, 1.20, 0.70),
                Fixture("toilet", 7.45, 5.00, 0.45, 0.55),
            ),
        ),
        Plan(
            plan_id="plan_02_l_shaped_family_flat",
            title="L-Shaped Family Flat",
            rooms=(
                Room(
                    "Living / Dining",
                    0.0,
                    0.0,
                    5.00,
                    5.80,
                    "living",
                    components=(
                        Component("Lounge rectangle", 0.0, 0.0, 5.00, 3.20, "add"),
                        Component("Living / Dining bay", 0.0, 3.20, 2.60, 2.60, "add"),
                    ),
                    outline=((0.0, 0.0), (5.00, 0.0), (5.00, 3.20), (2.60, 3.20), (2.60, 5.80), (0.0, 5.80)),
                ),
                Room("Kitchen", 5.00, 0.0, 3.00, 3.20, "kitchen"),
                Room("Hall", 2.60, 3.20, 5.40, 1.20, "hall"),
                Room("Primary Bedroom", 0.0, 5.80, 4.00, 3.40, "bedroom"),
                Room("Bedroom 2", 4.00, 4.40, 3.20, 3.20, "bedroom"),
                Room("Bath", 7.20, 3.20, 2.00, 2.20, "bathroom"),
                Room("Laundry", 7.20, 5.40, 2.00, 1.60, "laundry"),
                Room("Closet", 7.20, 7.00, 2.00, 1.20, "storage"),
            ),
            fixtures=(
                Fixture("sofa", 0.40, 0.55, 2.00, 0.75),
                Fixture("table", 0.70, 3.75, 1.15, 0.85),
                Fixture("counter", 5.25, 0.35, 2.35, 0.55),
                Fixture("bed", 0.50, 6.35, 2.00, 2.00),
                Fixture("bed", 4.45, 4.85, 1.70, 1.85),
                Fixture("bath", 7.45, 3.55, 1.20, 0.70),
                Fixture("washer", 7.60, 5.80, 0.70, 0.70),
                Fixture("wardrobe", 7.50, 7.35, 1.25, 0.45),
            ),
            notes=("Living / Dining is an L-shaped area decomposed into two additive rectangles.",),
        ),
        Plan(
            plan_id="plan_03_courtyard_unit",
            title="Courtyard Unit",
            rooms=(
                Room(
                    "Living Room",
                    0.0,
                    0.0,
                    5.60,
                    4.20,
                    "living",
                    components=(
                        Component("Living Room gross rectangle", 0.0, 0.0, 5.60, 4.20, "add"),
                        Component("Lightwell void", 2.20, 1.40, 1.20, 1.00, "subtract"),
                    ),
                    label_x=4.25,
                    label_y=3.20,
                ),
                Room("Kitchen", 5.60, 0.0, 2.80, 2.80, "kitchen"),
                Room("Bedroom", 0.0, 4.20, 3.60, 3.30, "bedroom"),
                Room("Study", 3.60, 4.20, 2.40, 2.60, "study"),
                Room("Bathroom", 6.00, 4.20, 2.40, 2.00, "bathroom"),
                Room("Entry Hall", 6.00, 2.80, 2.40, 1.40, "hall"),
            ),
            fixtures=(
                Fixture("sofa", 0.45, 0.55, 1.85, 0.70),
                Fixture("table", 3.85, 0.95, 1.10, 0.85),
                Fixture("counter", 5.90, 0.35, 2.10, 0.55),
                Fixture("bed", 0.45, 4.75, 1.80, 1.90),
                Fixture("desk", 4.05, 4.65, 1.15, 0.65),
                Fixture("bath", 6.30, 4.50, 1.30, 0.65),
            ),
            notes=("Living Room contains a 1.20 m x 1.00 m lightwell void excluded from floor area.",),
        ),
        Plan(
            plan_id="plan_04_townhouse_ground",
            title="Townhouse Ground Floor",
            rooms=(
                Room("Garage", 0.0, 0.0, 3.40, 5.40, "garage"),
                Room("Foyer", 3.40, 0.0, 2.20, 2.40, "hall"),
                Room("Powder Room", 5.60, 0.0, 1.80, 1.80, "bathroom"),
                Room("Stair Hall", 5.60, 1.80, 1.80, 3.60, "hall"),
                Room("Kitchen", 3.40, 2.40, 3.40, 3.00, "kitchen"),
                Room("Dining", 6.80, 1.80, 3.20, 3.60, "dining"),
                Room("Living Room", 3.40, 5.40, 6.60, 4.00, "living"),
                Room("Storage", 0.0, 5.40, 1.60, 1.80, "storage"),
                Room("Mudroom", 1.60, 5.40, 1.80, 1.80, "utility"),
            ),
            fixtures=(
                Fixture("car", 0.35, 0.55, 2.45, 4.15),
                Fixture("sink", 6.05, 0.45, 0.55, 0.45),
                Fixture("counter", 3.75, 2.75, 2.60, 0.55),
                Fixture("table", 7.55, 2.70, 1.20, 0.90),
                Fixture("sofa", 4.00, 6.05, 2.40, 0.80),
                Fixture("washer", 2.20, 5.85, 0.65, 0.65),
            ),
        ),
        Plan(
            plan_id="plan_05_small_clinic",
            title="Small Clinic Suite",
            rooms=(
                Room("Reception", 0.0, 0.0, 4.20, 3.20, "reception"),
                Room("Waiting", 4.20, 0.0, 3.60, 3.20, "waiting"),
                Room("Consult Room 1", 0.0, 3.20, 3.20, 3.20, "consult"),
                Room("Consult Room 2", 3.20, 3.20, 3.20, 3.20, "consult"),
                Room("Treatment", 6.40, 3.20, 3.40, 3.20, "treatment"),
                Room("WC", 7.80, 0.0, 2.00, 1.80, "bathroom"),
                Room("Records", 7.80, 1.80, 2.00, 1.40, "storage"),
                Room("Corridor", 0.0, 6.40, 9.80, 1.20, "corridor"),
            ),
            fixtures=(
                Fixture("desk", 0.50, 0.55, 1.40, 0.70),
                Fixture("sofa", 4.65, 0.75, 1.80, 0.65),
                Fixture("desk", 0.45, 3.75, 1.10, 0.65),
                Fixture("desk", 3.65, 3.75, 1.10, 0.65),
                Fixture("bed", 7.00, 3.75, 1.80, 0.80),
                Fixture("toilet", 8.25, 0.55, 0.45, 0.55),
                Fixture("sink", 8.95, 0.55, 0.50, 0.42),
                Fixture("wardrobe", 8.10, 2.20, 1.30, 0.45),
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-png", action="store_true")
    args = parser.parse_args()

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ANSWER_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "description": "Synthetic metric floor plans for Area Agent evaluation.",
        "measurement_basis": "net_internal_room_area",
        "scale": {"px_per_m": PX_PER_M},
        "plans": [],
    }

    for plan in plans():
        svg = build_svg(plan)
        svg_path = IMAGES_DIR / f"{plan.plan_id}.svg"
        png_path = IMAGES_DIR / f"{plan.plan_id}.png"
        svg_path.write_text(svg, encoding="utf-8")

        if not args.skip_png:
            render_png(svg_path, png_path)

        answer = build_answer_sheet(plan, png_path if png_path.exists() else svg_path)
        answer_json_path = ANSWER_DIR / f"{plan.plan_id}.answer.json"
        answer_md_path = ANSWER_DIR / f"{plan.plan_id}.answer.md"
        gold_path = GOLD_DIR / f"{plan.plan_id}.gold_extraction.json"
        answer_json_path.write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")
        answer_md_path.write_text(build_answer_markdown(answer), encoding="utf-8")
        gold_path.write_text(json.dumps(build_gold_extraction(plan), indent=2) + "\n", encoding="utf-8")

        manifest["plans"].append(
            {
                "plan_id": plan.plan_id,
                "title": plan.title,
                "image": str((png_path if png_path.exists() else svg_path).relative_to(ROOT)),
                "svg": str(svg_path.relative_to(ROOT)),
                "answer_sheet": str(answer_json_path.relative_to(ROOT)),
                "answer_markdown": str(answer_md_path.relative_to(ROOT)),
                "gold_extraction": str(gold_path.relative_to(ROOT)),
            }
        )

    (SAMPLE_ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    (SAMPLE_ROOT / "README.md").write_text(build_samples_readme(), encoding="utf-8")
    return 0


def build_svg(plan: Plan) -> str:
    min_x = min(room.x for room in plan.rooms)
    min_y = min(room.y for room in plan.rooms)
    max_x = max(room.x + room.width for room in plan.rooms)
    max_y = max(room.y + room.height for room in plan.rooms)

    width_px = int(math.ceil((max_x - min_x) * PX_PER_M + MARGIN_PX * 2))
    height_px = int(math.ceil((max_y - min_y) * PX_PER_M + MARGIN_PX * 2 + 88))

    def x(value_m: float) -> float:
        return MARGIN_PX + (value_m - min_x) * PX_PER_M

    def y(value_m: float) -> float:
        return MARGIN_PX + (value_m - min_y) * PX_PER_M

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" '
        f'viewBox="0 0 {width_px} {height_px}">',
        "<defs>",
        '<pattern id="grid" width="46" height="46" patternUnits="userSpaceOnUse">',
        '<path d="M 46 0 L 0 0 0 46" fill="none" stroke="#edf0f2" stroke-width="1"/>',
        "</pattern>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<rect width="100%" height="100%" fill="url(#grid)"/>',
        f'<text x="{MARGIN_PX}" y="42" font-family="{FONT_FAMILY}" font-size="24" '
        f'font-weight="700" fill="#172026">{escape(plan.title)}</text>',
        f'<text x="{MARGIN_PX}" y="68" font-family="{FONT_FAMILY}" font-size="13" fill="#4b5563">'
        "Synthetic metric plan - net room dimensions shown</text>",
    ]

    for room in plan.rooms:
        if room.outline:
            path_points = [f"{x(point_x):.2f},{y(point_y):.2f}" for point_x, point_y in room.outline]
            parts.append(
                f'<polygon points="{" ".join(path_points)}" '
                f'fill="#fbfbf8" stroke="#111827" stroke-width="{WALL_PX}" />'
            )
        elif room.components and any(component.operation == "add" for component in room.components):
            for component in room.components:
                if component.operation != "add":
                    continue
                parts.append(
                    f'<rect x="{x(component.x):.2f}" y="{y(component.y):.2f}" '
                    f'width="{component.width * PX_PER_M:.2f}" height="{component.height * PX_PER_M:.2f}" '
                    f'fill="#fbfbf8" stroke="#111827" stroke-width="{WALL_PX}" />'
                )
        else:
            parts.append(
                f'<rect x="{x(room.x):.2f}" y="{y(room.y):.2f}" '
                f'width="{room.width * PX_PER_M:.2f}" height="{room.height * PX_PER_M:.2f}" '
                f'fill="#fbfbf8" stroke="#111827" stroke-width="{WALL_PX}" />'
            )

    for room in plan.rooms:
        for component in room.all_components:
            if component.operation == "subtract":
                parts.append(
                    f'<rect x="{x(component.x):.2f}" y="{y(component.y):.2f}" '
                    f'width="{component.width * PX_PER_M:.2f}" height="{component.height * PX_PER_M:.2f}" '
                    'fill="#ffffff" stroke="#6b7280" stroke-width="4" stroke-dasharray="8 6" />'
                )

    for fixture in plan.fixtures:
        draw_fixture(parts, fixture, x(fixture.x), y(fixture.y))

    for room in plan.rooms:
        draw_room_label(parts, room, x, y)

    for room in plan.rooms:
        for component in room.all_components:
            if component.operation == "subtract":
                cx = x(component.x) + component.width * PX_PER_M / 2
                cy = y(component.y) + component.height * PX_PER_M / 2
                draw_text_block(
                    parts,
                    ["VOID", f"{fmt_m(component.width)} x {fmt_m(component.height)}"],
                    cx,
                    cy - 8,
                    font_size=12,
                    color="#374151",
                )

    draw_scale_bar(parts, MARGIN_PX, height_px - 48)

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def draw_room_label(parts: list[str], room: Room, x, y) -> None:
    if room.components:
        add_components = [component for component in room.components if component.operation == "add"]
        if add_components:
            largest = max(add_components, key=lambda component: component.width * component.height)
            cx = x(room.label_x) if room.label_x is not None else x(largest.x) + largest.width * PX_PER_M / 2
            cy = y(room.label_y) if room.label_y is not None else y(largest.y) + largest.height * PX_PER_M / 2
            lines = [room.name, f"{fmt_m(largest.width)} x {fmt_m(largest.height)}"]
            draw_text_block(parts, lines, cx, cy - 10, font_size=13)
            for component in add_components:
                if component is largest:
                    continue
                cx = x(component.x) + component.width * PX_PER_M / 2
                cy = y(component.y) + component.height * PX_PER_M / 2
                lines = [component.name, f"{fmt_m(component.width)} x {fmt_m(component.height)}"]
                draw_text_block(parts, lines, cx, cy - 8, font_size=12, color="#1f2937")
            return

    x_px = x(room.x)
    y_px = y(room.y)
    cx = x(room.label_x) if room.label_x is not None else x_px + room.width * PX_PER_M / 2
    cy = y(room.label_y) if room.label_y is not None else y_px + room.height * PX_PER_M / 2
    lines = [room.name, f"{fmt_m(room.width)} x {fmt_m(room.height)}"]
    draw_text_block(parts, lines, cx, cy - 10, font_size=14 if room.width >= 2.2 else 12)


def draw_text_block(
    parts: list[str],
    lines: list[str],
    cx: float,
    cy: float,
    *,
    font_size: int,
    color: str = "#111827",
) -> None:
    line_height = font_size + 4
    start_y = cy - ((len(lines) - 1) * line_height / 2)
    block_width = max(len(line) for line in lines) * font_size * 0.58 + 16
    block_height = len(lines) * line_height + 8
    parts.append(
        f'<rect x="{cx - block_width / 2:.2f}" y="{cy - block_height / 2:.2f}" '
        f'width="{block_width:.2f}" height="{block_height:.2f}" rx="4" '
        'fill="#fbfbf8" stroke="none" />'
    )
    for index, line in enumerate(lines):
        weight = "700" if index == 0 else "500"
        parts.append(
            f'<text x="{cx:.2f}" y="{start_y + index * line_height:.2f}" '
            f'font-family="{FONT_FAMILY}" font-size="{font_size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="middle" dominant-baseline="middle">{escape(line)}</text>'
        )


def draw_fixture(parts: list[str], fixture: Fixture, x_px: float, y_px: float) -> None:
    w = fixture.width * PX_PER_M
    h = fixture.height * PX_PER_M
    fill = "#eef2f7"
    stroke = "#94a3b8"
    parts.append(
        f'<rect x="{x_px:.2f}" y="{y_px:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2" />'
    )
    label = {
        "bed": "BED",
        "bath": "TUB",
        "toilet": "WC",
        "sink": "SINK",
        "counter": "CTR",
        "sofa": "SOFA",
        "table": "TBL",
        "washer": "WM",
        "car": "CAR",
        "desk": "DESK",
        "wardrobe": "WRD",
    }[fixture.fixture_type]
    parts.append(
        f'<text x="{x_px + w / 2:.2f}" y="{y_px + h / 2:.2f}" font-family="{FONT_FAMILY}" '
        'font-size="10" font-weight="700" fill="#64748b" text-anchor="middle" '
        f'dominant-baseline="middle">{label}</text>'
    )


def draw_dimension_frame(
    parts: list[str],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    x,
    y,
) -> None:
    left = x(min_x)
    top = y(min_y)
    right = x(max_x)
    bottom = y(max_y)
    offset = 38
    tick = 8

    width_label = fmt_m(max_x - min_x)
    height_label = fmt_m(max_y - min_y)
    parts.extend(
        [
            f'<line x1="{left:.2f}" y1="{top - offset:.2f}" x2="{right:.2f}" y2="{top - offset:.2f}" '
            'stroke="#334155" stroke-width="2"/>',
            f'<line x1="{left:.2f}" y1="{top - offset - tick:.2f}" x2="{left:.2f}" y2="{top - offset + tick:.2f}" '
            'stroke="#334155" stroke-width="2"/>',
            f'<line x1="{right:.2f}" y1="{top - offset - tick:.2f}" x2="{right:.2f}" y2="{top - offset + tick:.2f}" '
            'stroke="#334155" stroke-width="2"/>',
            f'<text x="{(left + right) / 2:.2f}" y="{top - offset - 10:.2f}" font-family="{FONT_FAMILY}" '
            f'font-size="13" font-weight="700" fill="#334155" text-anchor="middle">{width_label}</text>',
            f'<line x1="{left - offset:.2f}" y1="{top:.2f}" x2="{left - offset:.2f}" y2="{bottom:.2f}" '
            'stroke="#334155" stroke-width="2"/>',
            f'<line x1="{left - offset - tick:.2f}" y1="{top:.2f}" x2="{left - offset + tick:.2f}" y2="{top:.2f}" '
            'stroke="#334155" stroke-width="2"/>',
            f'<line x1="{left - offset - tick:.2f}" y1="{bottom:.2f}" x2="{left - offset + tick:.2f}" y2="{bottom:.2f}" '
            'stroke="#334155" stroke-width="2"/>',
            f'<text x="{left - offset - 14:.2f}" y="{(top + bottom) / 2:.2f}" font-family="{FONT_FAMILY}" '
            f'font-size="13" font-weight="700" fill="#334155" text-anchor="middle" '
            f'transform="rotate(-90 {left - offset - 14:.2f} {(top + bottom) / 2:.2f})">{height_label}</text>',
        ]
    )


def draw_scale_bar(parts: list[str], x_px: float, y_px: float) -> None:
    bar_w = 2 * PX_PER_M
    parts.extend(
        [
            f'<line x1="{x_px:.2f}" y1="{y_px:.2f}" x2="{x_px + bar_w:.2f}" y2="{y_px:.2f}" '
            'stroke="#111827" stroke-width="5"/>',
            f'<line x1="{x_px:.2f}" y1="{y_px - 8:.2f}" x2="{x_px:.2f}" y2="{y_px + 8:.2f}" '
            'stroke="#111827" stroke-width="3"/>',
            f'<line x1="{x_px + bar_w:.2f}" y1="{y_px - 8:.2f}" x2="{x_px + bar_w:.2f}" y2="{y_px + 8:.2f}" '
            'stroke="#111827" stroke-width="3"/>',
            f'<text x="{x_px + bar_w / 2:.2f}" y="{y_px + 24:.2f}" font-family="{FONT_FAMILY}" '
            'font-size="13" font-weight="700" fill="#111827" text-anchor="middle">2.00 m scale bar</text>',
        ]
    )


def render_png(svg_path: Path, png_path: Path) -> None:
    if render_png_with_pillow(svg_path, png_path):
        return

    qlmanage = shutil.which("qlmanage")
    if qlmanage is None:
        return

    for stale in (png_path, png_path.with_name(f"{svg_path.name}.png")):
        if stale.exists():
            stale.unlink()

    result = subprocess.run(
        [qlmanage, "-t", "-s", "1800", "-o", str(png_path.parent), str(svg_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    generated = png_path.with_name(f"{svg_path.name}.png")
    if result.returncode == 0 and generated.exists():
        generated.replace(png_path)


def render_png_with_pillow(svg_path: Path, png_path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    tree = ElementTree.parse(svg_path)
    root = tree.getroot()
    width = int(float(root.attrib["width"]))
    height = int(float(root.attrib["height"]))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    # Render the same plan directly from the SVG primitives we generated.
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag == "rect":
            x = parse_svg_length(element.attrib.get("x", "0"), width)
            y = parse_svg_length(element.attrib.get("y", "0"), height)
            w = parse_svg_length(element.attrib.get("width", str(width)), width)
            h = parse_svg_length(element.attrib.get("height", str(height)), height)
            fill = element.attrib.get("fill")
            stroke = element.attrib.get("stroke")
            stroke_width = int(float(element.attrib.get("stroke-width", 1)))
            if fill and fill.startswith("#"):
                draw.rectangle([x, y, x + w, y + h], fill=fill)
            if stroke and stroke.startswith("#"):
                draw.rectangle([x, y, x + w, y + h], outline=stroke, width=stroke_width)
        elif tag == "polygon":
            points = parse_points(element.attrib["points"])
            fill = element.attrib.get("fill", "#ffffff")
            stroke = element.attrib.get("stroke", "#000000")
            stroke_width = int(float(element.attrib.get("stroke-width", 1)))
            draw.polygon(points, fill=fill)
            draw.line(points + [points[0]], fill=stroke, width=stroke_width, joint="curve")
        elif tag == "line":
            stroke = element.attrib.get("stroke", "#000000")
            stroke_width = int(float(element.attrib.get("stroke-width", 1)))
            draw.line(
                [
                    float(element.attrib["x1"]),
                    float(element.attrib["y1"]),
                    float(element.attrib["x2"]),
                    float(element.attrib["y2"]),
                ],
                fill=stroke,
                width=stroke_width,
            )
        elif tag == "text":
            text = "".join(element.itertext())
            x = float(element.attrib["x"])
            y = float(element.attrib["y"])
            size = int(float(element.attrib.get("font-size", 14)))
            color = element.attrib.get("fill", "#111827")
            weight = element.attrib.get("font-weight", "400")
            font = load_font(ImageFont, size, bold=weight in {"700", "bold"})
            anchor = "mm" if element.attrib.get("text-anchor") == "middle" else "la"
            angle = rotation_angle(element.attrib.get("transform"))
            if angle:
                draw_rotated_text(image, text, x, y, font, color, angle)
            else:
                draw.text((x, y), text, fill=color, font=font, anchor=anchor)

    image.save(png_path)
    return True


def parse_points(value: str) -> list[tuple[float, float]]:
    points = []
    for point in value.split():
        x_value, y_value = point.split(",")
        points.append((float(x_value), float(y_value)))
    return points


def parse_svg_length(value: str, total: int) -> float:
    if value.endswith("%"):
        return total * float(value[:-1]) / 100
    return float(value)


def load_font(image_font, size: int, *, bold: bool):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return image_font.truetype(candidate, size=size)
            except OSError:
                continue
    return image_font.load_default()


def rotation_angle(transform: str | None) -> float | None:
    if not transform or not transform.startswith("rotate("):
        return None
    try:
        angle = transform.removeprefix("rotate(").split()[0]
        return float(angle)
    except (IndexError, ValueError):
        return None


def draw_rotated_text(image, text: str, x: float, y: float, font, color: str, angle: float) -> None:
    from PIL import Image, ImageDraw

    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0] + 16
    text_height = bbox[3] - bbox[1] + 16
    layer = Image.new("RGBA", (text_width, text_height), (255, 255, 255, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.text((text_width / 2, text_height / 2), text, fill=color, font=font, anchor="mm")
    rotated = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    image.paste(
        rotated.convert("RGB"),
        (int(x - rotated.width / 2), int(y - rotated.height / 2)),
        rotated,
    )


def build_answer_sheet(plan: Plan, image_path: Path) -> dict[str, object]:
    rooms = []
    for room in plan.rooms:
        components = [
            {
                "name": component.name,
                "operation": component.operation,
                "length_m": round(component.width, 2),
                "width_m": round(component.height, 2),
                "calculation": f"{component.width:.2f} m x {component.height:.2f} m",
                "signed_area_sqm": round(component.area_sqm, 4),
            }
            for component in room.all_components
        ]
        rooms.append(
            {
                "name": room.name,
                "room_type": room.room_type,
                "displayed_dimension": f"{room.width:.2f} m x {room.height:.2f} m",
                "components": components,
                "area_sqm": round(room.area_sqm, 4),
            }
        )

    total = sum(room.area_sqm for room in plan.rooms)
    return {
        "plan_id": plan.plan_id,
        "title": plan.title,
        "image": str(image_path.relative_to(ROOT)),
        "measurement_basis": "net_internal_room_area",
        "units": "metric",
        "scale": {"px_per_m": PX_PER_M},
        "notes": list(plan.notes),
        "rooms": rooms,
        "total_area_sqm": round(total, 4),
    }


def build_gold_extraction(plan: Plan) -> dict[str, object]:
    return {
        "project_name": plan.title,
        "requested_measurement_basis": "net_internal_room_area",
        "scale_basis": "dimension_labels",
        "units_detected": ["m"],
        "rooms": [
            {
                "room_id": room.name.lower().replace(" ", "_").replace("/", "").replace("__", "_"),
                "name": room.name,
                "room_type": room.room_type,
                "boundary_basis": "inside_face_of_walls",
                "measurement_method": "dimension_labels",
                "components": [
                    {
                        "component_id": component.name.lower().replace(" ", "_").replace("/", "").replace("__", "_"),
                        "name": component.name,
                        "operation": component.operation,
                        "length": {
                            "value": round(component.width, 2),
                            "unit": "m",
                            "source_text": f"{component.width:.2f} m",
                            "confidence": 1.0,
                        },
                        "width": {
                            "value": round(component.height, 2),
                            "unit": "m",
                            "source_text": f"{component.height:.2f} m",
                            "confidence": 1.0,
                        },
                        "reason": "Synthetic fixture ground truth",
                        "source_refs": [plan.plan_id],
                        "confidence": 1.0,
                    }
                    for component in room.all_components
                ],
                "labeled_area": None,
                "notes": [],
                "warnings": [],
                "confidence": 1.0,
            }
            for room in plan.rooms
        ],
        "consistency_checks": [],
        "assumptions": ["Synthetic fixture with net internal metric dimensions."],
        "warnings": [],
        "questions": [],
    }


def build_answer_markdown(answer: dict[str, object]) -> str:
    rooms = answer["rooms"]
    assert isinstance(rooms, list)
    lines = [
        f"# {answer['title']} Answer Sheet",
        "",
        f"- Plan ID: `{answer['plan_id']}`",
        f"- Measurement basis: {answer['measurement_basis']}",
        f"- Total area: {answer['total_area_sqm']} sqm",
        "",
        "## Room Computations",
        "",
        "| Room | Computation | Area (sqm) |",
        "| --- | --- | ---: |",
    ]
    for room in rooms:
        assert isinstance(room, dict)
        components = room["components"]
        assert isinstance(components, list)
        computation_parts = []
        for component in components:
            assert isinstance(component, dict)
            sign = "-" if component["operation"] == "subtract" else "+"
            computation_parts.append(f"{sign} {component['calculation']}")
        computation = " ".join(computation_parts).lstrip("+ ")
        lines.append(f"| {room['name']} | {computation} | {room['area_sqm']} |")
    lines.append("")
    return "\n".join(lines)


def build_samples_readme() -> str:
    return """# Synthetic Floor Plan Samples

These five generated plans are controlled fixtures for Area Agent evaluation.

- Images contain room labels and metric dimensions only.
- Images intentionally do not contain room areas or total areas.
- Answer sheets contain the ground-truth area computations.
- Gold extraction JSON files match the Area Agent structured schema for
  deterministic harness tests.
- Dimensions are net internal room dimensions.
- SVG files are the source drawings; PNG files are generated for model input.

Regenerate the set from the repository root:

```bash
PYTHONPATH=src .venv/bin/python tools/generate_synthetic_floorplans.py
```

Run the Area Agent evaluation:

```bash
PYTHONPATH=src .venv/bin/python -m abscissa_ci.cli eval-samples
```
"""


def fmt_m(value: float) -> str:
    return f"{value:.2f} m"


def escape(value: str) -> str:
    return html.escape(value, quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
