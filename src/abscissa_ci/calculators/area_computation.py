from __future__ import annotations

from abscissa_ci.models import RectangleDraft, RoomAreaResult, clean_float


def compute_rectangle_area(rectangle: RectangleDraft) -> RoomAreaResult:
    area_sqm = clean_float(rectangle.length_m * rectangle.width_m)
    signed_area_sqm = area_sqm if rectangle.operation == "add" else -area_sqm
    return RoomAreaResult(
        name=rectangle.name,
        length_m=clean_float(rectangle.length_m),
        width_m=clean_float(rectangle.width_m),
        operation=rectangle.operation,
        area_sqm=area_sqm,
        signed_area_sqm=signed_area_sqm,
        calculation=f"{rectangle.operation} ({rectangle.length_m:g}m * {rectangle.width_m:g}m)",
        source_text=rectangle.source_text,
        confidence=rectangle.confidence,
        warnings=rectangle.warnings,
    )


def compute_room_areas(rectangles: list[RectangleDraft]) -> list[RoomAreaResult]:
    return [compute_rectangle_area(rectangle) for rectangle in rectangles]


def compute_total_area(room_areas: list[RoomAreaResult]) -> float:
    return clean_float(sum(room.signed_area_sqm for room in room_areas))
