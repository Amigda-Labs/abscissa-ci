from __future__ import annotations

from html import escape
from math import hypot

from abscissa_ci.cad.door_style import DoorStyle, load_door_style
from abscissa_ci.cad.models import CadProject, LotArea, Opening, Point, WallSegment


SCALE_PX_PER_M = 80.0
MARGIN_PX = 64.0


def export_project_svg(project: CadProject) -> str:
    level = project.levels[0]
    bounds = _project_bounds(project)
    min_x, min_y, max_x, max_y = bounds
    width = max(640.0, (max_x - min_x) * SCALE_PX_PER_M + MARGIN_PX * 2)
    height = max(420.0, (max_y - min_y) * SCALE_PX_PER_M + MARGIN_PX * 2)

    def sx(value: float) -> float:
        return (value - min_x) * SCALE_PX_PER_M + MARGIN_PX

    def sy(value: float) -> float:
        return (value - min_y) * SCALE_PX_PER_M + MARGIN_PX

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
            f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'
        ),
        f"<title>{escape(project.project.name)}</title>",
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<g id="lot-areas" fill="none">',
    ]

    for lot in level.lots:
        min_x, min_y, max_x, max_y = _lot_bounds(lot)
        area_sqm = lot.area_sqm
        stroke_width = max(1.0, (lot.boundary_thickness_mm / 1000.0) * SCALE_PX_PER_M)
        rect_x = sx(min_x)
        rect_y = sy(min_y)
        rect_width = (max_x - min_x) * SCALE_PX_PER_M
        rect_height = (max_y - min_y) * SCALE_PX_PER_M
        lines.append(
            f'<rect id="{escape(lot.lot_id)}" x="{rect_x:.2f}" y="{rect_y:.2f}" '
            f'width="{rect_width:.2f}" height="{rect_height:.2f}" stroke="#0f766e" '
            f'stroke-width="{stroke_width:.2f}" stroke-dasharray="12 6 2 6" '
            f'data-entity-type="lot-area" data-area-sqm="{area_sqm:.4f}"/>'
        )
        for corner in _lot_corners(lot):
            lines.append(
                f'<circle cx="{sx(corner.x):.2f}" cy="{sy(corner.y):.2f}" r="4" '
                'fill="#f8fafc" stroke="#0f766e" stroke-width="1.5"/>'
            )

    lines.extend(
        [
            "</g>",
        '<g id="draft-lines" stroke-linecap="square" fill="none">',
        ]
    )

    for draft_line in level.lines:
        lines.append(
            f'<line id="{escape(draft_line.line_id)}" '
            f'x1="{sx(draft_line.start.x):.2f}" y1="{sy(draft_line.start.y):.2f}" '
            f'x2="{sx(draft_line.end.x):.2f}" y2="{sy(draft_line.end.y):.2f}" '
            'stroke="#64748b" stroke-width="1.5" stroke-dasharray="6 5" '
            'data-entity-type="draft-line"/>'
        )

    lines.extend(
        [
            "</g>",
            '<g id="walls" stroke-linecap="butt" fill="none">',
        ]
    )

    for wall in level.walls:
        stroke = "#111827" if wall.wall_type == "exterior" else "#374151"
        stroke_width = max(2.0, (wall.thickness_mm or 100.0) / 1000.0 * SCALE_PX_PER_M)
        lines.append(
            f'<line id="{escape(wall.wall_id)}" x1="{sx(wall.start.x):.2f}" '
            f'y1="{sy(wall.start.y):.2f}" x2="{sx(wall.end.x):.2f}" '
            f'y2="{sy(wall.end.y):.2f}" stroke="{stroke}" '
            f'stroke-width="{stroke_width:.2f}" data-wall-type="{wall.wall_type}"/>'
        )

    lines.append("</g>")
    lines.append('<g id="openings" fill="none" stroke-linecap="butt">')

    wall_by_id = {wall.wall_id: wall for wall in level.walls}
    door_style = load_door_style()
    for opening in level.openings:
        opening_geometry = _opening_geometry(wall_by_id, opening)
        if opening_geometry is None:
            continue
        start, end, wall_thickness_mm = opening_geometry
        stroke_width = max(4.0, (wall_thickness_mm or 100.0) / 1000.0 * SCALE_PX_PER_M + 3.0)
        color = "#2563eb" if opening.opening_type == "window" else "#f8fafc"
        lines.append(
            f'<line id="{escape(opening.opening_id)}" x1="{sx(start.x):.2f}" '
            f'y1="{sy(start.y):.2f}" x2="{sx(end.x):.2f}" y2="{sy(end.y):.2f}" '
            f'stroke="{color}" stroke-width="{stroke_width:.2f}" '
            f'data-opening-type="{opening.opening_type}"/>'
        )
        if opening.opening_type == "door":
            lines.extend(
                _door_svg(opening, start, end, wall_thickness_mm, sx, sy, door_style)
            )

    lines.append("</g>")
    lines.append('<g id="rooms" font-family="Inter, Arial, sans-serif" text-anchor="middle">')
    for room in level.rooms:
        lines.append(
            f'<text id="{escape(room.room_id)}" x="{sx(room.label.x):.2f}" '
            f'y="{sy(room.label.y):.2f}" font-size="14" fill="#0f172a">'
            f"{escape(room.name)}</text>"
        )
    lines.append("</g>")

    lines.append('<g id="dimensions" font-family="Inter, Arial, sans-serif" fill="#475569">')
    for dimension in level.dimensions:
        label = dimension.label or _format_distance(dimension.start, dimension.end)
        display_start, display_end = _dimension_display_points(
            dimension.start,
            dimension.end,
            dimension.offset_m,
        )
        mid_x = (display_start.x + display_end.x) / 2
        mid_y = (display_start.y + display_end.y) / 2
        lines.append(
            f'<line id="{escape(dimension.dimension_id)}" '
            f'x1="{sx(display_start.x):.2f}" y1="{sy(display_start.y):.2f}" '
            f'x2="{sx(display_end.x):.2f}" y2="{sy(display_end.y):.2f}" '
            'stroke="#64748b" stroke-width="1.5" stroke-dasharray="4 4"/>'
        )
        lines.append(
            f'<line x1="{sx(dimension.start.x):.2f}" y1="{sy(dimension.start.y):.2f}" '
            f'x2="{sx(display_start.x):.2f}" y2="{sy(display_start.y):.2f}" '
            'stroke="#94a3b8" stroke-width="1"/>'
        )
        lines.append(
            f'<line x1="{sx(dimension.end.x):.2f}" y1="{sy(dimension.end.y):.2f}" '
            f'x2="{sx(display_end.x):.2f}" y2="{sy(display_end.y):.2f}" '
            'stroke="#94a3b8" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{sx(mid_x):.2f}" y="{sy(mid_y) - 6:.2f}" '
            f'font-size="12" text-anchor="middle">{escape(label)}</text>'
        )
    lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines)


def _project_bounds(project: CadProject) -> tuple[float, float, float, float]:
    points: list[Point] = []
    for level in project.levels:
        for lot in level.lots:
            points.extend(_lot_corners(lot))
        for draft_line in level.lines:
            points.extend([draft_line.start, draft_line.end])
        for wall in level.walls:
            points.extend([wall.start, wall.end])
        for room in level.rooms:
            points.append(room.label)
        for dimension in level.dimensions:
            points.extend([dimension.start, dimension.end])
            points.extend(_dimension_display_points(dimension.start, dimension.end, dimension.offset_m))

    if not points:
        return 0.0, 0.0, 8.0, 5.0

    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    max_x = max(point.x for point in points)
    max_y = max(point.y for point in points)
    if min_x == max_x:
        max_x += 1.0
    if min_y == max_y:
        max_y += 1.0
    return min_x, min_y, max_x, max_y


def _opening_points(wall: WallSegment, opening: Opening) -> tuple[Point, Point]:
    length = wall.length_m
    if length <= 0:
        return wall.start, wall.start
    start_ratio = opening.offset_m / length
    end_ratio = min(length, opening.offset_m + opening.width_m) / length
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    return (
        Point(x=wall.start.x + dx * start_ratio, y=wall.start.y + dy * start_ratio),
        Point(x=wall.start.x + dx * end_ratio, y=wall.start.y + dy * end_ratio),
    )


def _opening_geometry(
    wall_by_id: dict[str, WallSegment],
    opening: Opening,
) -> tuple[Point, Point, float | None] | None:
    if opening.start is not None and opening.end is not None:
        return opening.start, opening.end, opening.wall_thickness_mm
    if opening.parent_wall_id is None:
        return None
    wall = wall_by_id.get(opening.parent_wall_id)
    if wall is None:
        return None
    start, end = _opening_points(wall, opening)
    return start, end, wall.thickness_mm


def _door_svg(
    opening: Opening,
    start: Point,
    end: Point,
    wall_thickness_mm: float | None,
    sx,
    sy,
    style: DoorStyle,
) -> list[str]:
    start_x = sx(start.x)
    start_y = sy(start.y)
    end_x = sx(end.x)
    end_y = sy(end.y)
    span_px = hypot(end_x - start_x, end_y - start_y)
    if span_px <= 0:
        return []

    base_tx = (end_x - start_x) / span_px
    base_ty = (end_y - start_y) / span_px
    perpendicular_x = -base_ty
    perpendicular_y = base_tx

    frame_depth = max(10.0, (wall_thickness_mm or 100.0) / 1000.0 * SCALE_PX_PER_M + 6.0)
    half_frame = frame_depth / 2.0

    jamb_mm = opening.frame_jamb_mm if opening.frame_jamb_mm is not None else style.frame_jamb_mm
    jamb_length = max(style.jamb_px_min, (jamb_mm / 1000.0) * SCALE_PX_PER_M)

    leaf_mm = (
        opening.leaf_thickness_mm
        if opening.leaf_thickness_mm is not None
        else style.leaf_thickness_mm
    )
    leaf_thickness = max(
        style.leaf_thickness_px_min,
        min(style.leaf_thickness_px_max, (leaf_mm / 1000.0) * SCALE_PX_PER_M),
    )

    if opening.hinge_side == "end":
        hinge_x, hinge_y = end_x, end_y
        latch_x, latch_y = start_x, start_y
    else:
        hinge_x, hinge_y = start_x, start_y
        latch_x, latch_y = end_x, end_y
    swing_tx = (latch_x - hinge_x) / span_px
    swing_ty = (latch_y - hinge_y) / span_px

    if opening.swing_direction == "ccw":
        normal_x = swing_ty
        normal_y = -swing_tx
    else:
        normal_x = -swing_ty
        normal_y = swing_tx

    hinge_inner_x = hinge_x + swing_tx * jamb_length + normal_x * half_frame
    hinge_inner_y = hinge_y + swing_ty * jamb_length + normal_y * half_frame
    latch_inner_x = latch_x - swing_tx * jamb_length + normal_x * half_frame
    latch_inner_y = latch_y - swing_ty * jamb_length + normal_y * half_frame
    leaf_length = max(10.0, hypot(latch_inner_x - hinge_inner_x, latch_inner_y - hinge_inner_y))
    leaf_end_x = hinge_inner_x + normal_x * leaf_length
    leaf_end_y = hinge_inner_y + normal_y * leaf_length
    sweep_flag = "0" if opening.swing_direction == "ccw" else "1"

    def jamb_points(anchor_x: float, anchor_y: float, inward: float) -> list[tuple[float, float]]:
        inner_x = anchor_x + base_tx * jamb_length * inward
        inner_y = anchor_y + base_ty * jamb_length * inward
        return [
            (anchor_x + perpendicular_x * half_frame, anchor_y + perpendicular_y * half_frame),
            (inner_x + perpendicular_x * half_frame, inner_y + perpendicular_y * half_frame),
            (inner_x - perpendicular_x * half_frame, inner_y - perpendicular_y * half_frame),
            (anchor_x - perpendicular_x * half_frame, anchor_y - perpendicular_y * half_frame),
        ]

    leaf_points = [
        (hinge_inner_x, hinge_inner_y),
        (leaf_end_x, leaf_end_y),
        (leaf_end_x + swing_tx * leaf_thickness, leaf_end_y + swing_ty * leaf_thickness),
        (hinge_inner_x + swing_tx * leaf_thickness, hinge_inner_y + swing_ty * leaf_thickness),
    ]

    colors = style.colors
    svg: list[str] = []
    for anchor_x, anchor_y, inward in (
        (start_x, start_y, 1.0),
        (end_x, end_y, -1.0),
    ):
        svg.append(
            '<polygon points="'
            + " ".join(f"{x:.2f},{y:.2f}" for x, y in jamb_points(anchor_x, anchor_y, inward))
            + f'" fill="{colors.frame_fill}" stroke="{colors.frame_stroke}" stroke-width="1.5"/>'
        )
    svg.append(
        f'<path d="M {latch_inner_x:.2f} {latch_inner_y:.2f} '
        f'A {leaf_length:.2f} {leaf_length:.2f} 0 0 {sweep_flag} '
        f'{leaf_end_x:.2f} {leaf_end_y:.2f}" '
        f'fill="none" stroke="{colors.swing_stroke}" stroke-width="2"/>'
    )
    svg.append(
        '<polygon points="'
        + " ".join(f"{x:.2f},{y:.2f}" for x, y in leaf_points)
        + f'" fill="{colors.leaf_fill}" stroke="{colors.leaf_stroke}" stroke-width="2" '
        f'data-door-swing="{opening.swing_direction}" data-hinge-side="{opening.hinge_side}"/>'
    )
    return svg


def _format_distance(start: Point, end: Point) -> str:
    distance = hypot(end.x - start.x, end.y - start.y)
    return f"{distance:.2f} m"


def _lot_bounds(lot: LotArea) -> tuple[float, float, float, float]:
    return (
        min(lot.corner_a.x, lot.corner_b.x),
        min(lot.corner_a.y, lot.corner_b.y),
        max(lot.corner_a.x, lot.corner_b.x),
        max(lot.corner_a.y, lot.corner_b.y),
    )


def _lot_corners(lot: LotArea) -> list[Point]:
    min_x, min_y, max_x, max_y = _lot_bounds(lot)
    return [
        Point(x=min_x, y=min_y),
        Point(x=max_x, y=min_y),
        Point(x=max_x, y=max_y),
        Point(x=min_x, y=max_y),
    ]


def _dimension_display_points(start: Point, end: Point, offset_m: float) -> tuple[Point, Point]:
    if abs(start.y - end.y) < 1e-9:
        return (
            Point(x=start.x, y=start.y + offset_m),
            Point(x=end.x, y=end.y + offset_m),
        )
    return (
        Point(x=start.x + offset_m, y=start.y),
        Point(x=end.x + offset_m, y=end.y),
    )
