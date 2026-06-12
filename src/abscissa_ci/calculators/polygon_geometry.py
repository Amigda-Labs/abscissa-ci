from __future__ import annotations

import re
from itertools import combinations
from math import hypot

from abscissa_ci.models import PolygonAreaResult, PolygonDraft, PolygonPoint, clean_float


Point = tuple[float, float]

# Coordinates come from clean_float-style inputs with at most 4 decimal places,
# so anything below this is float noise rather than real geometry.
GEOMETRY_EPS = 1e-9
AXIS_ALIGNMENT_TOLERANCE_M = 1e-6
# Drawings label dimensions to 2 decimal places; allow half of the last digit.
LABEL_TOLERANCE_M = 0.005
MIN_POLYGON_AREA_SQM = 1e-6


def _as_xy(points: list[PolygonPoint]) -> list[Point]:
    return [(point.x_m, point.y_m) for point in points]


def _edges(points: list[Point]) -> list[tuple[Point, Point]]:
    return [(points[index], points[(index + 1) % len(points)]) for index in range(len(points))]


def shoelace_area(points: list[Point]) -> float:
    """Signed area of a simple polygon ring; positive when counter-clockwise."""

    total = 0.0
    for (x1, y1), (x2, y2) in _edges(points):
        total += x1 * y2 - x2 * y1
    return total / 2


def ring_perimeter(points: list[Point]) -> float:
    return sum(hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in _edges(points))


def _cross(origin: Point, a: Point, b: Point) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def _point_on_segment(point: Point, a: Point, b: Point) -> bool:
    if abs(_cross(a, b, point)) > GEOMETRY_EPS:
        return False
    return (
        min(a[0], b[0]) - GEOMETRY_EPS <= point[0] <= max(a[0], b[0]) + GEOMETRY_EPS
        and min(a[1], b[1]) - GEOMETRY_EPS <= point[1] <= max(a[1], b[1]) + GEOMETRY_EPS
    )


def _segments_properly_cross(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """True only when the segment interiors cross; shared endpoints and
    collinear touching do not count."""

    d1 = _cross(b1, b2, a1)
    d2 = _cross(b1, b2, a2)
    d3 = _cross(a1, a2, b1)
    d4 = _cross(a1, a2, b2)
    return (
        ((d1 > GEOMETRY_EPS and d2 < -GEOMETRY_EPS) or (d1 < -GEOMETRY_EPS and d2 > GEOMETRY_EPS))
        and ((d3 > GEOMETRY_EPS and d4 < -GEOMETRY_EPS) or (d3 < -GEOMETRY_EPS and d4 > GEOMETRY_EPS))
    )


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """True for any contact, including endpoint touches and collinear overlap."""

    if _segments_properly_cross(a1, a2, b1, b2):
        return True
    return (
        _point_on_segment(a1, b1, b2)
        or _point_on_segment(a2, b1, b2)
        or _point_on_segment(b1, a1, a2)
        or _point_on_segment(b2, a1, a2)
    )


def _self_intersects(points: list[Point]) -> bool:
    edges = _edges(points)
    count = len(edges)
    for i, j in combinations(range(count), 2):
        adjacent = j == i + 1 or (i == 0 and j == count - 1)
        if adjacent:
            continue
        if _segments_intersect(*edges[i], *edges[j]):
            return True
    return False


def point_on_boundary(point: Point, ring: list[Point]) -> bool:
    return any(_point_on_segment(point, a, b) for a, b in _edges(ring))


def point_in_polygon(point: Point, ring: list[Point]) -> bool:
    """Even-odd containment test, treating the boundary as inside."""

    if point_on_boundary(point, ring):
        return True
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in _edges(ring):
        if (y1 > y) != (y2 > y):
            x_crossing = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x_crossing > x:
                inside = not inside
    return inside


def point_strictly_inside(point: Point, ring: list[Point]) -> bool:
    return not point_on_boundary(point, ring) and point_in_polygon(point, ring)


def _ring_centroid(points: list[Point]) -> Point:
    area = shoelace_area(points)
    if abs(area) < MIN_POLYGON_AREA_SQM:
        return (
            sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points),
        )
    cx = 0.0
    cy = 0.0
    for (x1, y1), (x2, y2) in _edges(points):
        factor = x1 * y2 - x2 * y1
        cx += (x1 + x2) * factor
        cy += (y1 + y2) * factor
    return (cx / (6 * area), cy / (6 * area))


def validate_polygon(polygon: PolygonDraft) -> tuple[list[str], list[str]]:
    """Per-polygon checks. Errors gate computation; warnings flag review items."""

    errors: list[str] = []
    warnings: list[str] = []
    points = _as_xy(polygon.points)
    edges = _edges(points)
    edge_count = len(edges)

    for index, ((x1, y1), (x2, y2)) in enumerate(edges):
        if hypot(x2 - x1, y2 - y1) < GEOMETRY_EPS:
            errors.append(f"{polygon.name}: edge {index} has zero length.")

    if not errors and _self_intersects(points):
        errors.append(f"{polygon.name}: boundary intersects itself; the ring must be a simple polygon.")

    if not errors and abs(shoelace_area(points)) < MIN_POLYGON_AREA_SQM:
        errors.append(f"{polygon.name}: polygon area is zero; the points may be collinear.")

    non_axis_edges = [
        index
        for index, ((x1, y1), (x2, y2)) in enumerate(edges)
        if abs(x2 - x1) > AXIS_ALIGNMENT_TOLERANCE_M and abs(y2 - y1) > AXIS_ALIGNMENT_TOLERANCE_M
    ]
    if non_axis_edges:
        warnings.append(
            f"{polygon.name}: edges {non_axis_edges} are not axis-aligned; "
            "expected a rectilinear footprint for this checkpoint."
        )

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    span_width = max(xs) - min(xs)
    span_height = max(ys) - min(ys)
    if polygon.bounding_width_m is not None and abs(span_width - polygon.bounding_width_m) > LABEL_TOLERANCE_M:
        errors.append(
            f"{polygon.name}: vertices span {span_width:g}m wide but the plan's overall "
            f"width is labeled {polygon.bounding_width_m:g}m."
        )
    if polygon.bounding_height_m is not None and abs(span_height - polygon.bounding_height_m) > LABEL_TOLERANCE_M:
        errors.append(
            f"{polygon.name}: vertices span {span_height:g}m tall but the plan's overall "
            f"height is labeled {polygon.bounding_height_m:g}m."
        )

    for label in polygon.edge_labels:
        if label.edge_index >= edge_count:
            errors.append(
                f"{polygon.name}: edge label index {label.edge_index} is out of range "
                f"for {edge_count} edges."
            )
            continue
        (x1, y1), (x2, y2) = edges[label.edge_index]
        measured = hypot(x2 - x1, y2 - y1)
        if abs(measured - label.length_m) > LABEL_TOLERANCE_M:
            source = f" (label source: {label.source_text})" if label.source_text else ""
            errors.append(
                f"{polygon.name}: edge {label.edge_index} measures {measured:g}m from its "
                f"vertices but is labeled {label.length_m:g}m{source}."
            )

    return errors, warnings


def _rings_overlap(ring_a: list[Point], ring_b: list[Point]) -> bool:
    for edge_a in _edges(ring_a):
        for edge_b in _edges(ring_b):
            if _segments_properly_cross(*edge_a, *edge_b):
                return True
    if any(point_strictly_inside(vertex, ring_b) for vertex in ring_a):
        return True
    if any(point_strictly_inside(vertex, ring_a) for vertex in ring_b):
        return True
    # Catches full containment and identical rings, where no vertex of either
    # ring lies strictly inside the other.
    return point_strictly_inside(_ring_centroid(ring_a), ring_b) or point_strictly_inside(
        _ring_centroid(ring_b), ring_a
    )


def _ring_contains(outer: list[Point], inner: list[Point]) -> bool:
    if any(not point_in_polygon(vertex, outer) for vertex in inner):
        return False
    for inner_edge in _edges(inner):
        for outer_edge in _edges(outer):
            if _segments_properly_cross(*inner_edge, *outer_edge):
                return False
    return True


def validate_polygon_set(polygons: list[PolygonDraft]) -> list[str]:
    """Cross-polygon checks over individually valid polygons.

    Sharing a boundary edge is allowed (decomposed footprints); overlapping
    interiors are not, because signed-area summation would double-count them.
    """

    errors: list[str] = []
    adds = [(polygon, _as_xy(polygon.points)) for polygon in polygons if polygon.operation == "add"]
    subtracts = [
        (polygon, _as_xy(polygon.points)) for polygon in polygons if polygon.operation == "subtract"
    ]

    for (draft_a, ring_a), (draft_b, ring_b) in combinations(adds, 2):
        if _rings_overlap(ring_a, ring_b):
            errors.append(
                f"Included floor polygons '{draft_a.name}' and '{draft_b.name}' overlap, "
                "so their areas would be double-counted."
            )

    for (draft_a, ring_a), (draft_b, ring_b) in combinations(subtracts, 2):
        if _rings_overlap(ring_a, ring_b):
            errors.append(
                f"Void polygons '{draft_a.name}' and '{draft_b.name}' overlap, "
                "so their areas would be double-subtracted."
            )

    for draft, ring in subtracts:
        if not any(_ring_contains(add_ring, ring) for _, add_ring in adds):
            errors.append(
                f"Void polygon '{draft.name}' is not contained inside any included floor polygon."
            )

    return errors


def validate_dimension_coverage(
    dimension_inventory: list[str],
    polygons: list[PolygonDraft],
) -> list[str]:
    """Every printed dimension must be attached to an edge or be an overall dim.

    A wrong-but-self-consistent extraction typically drops the printed labels
    that do not fit its invented shape; requiring full coverage catches it.
    """

    if not dimension_inventory or not polygons:
        return []

    unused_label_texts: list[str] = []
    unused_label_values: list[float] = []
    bounding_values: list[float] = []
    for polygon in polygons:
        for label in polygon.edge_labels:
            unused_label_texts.append((label.source_text or "").strip())
            unused_label_values.append(label.length_m)
        if polygon.bounding_width_m is not None:
            bounding_values.append(polygon.bounding_width_m)
        if polygon.bounding_height_m is not None:
            bounding_values.append(polygon.bounding_height_m)

    errors: list[str] = []
    for entry in dimension_inventory:
        text = entry.strip()
        if text in unused_label_texts:
            index = unused_label_texts.index(text)
            unused_label_texts.pop(index)
            unused_label_values.pop(index)
            continue

        match = re.search(r"\d+(?:\.\d+)?", text)
        if match is None:
            continue
        value = float(match.group())

        value_index = next(
            (i for i, used in enumerate(unused_label_values) if abs(used - value) <= LABEL_TOLERANCE_M),
            None,
        )
        if value_index is not None:
            unused_label_texts.pop(value_index)
            unused_label_values.pop(value_index)
            continue

        bounding_index = next(
            (i for i, bound in enumerate(bounding_values) if abs(bound - value) <= LABEL_TOLERANCE_M),
            None,
        )
        if bounding_index is not None:
            bounding_values.pop(bounding_index)
            continue

        errors.append(
            f"Printed dimension '{text}' is not assigned to any edge or overall dimension; "
            "the extracted shape does not account for it."
        )
    return errors


def compute_polygon_area(polygon: PolygonDraft) -> PolygonAreaResult:
    errors, validation_warnings = validate_polygon(polygon)
    warnings = [*polygon.warnings, *validation_warnings]
    point_count = len(polygon.points)

    if errors:
        return PolygonAreaResult(
            name=polygon.name,
            operation=polygon.operation,
            is_valid=False,
            point_count=point_count,
            calculation="not computed: polygon failed validation",
            errors=errors,
            warnings=warnings,
            source_text=polygon.source_text,
            confidence=polygon.confidence,
        )

    points = _as_xy(polygon.points)
    area_sqm = clean_float(abs(shoelace_area(points)))
    signed_area_sqm = area_sqm if polygon.operation == "add" else -area_sqm
    return PolygonAreaResult(
        name=polygon.name,
        operation=polygon.operation,
        is_valid=True,
        point_count=point_count,
        area_sqm=area_sqm,
        signed_area_sqm=signed_area_sqm,
        perimeter_m=clean_float(ring_perimeter(points)),
        calculation=f"{polygon.operation} shoelace({point_count} vertices) = {area_sqm:g} sqm",
        errors=[],
        warnings=warnings,
        source_text=polygon.source_text,
        confidence=polygon.confidence,
    )


def compute_polygon_areas(polygons: list[PolygonDraft]) -> list[PolygonAreaResult]:
    return [compute_polygon_area(polygon) for polygon in polygons]


def compute_total_polygon_area(zones: list[PolygonAreaResult]) -> float:
    return clean_float(sum(zone.signed_area_sqm or 0.0 for zone in zones))
