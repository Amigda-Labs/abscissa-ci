from __future__ import annotations

from abscissa_ci.models import (
    EdgeDimensionLabel,
    PolygonDraft,
    PolygonPoint,
    PolygonTraverse,
    clean_float,
)


Point = tuple[float, float]

DIRECTION_VECTORS: dict[str, Point] = {
    "E": (1.0, 0.0),
    "N": (0.0, 1.0),
    "W": (-1.0, 0.0),
    "S": (0.0, -1.0),
}
DIRECTION_NAMES = {"E": "east", "N": "north", "W": "west", "S": "south"}
# Drawings label dimensions to 2 decimal places; allow half of the last digit.
CLOSURE_TOLERANCE_M = 0.005


def traverse_closure_errors(traverse: PolygonTraverse) -> list[str]:
    """Per-axis closure checks, reported the way a surveyor states misclosure.

    A closed rectilinear traverse must satisfy sum(east) == sum(west) and
    sum(north) == sum(south); a violation localizes the error to one axis.
    """

    totals = {direction: 0.0 for direction in DIRECTION_VECTORS}
    for move in traverse.moves:
        totals[move.direction] += move.length_m

    errors: list[str] = []
    misclose_x = totals["E"] - totals["W"]
    if abs(misclose_x) > CLOSURE_TOLERANCE_M:
        errors.append(
            f"{traverse.name}: traverse does not close east-west: east moves total "
            f"{totals['E']:g}m but west moves total {totals['W']:g}m "
            f"(misclosure {misclose_x:+g}m)."
        )
    misclose_y = totals["N"] - totals["S"]
    if abs(misclose_y) > CLOSURE_TOLERANCE_M:
        errors.append(
            f"{traverse.name}: traverse does not close north-south: north moves total "
            f"{totals['N']:g}m but south moves total {totals['S']:g}m "
            f"(misclosure {misclose_y:+g}m)."
        )
    return errors


def traverse_points(traverse: PolygonTraverse) -> list[Point]:
    """Vertex before each move, walking from (0, 0); vertex i starts move i."""

    x = y = 0.0
    points: list[Point] = []
    for move in traverse.moves:
        points.append((x, y))
        dx, dy = DIRECTION_VECTORS[move.direction]
        x += dx * move.length_m
        y += dy * move.length_m
    return points


def traverse_to_polygon(traverse: PolygonTraverse) -> tuple[PolygonDraft | None, list[str]]:
    """Deterministically derive a polygon from a closed traverse.

    Returns (polygon, []) on success or (None, errors) when the traverse does
    not close; an open traverse has no trustworthy shape to draw.
    """

    errors = traverse_closure_errors(traverse)
    if errors:
        return None, errors

    points = traverse_points(traverse)
    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    shifted = [
        PolygonPoint(x_m=clean_float(x - min_x), y_m=clean_float(y - min_y))
        for x, y in points
    ]

    # Move i runs from vertex i to vertex i+1, so it is edge i of the ring.
    edge_labels = [
        EdgeDimensionLabel(
            edge_index=index, length_m=move.length_m, source_text=move.source_text
        )
        for index, move in enumerate(traverse.moves)
        if move.source_text
    ]

    polygon = PolygonDraft(
        name=traverse.name,
        operation=traverse.operation,
        points=shifted,
        edge_labels=edge_labels,
        bounding_width_m=traverse.bounding_width_m,
        bounding_height_m=traverse.bounding_height_m,
        source_text=traverse.source_text,
        confidence=traverse.confidence,
        warnings=list(traverse.warnings),
    )
    return polygon, []


def traverse_derivation_notes(traverse: PolygonTraverse) -> list[str]:
    """Human-readable record of every unprinted length the model derived."""

    return [
        f"{traverse.name}: move {index} ({DIRECTION_NAMES[move.direction]} "
        f"{move.length_m:g}m) was not printed; derived from {move.derivation}."
        for index, move in enumerate(traverse.moves)
        if not move.source_text and move.derivation
    ]
