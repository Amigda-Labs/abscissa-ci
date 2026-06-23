from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import hypot, isclose

from abscissa_ci.cad.models import Point, WallSegment


POINT_KEY_PRECISION = 6


@dataclass(frozen=True)
class WallSolid:
    wall: WallSegment
    points: list[Point]


@dataclass(frozen=True)
class WallJoint:
    key: str
    point: Point
    wall_ids: list[str]
    wall_type: str
    thickness_mm: float
    points: list[Point]


def wall_solid_polygon(wall: WallSegment) -> WallSolid:
    """Return the filled wall body derived from a semantic centerline wall."""
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    length = hypot(dx, dy)
    if length <= 0:
        return WallSolid(wall=wall, points=[])

    thickness_m = (wall.thickness_mm or 100.0) / 1000.0
    half = thickness_m / 2.0
    normal_x = -dy / length
    normal_y = dx / length
    points = [
        Point(x=wall.start.x + normal_x * half, y=wall.start.y + normal_y * half),
        Point(x=wall.end.x + normal_x * half, y=wall.end.y + normal_y * half),
        Point(x=wall.end.x - normal_x * half, y=wall.end.y - normal_y * half),
        Point(x=wall.start.x - normal_x * half, y=wall.start.y - normal_y * half),
    ]
    return WallSolid(wall=wall, points=points)


def wall_joint_polygons(
    walls: list[WallSegment],
    suppressed_endpoint_keys: set[str] | None = None,
) -> list[WallJoint]:
    """Return square joint patches for shared orthogonal wall endpoints."""
    suppressed_endpoint_keys = suppressed_endpoint_keys or set()
    endpoint_groups: dict[str, list[tuple[WallSegment, Point]]] = defaultdict(list)
    for wall in walls:
        endpoint_groups[point_key(wall.start)].append((wall, wall.start))
        endpoint_groups[point_key(wall.end)].append((wall, wall.end))

    joints: list[WallJoint] = []
    for key, entries in endpoint_groups.items():
        if key in suppressed_endpoint_keys or len(entries) < 2:
            continue
        orientations = {_wall_orientation(wall) for wall, _point in entries}
        if len(orientations) < 2:
            continue

        point = entries[0][1]
        thickness_mm = max((wall.thickness_mm or 100.0) for wall, _point in entries)
        half = thickness_mm / 2000.0
        wall_type = "exterior" if any(wall.wall_type == "exterior" for wall, _point in entries) else "interior"
        joints.append(
            WallJoint(
                key=key,
                point=point,
                wall_ids=[wall.wall_id for wall, _point in entries],
                wall_type=wall_type,
                thickness_mm=thickness_mm,
                points=[
                    Point(x=point.x - half, y=point.y - half),
                    Point(x=point.x + half, y=point.y - half),
                    Point(x=point.x + half, y=point.y + half),
                    Point(x=point.x - half, y=point.y + half),
                ],
            )
        )
    return joints


def point_key(point: Point) -> str:
    x = _rounded_coord(point.x)
    y = _rounded_coord(point.y)
    return f"{x}:{y}"


def _rounded_coord(value: float) -> float:
    rounded = round(value, POINT_KEY_PRECISION)
    return 0.0 if isclose(rounded, 0.0, abs_tol=10**-POINT_KEY_PRECISION) else rounded


def _wall_orientation(wall: WallSegment) -> str:
    return "horizontal" if isclose(wall.start.y, wall.end.y, abs_tol=1e-9) else "vertical"
