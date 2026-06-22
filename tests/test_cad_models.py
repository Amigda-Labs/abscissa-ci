import pytest
from pydantic import ValidationError

from abscissa_ci.cad.models import CadProject


def test_cad_project_applies_default_wall_thicknesses() -> None:
    project = CadProject.model_validate(
        {
            "project": {"name": "Test Plan"},
            "levels": [
                {
                    "level_id": "level-1",
                    "name": "Ground Floor",
                    "walls": [
                        {
                            "wall_id": "w-ext",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "wall_type": "exterior",
                        },
                        {
                            "wall_id": "w-int",
                            "start": {"x": 1, "y": 0},
                            "end": {"x": 1, "y": 3},
                            "wall_type": "interior",
                        },
                    ],
                    "openings": [],
                    "rooms": [],
                    "dimensions": [],
                }
            ],
        }
    )

    assert project.levels[0].walls[0].thickness_mm == 150
    assert project.levels[0].walls[0].exterior is True
    assert project.levels[0].walls[1].thickness_mm == 100
    assert project.levels[0].walls[1].exterior is False


def test_cad_project_rejects_non_orthogonal_walls() -> None:
    with pytest.raises(ValidationError, match="horizontal or vertical"):
        CadProject.model_validate(
            {
                "levels": [
                    {
                        "walls": [
                            {
                                "wall_id": "w1",
                                "start": {"x": 0, "y": 0},
                                "end": {"x": 4, "y": 3},
                                "wall_type": "interior",
                            }
                        ]
                    }
                ]
            }
        )


def test_cad_project_accepts_orthogonal_draft_lines() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "lines": [
                        {
                            "line_id": "l1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 3, "y": 0},
                        }
                    ]
                }
            ]
        }
    )

    assert project.levels[0].lines[0].length_m == 3


def test_cad_project_accepts_rectangular_lot_area() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "lots": [
                        {
                            "lot_id": "lot-1",
                            "corner_a": {"x": 0, "y": 0},
                            "corner_b": {"x": 12, "y": 20},
                        }
                    ]
                }
            ]
        }
    )

    lot = project.levels[0].lots[0]
    assert lot.boundary_thickness_mm == 35
    assert lot.dash_pattern == "lot_boundary_dash_circle"
    assert lot.area_sqm == 240


def test_cad_project_rejects_zero_width_lot_area() -> None:
    with pytest.raises(ValidationError, match="non-zero width and depth"):
        CadProject.model_validate(
            {
                "levels": [
                    {
                        "lots": [
                            {
                                "lot_id": "lot-1",
                                "corner_a": {"x": 0, "y": 0},
                                "corner_b": {"x": 0, "y": 20},
                            }
                        ]
                    }
                ]
            }
        )


def test_cad_project_rejects_non_orthogonal_draft_lines() -> None:
    with pytest.raises(ValidationError, match="lines must be horizontal or vertical"):
        CadProject.model_validate(
            {
                "levels": [
                    {
                        "lines": [
                            {
                                "line_id": "l1",
                                "start": {"x": 0, "y": 0},
                                "end": {"x": 3, "y": 2},
                            }
                        ]
                    }
                ]
            }
        )


def test_cad_project_preserves_dimension_offset() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "dimensions": [
                        {
                            "dimension_id": "dim-1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "offset_m": -0.75,
                        }
                    ]
                }
            ]
        }
    )

    assert project.levels[0].dimensions[0].offset_m == -0.75


def test_cad_project_rejects_opening_that_exceeds_parent_wall() -> None:
    with pytest.raises(ValidationError, match="exceeds its parent wall length"):
        CadProject.model_validate(
            {
                "levels": [
                    {
                        "walls": [
                            {
                                "wall_id": "w1",
                                "start": {"x": 0, "y": 0},
                                "end": {"x": 2, "y": 0},
                                "wall_type": "exterior",
                            }
                        ],
                        "openings": [
                            {
                                "opening_id": "d1",
                                "opening_type": "door",
                                "parent_wall_id": "w1",
                                "offset_m": 1.5,
                                "width_m": 0.9,
                            }
                        ],
                    }
                ]
            }
        )


def test_cad_project_preserves_door_swing_direction() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "wall_type": "exterior",
                        }
                    ],
                    "openings": [
                        {
                            "opening_id": "d1",
                            "opening_type": "door",
                            "parent_wall_id": "w1",
                            "offset_m": 1.0,
                            "width_m": 0.9,
                            "swing_direction": "ccw",
                        }
                    ],
                }
            ]
        }
    )

    assert project.levels[0].openings[0].swing_direction == "ccw"


def test_cad_project_door_defaults_hinge_side_and_optional_style_fields() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "wall_type": "exterior",
                        }
                    ],
                    "openings": [
                        {
                            "opening_id": "d1",
                            "opening_type": "door",
                            "parent_wall_id": "w1",
                            "offset_m": 1.0,
                            "width_m": 1.0,
                        }
                    ],
                }
            ]
        }
    )

    door = project.levels[0].openings[0]
    assert door.hinge_side == "start"
    assert door.frame_jamb_mm is None
    assert door.leaf_thickness_mm is None


def test_cad_project_preserves_editable_door_style_fields() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "wall_type": "exterior",
                        }
                    ],
                    "openings": [
                        {
                            "opening_id": "d1",
                            "opening_type": "door",
                            "parent_wall_id": "w1",
                            "offset_m": 1.0,
                            "width_m": 1.0,
                            "hinge_side": "end",
                            "frame_jamb_mm": 75,
                            "leaf_thickness_mm": 60,
                        }
                    ],
                }
            ]
        }
    )

    door = project.levels[0].openings[0]
    assert door.hinge_side == "end"
    assert door.frame_jamb_mm == 75
    assert door.leaf_thickness_mm == 60


def test_cad_project_accepts_explicit_door_geometry_for_wall_gaps() -> None:
    project = CadProject.model_validate(
        {
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w-before",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 1, "y": 0},
                            "wall_type": "interior",
                        },
                        {
                            "wall_id": "w-after",
                            "start": {"x": 1.9, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "wall_type": "interior",
                        },
                    ],
                    "openings": [
                        {
                            "opening_id": "door-gap",
                            "opening_type": "door",
                            "start": {"x": 1, "y": 0},
                            "end": {"x": 1.9, "y": 0},
                            "offset_m": 0,
                            "width_m": 0.9,
                            "wall_thickness_mm": 100,
                        }
                    ],
                }
            ]
        }
    )

    door = project.levels[0].openings[0]
    assert door.parent_wall_id is None
    assert door.start is not None
    assert door.end is not None
    assert door.wall_thickness_mm == 100


def test_cad_project_rejects_room_unknown_boundary_wall() -> None:
    with pytest.raises(ValidationError, match="unknown boundary walls"):
        CadProject.model_validate(
            {
                "levels": [
                    {
                        "walls": [],
                        "rooms": [
                            {
                                "room_id": "r1",
                                "name": "Living Room",
                                "room_type": "living_room",
                                "label": {"x": 1, "y": 1},
                                "boundary_wall_ids": ["missing-wall"],
                            }
                        ],
                    }
                ]
            }
        )
