"""Shared door component style.

Both the browser canvas (``static/app.js``) and the SVG exporter
(``export.py``) read their door geometry and colors from the same
``static/door_style.json`` file. Keeping a single source of truth prevents the
two renderers from drifting apart when the door visual is tuned.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


HingeSide = Literal["start", "end"]
DoorSwingDirection = Literal["cw", "ccw"]

STYLE_PATH = Path(__file__).resolve().parent / "static" / "door_style.json"


class DoorStyleColors(BaseModel):
    model_config = ConfigDict(extra="ignore")

    frame_fill: str = "#ffffff"
    frame_stroke: str = "#111827"
    leaf_fill: str = "#ffffff"
    leaf_fill_selected: str = "#fff7ed"
    leaf_stroke: str = "#111827"
    swing_stroke: str = "#64748b"
    selected: str = "#f97316"


class DoorSwingDefaults(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_direction: DoorSwingDirection = "cw"
    default_hinge_side: HingeSide = "start"


class DoorLeafWidths(BaseModel):
    model_config = ConfigDict(extra="ignore")

    exterior: float = 900.0
    interior: float = 800.0


class DoorStyle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = "abscissa-door-style-v1"
    frame_jamb_mm: float = Field(default=50.0, gt=0)
    leaf_thickness_mm: float = Field(default=45.0, gt=0)
    leaf_width_mm: DoorLeafWidths = Field(default_factory=DoorLeafWidths)
    swing: DoorSwingDefaults = Field(default_factory=DoorSwingDefaults)
    leaf_thickness_px_min: float = 5.0
    leaf_thickness_px_max: float = 12.0
    jamb_px_min: float = 3.0
    colors: DoorStyleColors = Field(default_factory=DoorStyleColors)

    def leaf_width_mm_for_wall_type(self, wall_type: str) -> float:
        if wall_type == "exterior":
            return self.leaf_width_mm.exterior
        return self.leaf_width_mm.interior

    def opening_width_m_for_wall_type(self, wall_type: str) -> float:
        leaf_m = self.leaf_width_mm_for_wall_type(wall_type) / 1000.0
        return leaf_m + 2.0 * (self.frame_jamb_mm / 1000.0)


@lru_cache(maxsize=1)
def load_door_style() -> DoorStyle:
    try:
        raw = json.loads(STYLE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DoorStyle()
    return DoorStyle.model_validate(raw)
