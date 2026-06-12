from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def clean_float(value: float, places: int = 4) -> float:
    rounded = round(float(value), places)
    return 0.0 if rounded == -0.0 else rounded


class AbscissaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RectangleDraft(AbscissaModel):
    name: str = Field(default="Unlabeled area", min_length=1)
    length_m: float = Field(gt=0)
    width_m: float = Field(gt=0)
    operation: Literal["add", "subtract"] = "add"
    source_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip() or "Unlabeled area"


class PolygonPoint(AbscissaModel):
    x_m: float
    y_m: float


class EdgeDimensionLabel(AbscissaModel):
    """A dimension printed on the drawing, tied to the boundary edge it measures.

    Edge ``i`` connects point ``i`` to point ``i + 1``; the last edge closes the
    ring back to point ``0``.
    """

    edge_index: int = Field(ge=0)
    length_m: float = Field(gt=0)
    source_text: str | None = None


class PolygonDraft(AbscissaModel):
    name: str = Field(default="Unlabeled polygon", min_length=1)
    operation: Literal["add", "subtract"] = "add"
    points: list[PolygonPoint] = Field(min_length=3)
    edge_labels: list[EdgeDimensionLabel] = Field(default_factory=list)
    # Overall printed plan dimensions, cross-checked against the vertex span.
    bounding_width_m: float | None = Field(default=None, gt=0)
    bounding_height_m: float | None = Field(default=None, gt=0)
    source_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip() or "Unlabeled polygon"

    @field_validator("points")
    @classmethod
    def strip_duplicate_closing_point(cls, points: list[PolygonPoint]) -> list[PolygonPoint]:
        if (
            len(points) >= 2
            and abs(points[0].x_m - points[-1].x_m) < 1e-9
            and abs(points[0].y_m - points[-1].y_m) < 1e-9
        ):
            points = points[:-1]
        if len(points) < 3:
            raise ValueError("Polygon needs at least 3 distinct points.")
        return points


class TraverseMove(AbscissaModel):
    """One leg of a closed boundary traverse, like a surveyor's field note.

    The extraction agent reports the boundary as compass moves instead of
    coordinates; vertices are derived deterministically from the moves.
    """

    direction: Literal["E", "N", "W", "S"]
    length_m: float = Field(gt=0)
    # Exact printed text when the drawing labels this leg; None when derived.
    source_text: str | None = None
    # Chain arithmetic behind an unprinted length, e.g. "16.00 - 5.00 - 7.00".
    derivation: str | None = None


class PolygonTraverse(AbscissaModel):
    name: str = Field(default="Unlabeled polygon", min_length=1)
    operation: Literal["add", "subtract"] = "add"
    moves: list[TraverseMove] = Field(min_length=4)
    bounding_width_m: float | None = Field(default=None, gt=0)
    bounding_height_m: float | None = Field(default=None, gt=0)
    source_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip() or "Unlabeled polygon"


class DimensionSurveyEntry(AbscissaModel):
    """A printed dimension observed during the perception pass, before any
    shape reasoning happens."""

    source_text: str = Field(min_length=1)
    orientation: Literal["horizontal", "vertical", "unknown"] = "unknown"
    # Where the dimension line sits relative to the building outline.
    side: Literal["top", "bottom", "left", "right", "interior", "unknown"] = "unknown"


class DimensionChainSegment(AbscissaModel):
    # Exact printed text, or None for an unlabeled run between extension lines.
    source_text: str | None = None


class DimensionChain(AbscissaModel):
    """One dimension lane: consecutive segments sharing extension lines.

    The extension lines of full-extent chains define the station grid that
    every footprint corner must land on.
    """

    orientation: Literal["horizontal", "vertical"]
    side: Literal["top", "bottom", "left", "right", "interior", "unknown"] = "unknown"
    # Segments in drawing order: left-to-right for horizontal chains,
    # top-to-bottom for vertical chains.
    segments: list[DimensionChainSegment] = Field(min_length=1)
    # The chain's first extension line (left end for horizontal, top end for
    # vertical) marks the outline's extreme position on its axis.
    starts_at_outline_edge: bool = False
    # The chain's last extension line (right end / bottom end) marks the
    # outline's opposite extreme.
    ends_at_outline_edge: bool = False
    # True when the chain measures the entire extent (both ends anchored).
    spans_full_extent: bool = False


class DimensionSurvey(AbscissaModel):
    bounding_width_m: float | None = Field(default=None, gt=0)
    bounding_height_m: float | None = Field(default=None, gt=0)
    entries: list[DimensionSurveyEntry] = Field(default_factory=list)
    chains: list[DimensionChain] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TraverseExtraction(AbscissaModel):
    """Assembly-pass output: boundary traverses built from the survey."""

    project_name: str | None = None
    traverses: list[PolygonTraverse] = Field(default_factory=list)
    rectangles: list[RectangleDraft] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OccupiedCell(AbscissaModel):
    """One floor-covered station-grid cell, 1-based, row 1 at the top."""

    row: int = Field(ge=1)
    col: int = Field(ge=1)


class OccupancyExtraction(AbscissaModel):
    """Assembly-pass output when the station grid is fully determined.

    The model only classifies each station-grid cell as floor or not; the
    polygon, its edges, and the area are all derived deterministically. The
    occupancy is stated twice - cell list and boolean matrix - and the two
    must agree exactly, which catches inverted or misindexed rows.
    """

    project_name: str | None = None
    occupied_cells: list[OccupiedCell] = Field(default_factory=list)
    # One list per grid row, top-to-bottom; booleans left-to-right per row.
    occupied_rows: list[list[bool]] = Field(default_factory=list)
    # Cells that look partially covered. On a correct station grid every cell
    # is fully floor or fully not, so any entry here blocks the draft.
    partially_covered_cells: list[OccupiedCell] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PolygonAreaResult(AbscissaModel):
    name: str
    operation: Literal["add", "subtract"]
    is_valid: bool
    point_count: int
    area_sqm: float | None = None
    signed_area_sqm: float | None = None
    perimeter_m: float | None = None
    calculation: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_text: str | None = None
    confidence: float | None = None


class FloorPlanExtraction(AbscissaModel):
    project_name: str | None = None
    rectangles: list[RectangleDraft] = Field(default_factory=list)
    polygons: list[PolygonDraft] = Field(default_factory=list)
    # Every dimension label printed on the drawing, exactly as printed,
    # including duplicates. Used to verify the polygons account for all of them.
    dimension_inventory: list[str] = Field(default_factory=list)
    # Extraction-time validation errors that downstream consumers cannot
    # re-derive (misclosures, station misalignment). Non-empty blocks compute.
    validation_errors: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TileSpec(AbscissaModel):
    length_mm: float = Field(default=600, gt=0)
    width_mm: float = Field(default=600, gt=0)

    @property
    def area_sqm(self) -> float:
        return clean_float((self.length_mm / 1000) * (self.width_mm / 1000), places=6)


class TileEstimateInput(AbscissaModel):
    project_name: str = "Untitled tile estimate"
    input_source: Literal["image", "json", "manual", "agent_tool", "unknown"] = "unknown"
    source_image_path: str | None = None
    rectangles: list[RectangleDraft] = Field(default_factory=list)
    polygons: list[PolygonDraft] = Field(default_factory=list)
    dimension_inventory: list[str] = Field(default_factory=list)
    # Carried from extraction; non-empty blocks computation because these
    # errors cannot be re-derived from the shapes alone.
    validation_errors: list[str] = Field(default_factory=list)
    tile_spec: TileSpec = Field(default_factory=TileSpec)
    waste_percent: float = Field(default=10, ge=0)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RoomAreaResult(AbscissaModel):
    name: str
    length_m: float
    width_m: float
    operation: Literal["add", "subtract"]
    area_sqm: float
    signed_area_sqm: float
    calculation: str
    source_text: str | None = None
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)


class TileCountResult(AbscissaModel):
    tile_length_mm: float
    tile_width_mm: float
    tile_area_sqm: float
    base_tile_count: int
    order_tile_count: int
    waste_percent: float
    calculation: str


class TileEstimateResult(AbscissaModel):
    can_compute: bool
    project_name: str
    input_source: str
    source_image_path: str | None = None
    extracted_rectangles: list[RectangleDraft] = Field(default_factory=list)
    extracted_polygons: list[PolygonDraft] = Field(default_factory=list)
    rooms: list[RoomAreaResult] = Field(default_factory=list)
    polygons: list[PolygonAreaResult] = Field(default_factory=list)
    total_floor_area_sqm: float | None = None
    tile_spec: TileSpec = Field(default_factory=TileSpec)
    tile_area_sqm: float
    base_tile_count: int | None = None
    order_tile_count: int | None = None
    waste_percent: float
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_status: Literal["draft_for_human_evaluation"] = "draft_for_human_evaluation"
