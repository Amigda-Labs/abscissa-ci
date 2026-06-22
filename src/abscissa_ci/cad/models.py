from __future__ import annotations

from math import isclose
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LengthUnit = Literal["m"]
WallThicknessUnit = Literal["mm"]
WallType = Literal["exterior", "interior"]
OpeningType = Literal["door", "window"]
DoorSwingDirection = Literal["cw", "ccw"]
DoorHingeSide = Literal["start", "end"]
DimensionKind = Literal["linear"]

EXTERIOR_WALL_THICKNESS_MM = 150.0
INTERIOR_WALL_THICKNESS_MM = 100.0
DEFAULT_GRID_SIZE_M = 0.25
DEFAULT_DOOR_WIDTH_M = 0.9
DEFAULT_WINDOW_WIDTH_M = 1.2
LOT_BOUNDARY_THICKNESS_MM = 35.0
ORTHOGONAL_TOLERANCE = 1e-9


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(StrictModel):
    x: float
    y: float


class ProjectDefaults(StrictModel):
    exterior_wall_thickness_mm: float = Field(default=EXTERIOR_WALL_THICKNESS_MM, gt=0)
    interior_wall_thickness_mm: float = Field(default=INTERIOR_WALL_THICKNESS_MM, gt=0)
    door_width_m: float = Field(default=DEFAULT_DOOR_WIDTH_M, gt=0)
    window_width_m: float = Field(default=DEFAULT_WINDOW_WIDTH_M, gt=0)


class ProjectUnits(StrictModel):
    length: LengthUnit = "m"
    wall_thickness: WallThicknessUnit = "mm"


class ProjectInfo(StrictModel):
    name: str = "Untitled Abscissa Plan"
    units: ProjectUnits = Field(default_factory=ProjectUnits)
    grid_size_m: float = Field(default=DEFAULT_GRID_SIZE_M, gt=0)
    defaults: ProjectDefaults = Field(default_factory=ProjectDefaults)


class WallSegment(StrictModel):
    wall_id: str
    start: Point
    end: Point
    wall_type: WallType = "interior"
    thickness_mm: float | None = Field(default=None, gt=0)
    exterior: bool = False

    @model_validator(mode="after")
    def validate_wall(self) -> WallSegment:
        if same_point(self.start, self.end):
            raise ValueError("wall start and end points must be different")
        if not is_orthogonal(self.start, self.end):
            raise ValueError("v1 CAD walls must be horizontal or vertical")
        if self.thickness_mm is None:
            self.thickness_mm = (
                EXTERIOR_WALL_THICKNESS_MM
                if self.wall_type == "exterior"
                else INTERIOR_WALL_THICKNESS_MM
            )
        self.exterior = self.wall_type == "exterior"
        return self

    @property
    def length_m(self) -> float:
        return abs(self.end.x - self.start.x) + abs(self.end.y - self.start.y)


class DraftLine(StrictModel):
    line_id: str
    start: Point
    end: Point

    @model_validator(mode="after")
    def validate_line(self) -> DraftLine:
        if same_point(self.start, self.end):
            raise ValueError("line start and end points must be different")
        if not is_orthogonal(self.start, self.end):
            raise ValueError("v1 CAD lines must be horizontal or vertical")
        return self

    @property
    def length_m(self) -> float:
        return abs(self.end.x - self.start.x) + abs(self.end.y - self.start.y)


class LotArea(StrictModel):
    lot_id: str
    name: str = "Lot Area"
    corner_a: Point
    corner_b: Point
    boundary_thickness_mm: float = Field(default=LOT_BOUNDARY_THICKNESS_MM, gt=0)
    dash_pattern: str = "lot_boundary_dash_circle"

    @model_validator(mode="after")
    def validate_lot(self) -> LotArea:
        if same_point(self.corner_a, self.corner_b):
            raise ValueError("lot area corners must be different")
        if isclose(self.corner_a.x, self.corner_b.x, abs_tol=ORTHOGONAL_TOLERANCE) or isclose(
            self.corner_a.y,
            self.corner_b.y,
            abs_tol=ORTHOGONAL_TOLERANCE,
        ):
            raise ValueError("rectangular lot area must have non-zero width and depth")
        return self

    @property
    def width_m(self) -> float:
        return abs(self.corner_b.x - self.corner_a.x)

    @property
    def depth_m(self) -> float:
        return abs(self.corner_b.y - self.corner_a.y)

    @property
    def area_sqm(self) -> float:
        return self.width_m * self.depth_m


class Opening(StrictModel):
    opening_id: str
    opening_type: OpeningType
    parent_wall_id: str | None = None
    start: Point | None = None
    end: Point | None = None
    offset_m: float = Field(ge=0)
    width_m: float = Field(gt=0)
    wall_thickness_mm: float | None = Field(default=None, gt=0)
    swing_direction: DoorSwingDirection = "cw"
    hinge_side: DoorHingeSide = "start"
    frame_jamb_mm: float | None = Field(default=None, gt=0)
    leaf_thickness_mm: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_opening_geometry(self) -> Opening:
        has_parent_wall = self.parent_wall_id is not None
        has_explicit_geometry = self.start is not None and self.end is not None
        if not has_parent_wall and not has_explicit_geometry:
            raise ValueError("opening must reference a parent wall or provide start and end points")
        if has_explicit_geometry:
            assert self.start is not None
            assert self.end is not None
            if same_point(self.start, self.end):
                raise ValueError("opening start and end points must be different")
            if not is_orthogonal(self.start, self.end):
                raise ValueError("v1 CAD openings must be horizontal or vertical")
            if self.width_m > opening_length_m(self.start, self.end) + ORTHOGONAL_TOLERANCE:
                raise ValueError("opening width exceeds its explicit geometry length")
        return self


class RoomLabel(StrictModel):
    room_id: str
    name: str
    room_type: str = "room"
    label: Point
    boundary_wall_ids: list[str] = Field(default_factory=list)


class DimensionAnnotation(StrictModel):
    dimension_id: str
    kind: DimensionKind = "linear"
    start: Point
    end: Point
    offset_m: float = 0.0
    label: str | None = None
    reference_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimension(self) -> DimensionAnnotation:
        if same_point(self.start, self.end):
            raise ValueError("dimension start and end points must be different")
        if not is_orthogonal(self.start, self.end):
            raise ValueError("v1 dimensions must be horizontal or vertical")
        return self


class CadLevel(StrictModel):
    level_id: str = "level-1"
    name: str = "Ground Floor"
    lots: list[LotArea] = Field(default_factory=list)
    lines: list[DraftLine] = Field(default_factory=list)
    walls: list[WallSegment] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[RoomLabel] = Field(default_factory=list)
    dimensions: list[DimensionAnnotation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> CadLevel:
        lot_ids = {lot.lot_id for lot in self.lots}
        if len(lot_ids) != len(self.lots):
            raise ValueError("lot ids must be unique within a level")

        line_ids = {line.line_id for line in self.lines}
        if len(line_ids) != len(self.lines):
            raise ValueError("line ids must be unique within a level")

        wall_by_id = {wall.wall_id: wall for wall in self.walls}
        if len(wall_by_id) != len(self.walls):
            raise ValueError("wall ids must be unique within a level")

        opening_ids = {opening.opening_id for opening in self.openings}
        if len(opening_ids) != len(self.openings):
            raise ValueError("opening ids must be unique within a level")

        room_ids = {room.room_id for room in self.rooms}
        if len(room_ids) != len(self.rooms):
            raise ValueError("room ids must be unique within a level")

        dimension_ids = {dimension.dimension_id for dimension in self.dimensions}
        if len(dimension_ids) != len(self.dimensions):
            raise ValueError("dimension ids must be unique within a level")

        for opening in self.openings:
            if opening.parent_wall_id is None:
                continue
            parent_wall = wall_by_id.get(opening.parent_wall_id)
            if parent_wall is None:
                raise ValueError(f"opening {opening.opening_id} references an unknown wall")
            if opening.offset_m + opening.width_m > parent_wall.length_m + ORTHOGONAL_TOLERANCE:
                raise ValueError(f"opening {opening.opening_id} exceeds its parent wall length")

        for room in self.rooms:
            missing_wall_ids = [wall_id for wall_id in room.boundary_wall_ids if wall_id not in wall_by_id]
            if missing_wall_ids:
                raise ValueError(
                    f"room {room.room_id} references unknown boundary walls: "
                    + ", ".join(missing_wall_ids)
                )

        return self


class CadProject(StrictModel):
    schema_version: Literal["abscissa-cad-v1"] = "abscissa-cad-v1"
    project: ProjectInfo = Field(default_factory=ProjectInfo)
    levels: list[CadLevel] = Field(default_factory=lambda: [CadLevel()])

    @model_validator(mode="after")
    def validate_levels(self) -> CadProject:
        if not self.levels:
            raise ValueError("a CAD project must include at least one level")
        level_ids = {level.level_id for level in self.levels}
        if len(level_ids) != len(self.levels):
            raise ValueError("level ids must be unique")
        return self


def same_point(first: Point, second: Point) -> bool:
    return isclose(first.x, second.x, abs_tol=ORTHOGONAL_TOLERANCE) and isclose(
        first.y,
        second.y,
        abs_tol=ORTHOGONAL_TOLERANCE,
    )


def is_orthogonal(start: Point, end: Point) -> bool:
    return isclose(start.x, end.x, abs_tol=ORTHOGONAL_TOLERANCE) or isclose(
        start.y,
        end.y,
        abs_tol=ORTHOGONAL_TOLERANCE,
    )


def opening_length_m(start: Point, end: Point) -> float:
    return abs(end.x - start.x) + abs(end.y - start.y)


def create_default_project(name: str = "Untitled Abscissa Plan") -> CadProject:
    return CadProject(project=ProjectInfo(name=name), levels=[CadLevel()])
