from __future__ import annotations

from collections import Counter

from abscissa_ci.area.models import (
    AreaIssue,
    AreaReport,
    ComponentAreaResult,
    DimensionConsistencyCheck,
    MeasurementBasis,
    PlanAreaExtraction,
    RectangularAreaComponent,
    RoomAreaDraft,
    RoomAreaResult,
)


LENGTH_SUM_TOLERANCE_M = 0.05
LENGTH_SUM_TOLERANCE_PERCENT = 0.01
AREA_LABEL_WARNING_PERCENT = 0.03
AREA_LABEL_ERROR_PERCENT = 0.05
AREA_LABEL_ABSOLUTE_TOLERANCE_SQM = 0.25
MIN_REASONABLE_ROOM_AREA_SQM = 0.25
MAX_REASONABLE_ROOM_AREA_SQM = 500.0
MAX_REASONABLE_ROOM_DIMENSION_M = 100.0
MIN_REASONABLE_ROOM_DIMENSION_M = 0.15
MAX_ASPECT_RATIO_REVIEW = 20.0


def solve_area_takeoff(
    extraction: PlanAreaExtraction,
    *,
    requested_measurement_basis: MeasurementBasis = "net_internal_room_area",
    source_image_path: str | None = None,
) -> AreaReport:
    issues: list[AreaIssue] = []
    room_results: list[RoomAreaResult] = []

    issues.extend(_check_duplicate_room_names(extraction.rooms))

    for check in extraction.consistency_checks:
        issues.extend(_validate_dimension_consistency(check))

    for room in extraction.rooms:
        result, room_issues = _solve_room(room, requested_measurement_basis)
        room_results.append(result)
        issues.extend(room_issues)

    if not extraction.rooms:
        issues.append(
            AreaIssue(
                severity="error",
                code="no_rooms_detected",
                message="No rooms or included floor areas were extracted from the plan.",
            )
        )

    total_area = _sum_known_room_areas(room_results)
    questions = _build_questions(extraction, issues)
    can_compute = not any(issue.severity == "error" for issue in issues)

    return AreaReport(
        can_compute=can_compute,
        project_name=extraction.project_name,
        source_image_path=source_image_path,
        requested_measurement_basis=requested_measurement_basis,
        total_area_sqm=round(total_area, 4) if can_compute and total_area is not None else None,
        rooms=room_results,
        issues=issues,
        questions=questions,
        assumptions=extraction.assumptions,
        warnings=extraction.warnings,
    )


def _solve_room(
    room: RoomAreaDraft,
    requested_measurement_basis: MeasurementBasis,
) -> tuple[RoomAreaResult, list[AreaIssue]]:
    issues: list[AreaIssue] = []
    component_results: list[ComponentAreaResult] = []
    add_area = 0.0
    subtract_area = 0.0

    if not room.components and room.labeled_area is None:
        issues.append(
            AreaIssue(
                severity="error",
                code="room_has_no_area_basis",
                message=f"{room.name} has no rectangular components or labeled area.",
                room_id=room.room_id,
            )
        )

    if requested_measurement_basis == "net_internal_room_area":
        if room.boundary_basis in {"wall_centerline", "outside_face_of_walls", "mixed"}:
            issues.append(
                AreaIssue(
                    severity="warning",
                    code="wall_basis_not_net_internal",
                    message=(
                        f"{room.name} appears to use {room.boundary_basis}; net internal area "
                        "should use the inside face of walls."
                    ),
                    room_id=room.room_id,
                )
            )
        elif room.boundary_basis == "unknown":
            issues.append(
                AreaIssue(
                    severity="warning",
                    code="wall_basis_unknown",
                    message=(
                        f"{room.name} does not state whether dimensions are inside face, "
                        "centerline, or outside face of walls."
                    ),
                    room_id=room.room_id,
                )
            )

    for component in room.components:
        component_result, component_issues = _solve_component(room, component)
        issues.extend(component_issues)
        if component_result is None:
            continue
        component_results.append(component_result)
        if component.operation == "add":
            add_area += component_result.area_sqm
        else:
            subtract_area += component_result.area_sqm

    labeled_area_sqm = room.labeled_area.to_square_meters() if room.labeled_area else None
    computed_area = add_area - subtract_area if component_results else None

    if component_results and add_area <= 0:
        issues.append(
            AreaIssue(
                severity="error",
                code="room_has_no_positive_included_area",
                message=f"{room.name} has no positive included area.",
                room_id=room.room_id,
            )
        )

    if component_results and subtract_area >= add_area:
        issues.append(
            AreaIssue(
                severity="error",
                code="negative_space_exceeds_room",
                message=(
                    f"{room.name} subtracts {subtract_area:.2f} sqm from only "
                    f"{add_area:.2f} sqm of included area."
                ),
                room_id=room.room_id,
            )
        )

    if computed_area is not None and computed_area <= 0:
        issues.append(
            AreaIssue(
                severity="error",
                code="non_positive_room_area",
                message=f"{room.name} computes to {computed_area:.2f} sqm.",
                room_id=room.room_id,
            )
        )

    if computed_area is not None and computed_area > 0:
        issues.extend(_validate_room_area_size(room, computed_area))

    if component_results:
        issues.extend(_compare_labeled_area(room, computed_area, labeled_area_sqm))
        final_area = computed_area
    elif labeled_area_sqm is not None:
        final_area = labeled_area_sqm
        issues.append(
            AreaIssue(
                severity="warning",
                code="labeled_area_only",
                message=(
                    f"{room.name} uses only the area label because no dimensions were extracted."
                ),
                room_id=room.room_id,
            )
        )
    else:
        final_area = None

    return (
        RoomAreaResult(
            room_id=room.room_id,
            name=room.name,
            boundary_basis=room.boundary_basis,
            measurement_method=room.measurement_method,
            area_sqm=round(final_area, 4) if final_area is not None else None,
            add_area_sqm=round(add_area, 4),
            subtract_area_sqm=round(subtract_area, 4),
            components=component_results,
            labeled_area_sqm=round(labeled_area_sqm, 4) if labeled_area_sqm is not None else None,
            confidence=room.confidence,
        ),
        issues,
    )


def _solve_component(
    room: RoomAreaDraft,
    component: RectangularAreaComponent,
) -> tuple[ComponentAreaResult | None, list[AreaIssue]]:
    issues: list[AreaIssue] = []
    length_m = component.length.to_meters()
    width_m = component.width.to_meters()

    if length_m is None:
        issues.append(
            AreaIssue(
                severity="error",
                code="invalid_or_missing_length",
                message=f"{component.name} in {room.name} has no usable length.",
                room_id=room.room_id,
                component_id=component.component_id,
                evidence=[component.length.source_text] if component.length.source_text else [],
            )
        )
    if width_m is None:
        issues.append(
            AreaIssue(
                severity="error",
                code="invalid_or_missing_width",
                message=f"{component.name} in {room.name} has no usable width.",
                room_id=room.room_id,
                component_id=component.component_id,
                evidence=[component.width.source_text] if component.width.source_text else [],
            )
        )

    if length_m is None or width_m is None:
        return None, issues

    for axis_name, value_m in (("length", length_m), ("width", width_m)):
        if value_m < MIN_REASONABLE_ROOM_DIMENSION_M:
            issues.append(
                AreaIssue(
                    severity="warning",
                    code="suspiciously_small_dimension",
                    message=(
                        f"{component.name} in {room.name} has {axis_name} "
                        f"{value_m:.3f} m, which may indicate a bad unit or OCR read."
                    ),
                    room_id=room.room_id,
                    component_id=component.component_id,
                )
            )
        if value_m > MAX_REASONABLE_ROOM_DIMENSION_M:
            issues.append(
                AreaIssue(
                    severity="error",
                    code="unreasonable_dimension",
                    message=(
                        f"{component.name} in {room.name} has {axis_name} "
                        f"{value_m:.2f} m, which is unreasonable for a room takeoff."
                    ),
                    room_id=room.room_id,
                    component_id=component.component_id,
                )
            )

    aspect_ratio = max(length_m, width_m) / min(length_m, width_m)
    if aspect_ratio > MAX_ASPECT_RATIO_REVIEW:
        issues.append(
            AreaIssue(
                severity="warning",
                code="extreme_aspect_ratio",
                message=(
                    f"{component.name} in {room.name} has aspect ratio {aspect_ratio:.1f}:1; "
                    "verify this is not an OCR or boundary error."
                ),
                room_id=room.room_id,
                component_id=component.component_id,
            )
        )

    area = length_m * width_m
    signed_area = area if component.operation == "add" else -area
    return (
        ComponentAreaResult(
            component_id=component.component_id,
            name=component.name,
            operation=component.operation,
            length_m=round(length_m, 4),
            width_m=round(width_m, 4),
            area_sqm=round(area, 4),
            signed_area_sqm=round(signed_area, 4),
        ),
        issues,
    )


def _validate_room_area_size(room: RoomAreaDraft, area_sqm: float) -> list[AreaIssue]:
    issues: list[AreaIssue] = []
    if area_sqm < MIN_REASONABLE_ROOM_AREA_SQM:
        issues.append(
            AreaIssue(
                severity="warning",
                code="suspiciously_small_room_area",
                message=f"{room.name} computes to only {area_sqm:.2f} sqm.",
                room_id=room.room_id,
            )
        )
    if area_sqm > MAX_REASONABLE_ROOM_AREA_SQM:
        issues.append(
            AreaIssue(
                severity="warning",
                code="suspiciously_large_room_area",
                message=f"{room.name} computes to {area_sqm:.2f} sqm.",
                room_id=room.room_id,
            )
        )
    return issues


def _compare_labeled_area(
    room: RoomAreaDraft,
    computed_area_sqm: float | None,
    labeled_area_sqm: float | None,
) -> list[AreaIssue]:
    if computed_area_sqm is None or labeled_area_sqm is None:
        return []

    difference = abs(computed_area_sqm - labeled_area_sqm)
    tolerance = max(AREA_LABEL_ABSOLUTE_TOLERANCE_SQM, labeled_area_sqm * AREA_LABEL_WARNING_PERCENT)
    error_tolerance = max(
        AREA_LABEL_ABSOLUTE_TOLERANCE_SQM,
        labeled_area_sqm * AREA_LABEL_ERROR_PERCENT,
    )

    if difference <= tolerance:
        return []

    percent = difference / labeled_area_sqm if labeled_area_sqm else 0
    severity = "error" if difference > error_tolerance else "warning"
    return [
        AreaIssue(
            severity=severity,
            code="area_label_mismatch",
            message=(
                f"{room.name} computes to {computed_area_sqm:.2f} sqm, but the plan label "
                f"shows {labeled_area_sqm:.2f} sqm ({percent:.1%} difference)."
            ),
            room_id=room.room_id,
            evidence=[room.labeled_area.source_text] if room.labeled_area and room.labeled_area.source_text else [],
        )
    ]


def _validate_dimension_consistency(check: DimensionConsistencyCheck) -> list[AreaIssue]:
    expected_m = check.expected_total.to_meters()
    part_values = [part.to_meters() for part in check.parts]
    if expected_m is None or any(value is None for value in part_values):
        return [
            AreaIssue(
                severity="error",
                code="dimension_check_has_unusable_values",
                message=f"Cannot validate dimension check '{check.description}' because a value is missing or unitless.",
                evidence=[check.source_text] if check.source_text else [],
            )
        ]

    parts_sum = sum(value for value in part_values if value is not None)
    difference = abs(expected_m - parts_sum)
    tolerance = max(LENGTH_SUM_TOLERANCE_M, expected_m * LENGTH_SUM_TOLERANCE_PERCENT)
    if difference <= tolerance:
        return []

    return [
        AreaIssue(
            severity="error",
            code="dimension_sum_mismatch",
            message=(
                f"Dimension check '{check.description}' does not add up: expected "
                f"{expected_m:.2f} m, parts sum to {parts_sum:.2f} m."
            ),
            evidence=[check.source_text] if check.source_text else [],
        )
    ]


def _check_duplicate_room_names(rooms: list[RoomAreaDraft]) -> list[AreaIssue]:
    counts = Counter(room.name.strip().lower() for room in rooms if room.name.strip())
    duplicates = [name for name, count in counts.items() if count > 1]
    return [
        AreaIssue(
            severity="warning",
            code="duplicate_room_name",
            message=f"Room name '{name}' appears more than once; verify the rooms are distinct.",
        )
        for name in duplicates
    ]


def _sum_known_room_areas(room_results: list[RoomAreaResult]) -> float | None:
    values = [room.area_sqm for room in room_results]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _build_questions(extraction: PlanAreaExtraction, issues: list[AreaIssue]) -> list[str]:
    questions = list(extraction.questions)
    for issue in issues:
        if issue.severity != "error":
            continue
        if issue.code == "dimension_sum_mismatch":
            questions.append(
                "The visible dimensions do not add up. Which dimension should be treated as authoritative?"
            )
        elif issue.code in {"invalid_or_missing_length", "invalid_or_missing_width"}:
            questions.append(
                "One or more room dimensions are missing or unitless. Can you provide the missing measurement or a clearer plan?"
            )
        elif issue.code == "negative_space_exceeds_room":
            questions.append(
                "A subtraction or void is larger than the included room area. Can you confirm the intended boundary and void dimensions?"
            )
        elif issue.code == "area_label_mismatch":
            questions.append(
                "The computed area disagrees with an area label on the plan. Should the area label or the visible dimensions be trusted?"
            )

    deduped: list[str] = []
    for question in questions:
        if question not in deduped:
            deduped.append(question)
    return deduped
