from abscissa_ci.area.models import (
    AreaMeasurement,
    DimensionConsistencyCheck,
    DimensionMeasurement,
    PlanAreaExtraction,
    RectangularAreaComponent,
    RoomAreaDraft,
)
from abscissa_ci.area.validation import solve_area_takeoff


def dim(value: float | None, unit: str = "m") -> DimensionMeasurement:
    return DimensionMeasurement(value=value, unit=unit, source_text=str(value) if value else None)


def component(
    component_id: str,
    length: float | None,
    width: float | None,
    operation: str = "add",
) -> RectangularAreaComponent:
    return RectangularAreaComponent(
        component_id=component_id,
        name=component_id,
        operation=operation,
        length=dim(length),
        width=dim(width),
        confidence=0.9,
    )


def room(*components: RectangularAreaComponent, labeled_area: float | None = None) -> RoomAreaDraft:
    return RoomAreaDraft(
        room_id="r1",
        name="Living Room",
        boundary_basis="inside_face_of_walls",
        measurement_method="dimension_labels",
        components=list(components),
        labeled_area=AreaMeasurement(value=labeled_area, unit="sqm") if labeled_area else None,
        confidence=0.9,
    )


def test_solves_room_area_with_negative_space() -> None:
    extraction = PlanAreaExtraction(
        rooms=[
            room(
                component("main", 6, 4),
                component("shaft", 1, 1.5, "subtract"),
            )
        ]
    )

    report = solve_area_takeoff(extraction)

    assert report.can_compute is True
    assert report.total_area_sqm == 22.5
    assert report.rooms[0].subtract_area_sqm == 1.5


def test_rejects_negative_space_larger_than_room() -> None:
    extraction = PlanAreaExtraction(
        rooms=[
            room(
                component("main", 2, 2),
                component("void", 3, 3, "subtract"),
            )
        ]
    )

    report = solve_area_takeoff(extraction)

    assert report.can_compute is False
    assert report.total_area_sqm is None
    assert any(issue.code == "negative_space_exceeds_room" for issue in report.issues)


def test_rejects_labeled_area_that_disagrees_with_dimensions() -> None:
    extraction = PlanAreaExtraction(rooms=[room(component("main", 5, 4), labeled_area=30)])

    report = solve_area_takeoff(extraction)

    assert report.can_compute is False
    assert any(issue.code == "area_label_mismatch" for issue in report.issues)


def test_rejects_dimension_sum_that_does_not_make_sense() -> None:
    extraction = PlanAreaExtraction(
        rooms=[room(component("main", 4, 3))],
        consistency_checks=[
            DimensionConsistencyCheck(
                check_id="x-total",
                description="overall width versus room segments",
                expected_total=dim(10),
                parts=[dim(4), dim(3)],
                source_text="10m overall, segments 4m + 3m",
            )
        ],
    )

    report = solve_area_takeoff(extraction)

    assert report.can_compute is False
    assert any(issue.code == "dimension_sum_mismatch" for issue in report.issues)


def test_rejects_missing_component_dimension() -> None:
    extraction = PlanAreaExtraction(rooms=[room(component("main", 5, None))])

    report = solve_area_takeoff(extraction)

    assert report.can_compute is False
    assert any(issue.code == "invalid_or_missing_width" for issue in report.issues)


def test_warns_when_wall_basis_is_not_net_internal() -> None:
    draft = room(component("main", 5, 4))
    draft.boundary_basis = "outside_face_of_walls"
    extraction = PlanAreaExtraction(rooms=[draft])

    report = solve_area_takeoff(extraction)

    assert report.can_compute is True
    assert any(issue.code == "wall_basis_not_net_internal" for issue in report.issues)
