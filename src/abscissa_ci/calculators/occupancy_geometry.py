from __future__ import annotations

import re

from abscissa_ci.models import EdgeDimensionLabel, PolygonDraft, PolygonPoint, clean_float
from abscissa_ci.calculators.polygon_geometry import shoelace_area


Point = tuple[float, float]

LABEL_TOLERANCE_M = 0.005
_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Directions as (dx, dy) unit steps in grid-index space.
_LEFT_TURN = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
_RIGHT_TURN = {value: key for key, value in _LEFT_TURN.items()}


def grid_to_polygons(
    x_stations: list[float],
    y_stations: list[float],
    occupied_rows: list[list[bool]],
) -> tuple[list[PolygonDraft], list[str]]:
    """Trace the boundary of the occupied-cell union into polygons.

    ``occupied_rows`` is listed top-to-bottom (drawing order); cell (row, col)
    covers x_stations[col]..[col+1] horizontally. Counter-clockwise loops are
    included floor areas; clockwise loops are holes and become subtract
    polygons. Returns (polygons, errors).
    """

    columns = len(x_stations) - 1
    rows = len(y_stations) - 1
    if len(occupied_rows) != rows or any(len(row) != columns for row in occupied_rows):
        return [], [
            f"Occupancy grid must be {rows} rows x {columns} columns to match the "
            "station grid."
        ]

    def occupied(band: int, col: int) -> bool:
        if not (0 <= band < rows and 0 <= col < columns):
            return False
        # band counts from the bottom; occupied_rows is listed from the top.
        return occupied_rows[rows - 1 - band][col]

    if not any(any(row) for row in occupied_rows):
        return [], ["Occupancy grid has no occupied cells."]

    # Directed boundary edges keeping the floor on the left: bottom edges run
    # east, right edges north, top edges west, left edges south. Shared edges
    # between occupied neighbors cancel.
    outgoing: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add_edge(start: tuple[int, int], end: tuple[int, int]) -> None:
        outgoing.setdefault(start, []).append(end)

    for band in range(rows):
        for col in range(columns):
            if not occupied(band, col):
                continue
            if not occupied(band - 1, col):
                add_edge((col, band), (col + 1, band))
            if not occupied(band, col + 1):
                add_edge((col + 1, band), (col + 1, band + 1))
            if not occupied(band + 1, col):
                add_edge((col + 1, band + 1), (col, band + 1))
            if not occupied(band, col - 1):
                add_edge((col, band + 1), (col, band))

    def pick_next(current: tuple[int, int], incoming: tuple[int, int]) -> tuple[int, int]:
        candidates = outgoing[current]
        if len(candidates) == 1:
            return candidates.pop()
        # Diagonal cell contact: prefer the left turn so the loop hugs its own
        # region instead of crossing into the diagonal neighbor's boundary.
        preferred = _LEFT_TURN[incoming]
        for index, candidate in enumerate(candidates):
            step = (candidate[0] - current[0], candidate[1] - current[1])
            if step == preferred:
                return candidates.pop(index)
        return candidates.pop()

    loops: list[list[tuple[int, int]]] = []
    while any(outgoing.values()):
        start = next(vertex for vertex, ends in outgoing.items() if ends)
        end = outgoing[start].pop()
        loop = [start]
        incoming = (end[0] - start[0], end[1] - start[1])
        current = end
        while current != start:
            loop.append(current)
            following = pick_next(current, incoming)
            incoming = (following[0] - current[0], following[1] - current[1])
            current = following
        loops.append(loop)

    polygons: list[PolygonDraft] = []
    add_count = 0
    void_count = 0
    for loop in loops:
        points = [
            (x_stations[col], y_stations[band]) for col, band in loop
        ]
        # Drop vertices in the middle of straight runs.
        merged: list[Point] = []
        count = len(points)
        for index in range(count):
            previous = points[(index - 1) % count]
            current_point = points[index]
            following = points[(index + 1) % count]
            incoming_dir = (
                current_point[0] - previous[0],
                current_point[1] - previous[1],
            )
            outgoing_dir = (
                following[0] - current_point[0],
                following[1] - current_point[1],
            )
            cross = incoming_dir[0] * outgoing_dir[1] - incoming_dir[1] * outgoing_dir[0]
            if abs(cross) > 1e-12:
                merged.append(current_point)

        is_hole = shoelace_area(merged) < 0
        if is_hole:
            void_count += 1
            name = f"Void {void_count}"
        else:
            add_count += 1
            name = f"Floor area {add_count}"
        polygons.append(
            PolygonDraft(
                name=name,
                operation="subtract" if is_hole else "add",
                points=[
                    PolygonPoint(x_m=clean_float(x), y_m=clean_float(y))
                    for x, y in merged
                ],
            )
        )

    # The shoelace totals must reproduce the summed cell areas exactly.
    cell_area = sum(
        (x_stations[col + 1] - x_stations[col]) * (y_stations[band + 1] - y_stations[band])
        for band in range(rows)
        for col in range(columns)
        if occupied(band, col)
    )
    # Holes were traced clockwise, so their shoelace areas are negative and
    # the raw signed sum equals the net floor area.
    signed_total = sum(
        shoelace_area([(p.x_m, p.y_m) for p in polygon.points]) for polygon in polygons
    )
    if abs(signed_total - cell_area) > 1e-6:
        return polygons, [
            "Internal occupancy tracing error: traced area "
            f"{signed_total:g} sqm does not match summed cell area {cell_area:g} sqm."
        ]

    return polygons, []


def attach_inventory_labels(polygons: list[PolygonDraft], inventory: list[str]) -> None:
    """Greedily attach each printed dimension to an unlabeled edge of equal
    length. Entries with no matching edge are left for the coverage check,
    which accepts overall bounding dimensions and flags everything else."""

    edges: list[tuple[PolygonDraft, int, float]] = []
    for polygon in polygons:
        points = [(p.x_m, p.y_m) for p in polygon.points]
        count = len(points)
        for index in range(count):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % count]
            edges.append((polygon, index, abs(x2 - x1) + abs(y2 - y1)))

    used: set[int] = set()
    for entry in inventory:
        match = _NUMBER.search(entry)
        if match is None:
            continue
        value = float(match.group())
        for position, (polygon, edge_index, length) in enumerate(edges):
            if position in used or abs(length - value) > LABEL_TOLERANCE_M:
                continue
            polygon.edge_labels.append(
                EdgeDimensionLabel(
                    edge_index=edge_index, length_m=value, source_text=entry
                )
            )
            used.add(position)
            break
