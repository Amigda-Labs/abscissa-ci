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


class FloorPlanExtraction(AbscissaModel):
    project_name: str | None = None
    rectangles: list[RectangleDraft] = Field(default_factory=list)
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
    rooms: list[RoomAreaResult] = Field(default_factory=list)
    total_floor_area_sqm: float | None = None
    tile_spec: TileSpec = Field(default_factory=TileSpec)
    tile_area_sqm: float
    base_tile_count: int | None = None
    order_tile_count: int | None = None
    waste_percent: float
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_status: Literal["draft_for_human_evaluation"] = "draft_for_human_evaluation"
