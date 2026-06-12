from __future__ import annotations

import re

from abscissa_ci.models import DimensionChain, DimensionSurvey, PolygonDraft


# Drawings label dimensions to 2 decimal places; allow half of the last digit.
STATION_TOLERANCE_M = 0.005
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _parse_length(text: str) -> float | None:
    match = _NUMBER.search(text)
    return float(match.group()) if match else None


def _has_interior_stations(stations: list[float] | None, overall: float | None) -> bool:
    """True when some station splits the extent; {0, overall} alone does not."""

    if not stations:
        return False
    if overall is None:
        return True
    return any(
        STATION_TOLERANCE_M < station < overall - STATION_TOLERANCE_M
        for station in stations
    )


def _axis_has_segment_labels(
    survey: DimensionSurvey, orientation: str, overall: float | None
) -> bool:
    for entry in survey.entries:
        if entry.orientation != orientation:
            continue
        value = _parse_length(entry.source_text)
        if value is None:
            continue
        if overall is not None and abs(value - overall) <= STATION_TOLERANCE_M:
            continue
        return True
    return False


def validate_survey(survey: DimensionSurvey) -> list[str]:
    """Deterministic consistency checks on the perception pass itself.

    Survey mistakes poison every later stage, so they are caught and fed back
    before any shape reasoning happens.
    """

    errors: list[str] = []
    if survey.bounding_width_m is None:
        errors.append("Survey is missing bounding_width_m (the overall printed width).")
    if survey.bounding_height_m is None:
        errors.append("Survey is missing bounding_height_m (the overall printed height).")

    for index, chain in enumerate(survey.chains, start=1):
        overall = (
            survey.bounding_width_m
            if chain.orientation == "horizontal"
            else survey.bounding_height_m
        )
        if not chain.spans_full_extent or overall is None:
            continue
        values = [
            _parse_length(segment.source_text) if segment.source_text else None
            for segment in chain.segments
        ]
        known = sum(value for value in values if value is not None)
        gap_count = values.count(None)
        if gap_count == 0 and abs(known - overall) > STATION_TOLERANCE_M:
            errors.append(
                f"Chain {index} ({chain.orientation}) sums to {known:g}m but the "
                f"overall {chain.orientation} extent is {overall:g}m; re-read its "
                "segments, their order, or its spans_full_extent flag."
            )
        elif gap_count >= 1 and known > overall - STATION_TOLERANCE_M:
            errors.append(
                f"Chain {index} ({chain.orientation}) has labeled segments summing "
                f"to {known:g}m plus {gap_count} unlabeled gap(s), which cannot fit "
                f"the overall {overall:g}m extent."
            )

    # Every surveyed label must be an overall dimension or sit in exactly one
    # chain slot, and chains may only contain surveyed labels. This catches
    # double-listed entries and orphaned labels that never made it into a lane.
    unmatched_chain_texts = [
        segment.source_text.strip()
        for chain in survey.chains
        for segment in chain.segments
        if segment.source_text
    ]
    unmatched_bounding = [
        value
        for value in (survey.bounding_width_m, survey.bounding_height_m)
        if value is not None
    ]
    for entry in survey.entries:
        text = entry.source_text.strip()
        if text in unmatched_chain_texts:
            unmatched_chain_texts.remove(text)
            continue
        value = _parse_length(text)
        bounding_index = next(
            (
                position
                for position, bound in enumerate(unmatched_bounding)
                if value is not None and abs(bound - value) <= STATION_TOLERANCE_M
            ),
            None,
        )
        if bounding_index is not None:
            unmatched_bounding.pop(bounding_index)
            continue
        errors.append(
            f"Surveyed label '{text}' is not an overall dimension and is not part "
            "of any dimension chain; place every segment label in its lane's chain."
        )
    for leftover in unmatched_chain_texts:
        errors.append(
            f"Chain segment '{leftover}' does not match any surveyed entry; chains "
            "may only contain labels that are also listed in entries."
        )

    # Segment labels imply interior corners; the chains must pin them to
    # absolute positions, or the station grid stays unusable.
    x_stations, y_stations = survey_stations(survey)
    if _axis_has_segment_labels(
        survey, "horizontal", survey.bounding_width_m
    ) and not _has_interior_stations(x_stations, survey.bounding_width_m):
        errors.append(
            "Horizontal segment labels exist but no horizontal chain pins them to "
            "the outline: for each horizontal lane, check whether its first and "
            "last extension lines align with the footprint's leftmost or rightmost "
            "points and set starts_at_outline_edge / ends_at_outline_edge."
        )
    if _axis_has_segment_labels(
        survey, "vertical", survey.bounding_height_m
    ) and not _has_interior_stations(y_stations, survey.bounding_height_m):
        errors.append(
            "Vertical segment labels exist but no vertical chain pins them to the "
            "outline: for each vertical lane, check whether its first and last "
            "extension lines align with the footprint's topmost or bottommost "
            "points and set starts_at_outline_edge / ends_at_outline_edge."
        )
    return errors


def _chain_values(chain: DimensionChain) -> list[float | None]:
    return [
        _parse_length(segment.source_text) if segment.source_text else None
        for segment in chain.segments
    ]


def chain_stations(chain: DimensionChain, overall: float | None) -> list[float] | None:
    """Absolute extension-line positions implied by one chain, 0 at the axis min.

    A chain only yields absolute stations where it is anchored to the
    outline's extremes. Fully anchored chains fill a single unlabeled gap
    with the complement of the printed segments; chains anchored at one end
    contribute the prefix (or suffix) run up to their first gap. Vertical
    chains are listed top-to-bottom, so their distances count down from the
    overall extent.
    """

    if overall is None:
        return None
    starts = chain.starts_at_outline_edge or chain.spans_full_extent
    ends = chain.ends_at_outline_edge or chain.spans_full_extent
    values = _chain_values(chain)
    if any(value is not None and value <= 0 for value in values):
        return None

    if starts and ends:
        return _stations_from_values(values, overall, chain.orientation)
    if starts:
        positions = _anchored_run(values, overall)
    elif ends:
        run = _anchored_run(list(reversed(values)), overall)
        positions = None if run is None else [overall - position for position in run]
    else:
        return None
    if positions is None:
        return None
    return _to_axis_coordinates(positions, overall, chain.orientation)


def _anchored_run(values: list[float | None], overall: float) -> list[float] | None:
    """Listing-space positions of the run anchored at the chain's start."""

    positions = [0.0]
    for value in values:
        if value is None:
            break
        positions.append(positions[-1] + value)
    if positions[-1] > overall + STATION_TOLERANCE_M:
        return None
    return positions


def _to_axis_coordinates(
    positions: list[float], overall: float, orientation: str
) -> list[float]:
    if orientation == "vertical":
        positions = [overall - position for position in positions]
    return sorted(set(positions))


def promoted_chain_stations(chain: DimensionChain, overall: float | None) -> list[float] | None:
    """Stations from a lane the model did not mark as full extent.

    Used only when no anchored chain exists on the axis: a lane with at least
    two segments whose labels plus at most one gap can fill the overall extent
    is assumed to span it. A wrong promotion yields a grid the printed labels
    cannot all live on, which the coverage check blocks downstream.
    """

    if overall is None or len(chain.segments) < 2:
        return None
    values = _chain_values(chain)
    if values.count(None) > 1:
        return None
    return _stations_from_values(values, overall, chain.orientation)


def _stations_from_values(
    values: list[float | None], overall: float, orientation: str
) -> list[float] | None:
    if any(value is not None and value <= 0 for value in values):
        return None
    known = sum(value for value in values if value is not None)
    gap_count = values.count(None)

    if gap_count == 0:
        if abs(known - overall) > STATION_TOLERANCE_M:
            # The chain does not sum to the overall extent; misread digits
            # would poison the grid, so contribute nothing.
            return None
        positions = [0.0]
        for value in values:
            positions.append(positions[-1] + value)
    elif gap_count == 1:
        gap = overall - known
        if gap <= STATION_TOLERANCE_M:
            return None
        positions = [0.0]
        for value in values:
            positions.append(positions[-1] + (gap if value is None else value))
    else:
        positions = [0.0, overall]
        running = 0.0
        for value in values:
            if value is None:
                break
            running += value
            positions.append(running)
        running = overall
        for value in reversed(values):
            if value is None:
                break
            running -= value
            positions.append(running)

    return _to_axis_coordinates(positions, overall, orientation)


def survey_stations(survey: DimensionSurvey) -> tuple[list[float] | None, list[float] | None]:
    """Station grid per axis, or None for an axis with no usable chain.

    Anchored (full-extent) chains are authoritative; when an axis has none,
    promotable partial lanes fill in.
    """

    x_stations: set[float] = set()
    y_stations: set[float] = set()
    for chain in survey.chains:
        if chain.orientation == "horizontal":
            stations = chain_stations(chain, survey.bounding_width_m)
            if stations is not None:
                x_stations.update(stations)
        else:
            stations = chain_stations(chain, survey.bounding_height_m)
            if stations is not None:
                y_stations.update(stations)

    def unanchored(chain: DimensionChain) -> bool:
        return not (
            chain.spans_full_extent
            or chain.starts_at_outline_edge
            or chain.ends_at_outline_edge
        )

    def has_interior_stations(stations: set[float], overall: float | None) -> bool:
        # The overall dimension alone yields only {0, overall}; an axis is
        # really determined only when some station splits the extent.
        if overall is None:
            return bool(stations)
        return any(
            STATION_TOLERANCE_M < station < overall - STATION_TOLERANCE_M
            for station in stations
        )

    if not has_interior_stations(x_stations, survey.bounding_width_m):
        for chain in survey.chains:
            if chain.orientation != "horizontal" or not unanchored(chain):
                continue
            stations = promoted_chain_stations(chain, survey.bounding_width_m)
            if stations is not None:
                x_stations.update(stations)
    if not has_interior_stations(y_stations, survey.bounding_height_m):
        for chain in survey.chains:
            if chain.orientation != "vertical" or not unanchored(chain):
                continue
            stations = promoted_chain_stations(chain, survey.bounding_height_m)
            if stations is not None:
                y_stations.update(stations)

    return (
        sorted(x_stations) if x_stations else None,
        sorted(y_stations) if y_stations else None,
    )


def filter_interval_matched_entries(
    inventory: list[str],
    x_stations: list[float],
    y_stations: list[float],
) -> list[str]:
    """Drop inventory entries that measure an adjacent-station interval.

    On the occupancy path a printed dimension may position a feature (a void
    margin, a recess offset) rather than measure a boundary edge; the station
    grid itself accounts for it. Returns the entries still unexplained.
    """

    intervals = {
        second - first
        for stations in (x_stations, y_stations)
        for first, second in zip(stations, stations[1:])
    }
    remaining: list[str] = []
    for entry in inventory:
        match = _NUMBER.search(entry)
        value = float(match.group()) if match else None
        if value is not None and any(
            abs(value - interval) <= STATION_TOLERANCE_M for interval in intervals
        ):
            continue
        remaining.append(entry)
    return remaining


def validate_station_usage(
    polygons: list[PolygonDraft],
    x_stations: list[float] | None,
    y_stations: list[float] | None,
) -> list[str]:
    """Every interior station must be used by some polygon corner.

    Stations come from extension lines that mark footprint features; a traced
    shape with no corner on an interior station ignores a printed feature.
    Void corners count - interior chains often position voids.
    """

    xs = {point.x_m for polygon in polygons for point in polygon.points}
    ys = {point.y_m for polygon in polygons for point in polygon.points}
    errors: list[str] = []
    if x_stations:
        for station in x_stations[1:-1]:
            if all(abs(x - station) > STATION_TOLERANCE_M for x in xs):
                errors.append(
                    f"No corner of the traced footprint lies on x station "
                    f"{station:g}m implied by the dimension chains; the drawing "
                    "marks a feature there that the shape ignores."
                )
    if y_stations:
        for station in y_stations[1:-1]:
            if all(abs(y - station) > STATION_TOLERANCE_M for y in ys):
                errors.append(
                    f"No corner of the traced footprint lies on y station "
                    f"{station:g}m implied by the dimension chains; the drawing "
                    "marks a feature there that the shape ignores."
                )
    return errors


def _off_station(value: float, stations: list[float]) -> bool:
    return all(abs(value - station) > STATION_TOLERANCE_M for station in stations)


def validate_station_alignment(
    polygons: list[PolygonDraft],
    survey: DimensionSurvey,
) -> list[str]:
    """Every floor corner must land on the printed dimension station grid.

    Closure, bounding, and label coverage can all be satisfied by a wrong
    shape that rearranges the same printed segments; corners off the
    extension-line grid expose it. Voids are skipped because their position
    is often assumed rather than printed.
    """

    x_stations, y_stations = survey_stations(survey)
    errors: list[str] = []
    for polygon in polygons:
        if polygon.operation != "add":
            continue
        bad_x = sorted(
            {point.x_m for point in polygon.points if x_stations and _off_station(point.x_m, x_stations)}
        )
        bad_y = sorted(
            {point.y_m for point in polygon.points if y_stations and _off_station(point.y_m, y_stations)}
        )
        if bad_x:
            listed = ", ".join(f"{value:g}" for value in bad_x)
            grid = ", ".join(f"{value:g}" for value in x_stations)
            errors.append(
                f"{polygon.name}: corner x position(s) {listed}m do not align with the "
                f"printed dimension stations on the x axis ({grid}m)."
            )
        if bad_y:
            listed = ", ".join(f"{value:g}" for value in bad_y)
            grid = ", ".join(f"{value:g}" for value in y_stations)
            errors.append(
                f"{polygon.name}: corner y position(s) {listed}m do not align with the "
                f"printed dimension stations on the y axis ({grid}m)."
            )
    return errors
