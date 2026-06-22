import json
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "abscissa_ci" / "cad" / "static"


def test_cad_static_app_exposes_required_command_aliases() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    for command in [
        "LOT",
        "LINE",
        "WALL",
        "RECTWALL",
        "CONVERT",
        "DOOR",
        "WINDOW",
        "ROOM",
        "DIM",
        "MOVE",
        "COPY",
        "TRIM",
        "EXTEND",
        "ROTATE",
        "ERASE",
        "UNDO",
        "REDO",
        "SAVE",
        "OPEN",
        "EXPORT",
    ]:
        assert f"{command}:" in app_js


def test_cad_static_app_keeps_metric_defaults_visible() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert "exteriorWallThicknessMm: 150" in app_js
    assert "interiorWallThicknessMm: 100" in app_js
    assert "Exterior - 150 mm" in index_html
    assert "Interior - 100 mm" in index_html


def test_cad_static_app_exposes_snap_coordinates_and_window_selection() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert "nearestSnapEndpoint" in app_js
    assert "finishSelectionDrag" in app_js
    assert "Crossing" in app_js
    assert "Window" in app_js
    assert 'id="coordinateReadout"' in index_html
    assert 'id="lineCount"' in index_html


def test_cad_static_app_exposes_lot_area_tool_and_command_echo() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="commandEcho"' in index_html
    assert 'data-command="LOT"' in index_html
    assert 'id="lotCount"' in index_html
    assert "addLotArea" in app_js
    assert "drawLots" in app_js
    assert "Command: ${toolCommandName(nextTool)}" in app_js


def test_cad_static_app_exposes_rectangle_wall_command() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'data-command="RW"' in index_html
    assert 'data-shortcut="RW"' in index_html
    assert 'RW: "rectangle-wall"' in app_js
    assert 'RECTWALL: "rectangle-wall"' in app_js
    assert "addRectangleWalls" in app_js
    assert "drawRectangleWallPreview" in app_js
    assert "rectangleSegments" in app_js


def test_cad_static_tool_shortcuts_are_visible_on_hover() -> None:
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert 'data-shortcut="L"' in index_html
    assert 'title="Shortcut: L"' in index_html
    assert "content: attr(data-shortcut)" in style_css
    assert ".tool:hover::after" in style_css
    assert ".tool:focus-visible::after" in style_css


def test_cad_static_app_draws_bottom_left_axis_indicator() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "drawAxisIndicator" in app_js
    assert "drawAxisArrow" in app_js
    assert 'ctx.fillText("X"' in app_js
    assert 'ctx.fillText("Y"' in app_js


def test_cad_static_app_uses_three_click_dimension_placement() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "dimensionMeasureEnd" in app_js
    assert "dimensionOffsetFromPlacement" in app_js
    assert "dimensionDisplayPoints" in app_js
    assert "click to place the dimension line" in app_js


def test_cad_static_app_rotates_doors_and_handles_keyboard_tool_shortcuts() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'data-command="ROTATE"' in index_html
    assert "rotateSelectedDoor" in app_js
    assert "doorSwingGeometry" in app_js
    assert "drawDoorFrame" in app_js
    assert "drawDoorJamb" in app_js
    assert "jambLength" in app_js
    assert "drawDoorSwingArrow" in app_js
    assert "doorStyle.colors.frame_fill" in app_js
    assert 'ctx.lineCap = "butt"' in app_js
    assert "doorLeafWidthForWall" in app_js
    assert "doorOpeningWidthForWall" in app_js
    assert "doorLeafWidthForWall(wall) + 2 * doorJambMeters(null)" in app_js
    assert "const hingeCornerOffset = frameDepth / 2" in app_js
    assert "const leafThickness = doorLeafThicknessPx(opening)" in app_js
    assert "const halfLeaf = doorLeafThicknessPx(opening)" not in app_js
    assert "Math.min(wallLength - width, hit.offset)" in app_js
    assert "doorFrameSnapPoints" in app_js
    assert "doorOpeningCenterlineEndpointKeys" in app_js
    assert 'type: "door-jamb"' in app_js
    assert "!suppressedWallEndpointKeys.has(pointKey(wall.start))" in app_js
    assert "executeCommand(command)" in app_js


def test_cad_static_shares_a_single_door_style_source() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    style_json = json.loads((STATIC_DIR / "door_style.json").read_text(encoding="utf-8"))

    assert style_json["frame_jamb_mm"] == 50
    assert style_json["leaf_width_mm"] == {"exterior": 900, "interior": 800}
    assert 'fetch("/door_style.json")' in app_js
    assert "getDoorStyle" in app_js
    assert 'id="doorProperties"' in index_html


def test_cad_static_exposes_editable_door_properties_panel() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    for input_id in ["doorJamb", "doorLeafThickness", "doorSwing", "doorHingeSide", "doorLeafWidth"]:
        assert f'id="{input_id}"' in index_html

    assert "syncDoorPanel" in app_js
    assert "applyDoorEdit" in app_js
    assert "door.frame_jamb_mm" in app_js
    assert "door.leaf_thickness_mm" in app_js
    assert "door.hinge_side" in app_js


def test_cad_static_app_applies_commands_to_existing_selection_and_esc_deselects() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'ESC: "deselect"' in app_js
    assert "function deselect()" in app_js
    assert 'setStatus("Selection cleared.")' in app_js
    assert 'action === "erase" && selected' in app_js
    assert "removeSelectedItems()" in app_js
    assert 'event.key === "Escape"' in app_js


def test_cad_static_app_exposes_trim_tool_and_two_letter_shortcut() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'data-command="TR"' in index_html
    assert "TR: \"trim\"" in app_js
    assert "TRIM: \"trim\"" in app_js
    assert "trimAt(point)" in app_js
    assert "trimIntersections" in app_js
    assert "queueKeyboardCommand" in app_js


def test_cad_static_app_exposes_extend_tool_and_door_wall_gap_behavior() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'data-command="EX"' in index_html
    assert "EX: \"extend\"" in app_js
    assert "EXTEND: \"extend\"" in app_js
    assert "extendAt(point)" in app_js
    assert "nearestExtension" in app_js
    assert "splitWallAroundOpening" in app_js
    assert "Door placed and wall segment removed." in app_js
