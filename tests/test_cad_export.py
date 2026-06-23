from abscissa_ci.cad.export import export_project_svg
from abscissa_ci.cad.models import CadProject


def test_export_project_svg_contains_semantic_floor_plan_entities() -> None:
    project = CadProject.model_validate(
        {
            "project": {"name": "Clinic Draft"},
            "levels": [
                {
                    "lots": [
                        {
                            "lot_id": "lot-1",
                            "name": "Main Lot",
                            "corner_a": {"x": -1, "y": -1},
                            "corner_b": {"x": 5, "y": 3},
                        }
                    ],
                    "lines": [
                        {
                            "line_id": "line-1",
                            "start": {"x": 0, "y": 2},
                            "end": {"x": 4, "y": 2},
                            "line_type": "setback",
                            "layer": "SETBACK",
                        },
                        {
                            "line_id": "grid-a",
                            "start": {"x": 1, "y": 0},
                            "end": {"x": 1, "y": 4},
                            "line_type": "grid",
                            "layer": "GRID",
                            "grid_label": "A",
                            "grid_axis": "vertical",
                        },
                        {
                            "line_id": "grid-b",
                            "start": {"x": 4, "y": 0},
                            "end": {"x": 4, "y": 4},
                            "line_type": "grid",
                            "layer": "GRID",
                            "grid_label": "B",
                            "grid_axis": "vertical",
                        }
                    ],
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
                            "opening_id": "door-1",
                            "opening_type": "door",
                            "parent_wall_id": "w1",
                            "offset_m": 1,
                            "width_m": 0.9,
                            "swing_direction": "ccw",
                        },
                        {
                            "opening_id": "window-1",
                            "opening_type": "window",
                            "parent_wall_id": "w1",
                            "offset_m": 2.6,
                            "width_m": 1.0,
                        }
                    ],
                    "rooms": [
                        {
                            "room_id": "room-1",
                            "name": "Waiting Area",
                            "room_type": "waiting",
                            "label": {"x": 2, "y": 1.5},
                        }
                    ],
                    "dimensions": [
                        {
                            "dimension_id": "dim-1",
                            "basis": "outside_face",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "offset_m": 0.5,
                        }
                    ],
                }
            ],
        }
    )

    svg = export_project_svg(project)

    assert "<svg" in svg
    assert "Clinic Draft" in svg
    assert 'id="lot-1"' in svg
    assert 'data-entity-type="lot-area"' in svg
    assert "<circle" in svg
    assert 'id="walls"' in svg
    assert 'data-entity-type="wall-solid"' in svg
    assert 'id="wall-joints"' in svg
    assert 'id="openings" fill="none" stroke-linecap="butt"' in svg
    assert 'id="line-1"' in svg
    assert 'data-entity-type="draft-line"' in svg
    assert 'data-line-type="setback"' in svg
    assert 'data-layer="SETBACK"' in svg
    assert 'id="grid-a"' in svg
    assert 'data-grid-label="A"' in svg
    assert 'data-grid-axis="vertical"' in svg
    assert 'data-entity-type="grid-label"' in svg
    assert 'data-entity-type="grid-dimension"' in svg
    assert 'id="w1"' in svg
    assert 'data-wall-type="exterior"' in svg
    assert 'id="door-1"' in svg
    assert 'data-door-swing="ccw"' in svg
    assert 'id="window-1-panel-1"' in svg
    assert 'id="window-1-panel-2"' in svg
    assert 'data-opening-type="window"' in svg
    assert 'data-window-panel="1"' in svg
    assert 'data-window-panel="2"' in svg
    assert 'data-wall-thickness-mm="150"' in svg
    assert "Waiting Area" in svg
    assert "4.00 m" in svg
    assert 'id="dim-1"' in svg
    assert 'data-dimension-basis="outside_face"' in svg


def test_export_project_svg_draws_wall_joint_solids_for_orthogonal_corners() -> None:
    project = CadProject.model_validate(
        {
            "project": {"name": "Joined Walls"},
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w-horizontal",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 2, "y": 0},
                            "wall_type": "exterior",
                        },
                        {
                            "wall_id": "w-vertical",
                            "start": {"x": 2, "y": 0},
                            "end": {"x": 2, "y": 2},
                            "wall_type": "exterior",
                        },
                    ],
                    "openings": [],
                }
            ],
        }
    )

    svg = export_project_svg(project)

    assert 'id="wall-joints"' in svg
    assert 'data-entity-type="wall-joint"' in svg
    assert 'data-wall-ids="w-horizontal w-vertical"' in svg


def test_export_project_svg_draws_explicit_door_gap_without_parent_wall() -> None:
    project = CadProject.model_validate(
        {
            "project": {"name": "Door Gap"},
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w-left",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 1, "y": 0},
                            "wall_type": "interior",
                        },
                        {
                            "wall_id": "w-right",
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
                            "swing_direction": "cw",
                        }
                    ],
                }
            ],
        }
    )

    svg = export_project_svg(project)

    assert 'id="door-gap"' in svg
    assert 'data-door-swing="cw"' in svg
    assert 'data-hinge-side="start"' in svg
    assert svg.count("<polygon") >= 3
    assert "<circle" not in svg


def test_export_project_svg_honors_door_hinge_side_and_style_overrides() -> None:
    project = CadProject.model_validate(
        {
            "project": {"name": "Door Overrides"},
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w-left",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 1, "y": 0},
                            "wall_type": "interior",
                        },
                        {
                            "wall_id": "w-right",
                            "start": {"x": 1.9, "y": 0},
                            "end": {"x": 4, "y": 0},
                            "wall_type": "interior",
                        },
                    ],
                    "openings": [
                        {
                            "opening_id": "door-hinge-end",
                            "opening_type": "door",
                            "start": {"x": 1, "y": 0},
                            "end": {"x": 1.9, "y": 0},
                            "offset_m": 0,
                            "width_m": 0.9,
                            "wall_thickness_mm": 100,
                            "swing_direction": "cw",
                            "hinge_side": "end",
                            "frame_jamb_mm": 75,
                            "leaf_thickness_mm": 60,
                        }
                    ],
                }
            ],
        }
    )

    svg = export_project_svg(project)

    assert 'data-hinge-side="end"' in svg
    assert 'data-door-swing="cw"' in svg
