from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


LengthUnit = Literal["m", "cm", "mm", "ft", "in", "unknown"]
AreaUnit = Literal["sqm", "sqft", "unknown"]
Operation = Literal["add", "subtract"]
BoundaryBasis = Literal[
    "inside_face_of_walls",
    "wall_centerline",
    "outside_face_of_walls",
    "mixed",
    "unknown",
]
MeasurementMethod = Literal[
    "dimension_labels",
    "scale_bar",
    "image_scale",
    "labeled_area",
    "assumption",
    "mixed",
    "unknown",
]
MeasurementBasis = Literal[
    "net_internal_room_area",
    "gross_floor_area",
    "centerline_area",
    "unknown",
]
Severity = Literal["info", "warning", "error"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DimensionMeasurement(StrictModel):
    value: float | None = Field(default=None, description="Numeric value as shown or normalized.")
    unit: LengthUnit = "unknown"
    source_text: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_meters(self) -> float | None:
        if self.value is None or self.value <= 0:
            return None
        factors = {
            "m": 1.0,
            "cm": 0.01,
            "mm": 0.001,
            "ft": 0.3048,
            "in": 0.0254,
        }
        factor = factors.get(self.unit)
        if factor is None:
            return None
        return self.value * factor


class AreaMeasurement(StrictModel):
    value: float | None = None
    unit: AreaUnit = "unknown"
    source_text: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_square_meters(self) -> float | None:
        if self.value is None or self.value <= 0:
            return None
        if self.unit == "sqm":
            return self.value
        if self.unit == "sqft":
            return self.value * 0.09290304
        return None


class NormalizedImageRegion(StrictModel):
    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)


class RectangularAreaComponent(StrictModel):
    component_id: str
    name: str
    operation: Operation = "add"
    length: DimensionMeasurement
    width: DimensionMeasurement
    reason: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RoomAreaDraft(StrictModel):
    room_id: str
    name: str
    room_type: str | None = None
    boundary_basis: BoundaryBasis = "unknown"
    measurement_method: MeasurementMethod = "unknown"
    image_region: NormalizedImageRegion | None = None
    components: list[RectangularAreaComponent] = Field(default_factory=list)
    labeled_area: AreaMeasurement | None = None
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DimensionConsistencyCheck(StrictModel):
    check_id: str
    description: str
    axis: Literal["x", "y", "unknown"] = "unknown"
    expected_total: DimensionMeasurement
    parts: list[DimensionMeasurement]
    source_text: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PlanAreaExtraction(StrictModel):
    project_name: str | None = None
    requested_measurement_basis: MeasurementBasis = "net_internal_room_area"
    scale_basis: MeasurementMethod = "unknown"
    units_detected: list[LengthUnit] = Field(default_factory=list)
    rooms: list[RoomAreaDraft] = Field(default_factory=list)
    consistency_checks: list[DimensionConsistencyCheck] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class AreaIssue(StrictModel):
    severity: Severity
    code: str
    message: str
    room_id: str | None = None
    component_id: str | None = None
    evidence: list[str] = Field(default_factory=list)


class ComponentAreaResult(StrictModel):
    component_id: str
    name: str
    operation: Operation
    length_m: float
    width_m: float
    area_sqm: float
    signed_area_sqm: float


class RoomAreaResult(StrictModel):
    room_id: str
    name: str
    boundary_basis: BoundaryBasis
    measurement_method: MeasurementMethod
    area_sqm: float | None
    add_area_sqm: float
    subtract_area_sqm: float
    components: list[ComponentAreaResult] = Field(default_factory=list)
    labeled_area_sqm: float | None = None
    confidence: float


class AreaReport(StrictModel):
    can_compute: bool
    project_name: str | None = None
    source_image_path: str | None = None
    requested_measurement_basis: MeasurementBasis
    total_area_sqm: float | None
    rooms: list[RoomAreaResult] = Field(default_factory=list)
    issues: list[AreaIssue] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
