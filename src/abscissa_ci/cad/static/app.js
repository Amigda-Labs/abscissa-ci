(function () {
  "use strict";

  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");
  const commandEcho = document.getElementById("commandEcho");
  const commandLine = document.getElementById("commandLine");
  const wallTypeEl = document.getElementById("wallType");
  const dimensionBasisEl = document.getElementById("dimensionBasis");
  const roomNameEl = document.getElementById("roomName");
  const roomTypeEl = document.getElementById("roomType");
  const coordinateReadout = document.getElementById("coordinateReadout");
  const fileInput = document.getElementById("fileInput");
  const doorPanel = document.getElementById("doorProperties");
  const doorLeafWidthEl = document.getElementById("doorLeafWidth");
  const doorJambEl = document.getElementById("doorJamb");
  const doorLeafThicknessEl = document.getElementById("doorLeafThickness");
  const doorSwingEl = document.getElementById("doorSwing");
  const doorHingeSideEl = document.getElementById("doorHingeSide");
  const lotWidthEl = document.getElementById("lotWidth");
  const lotDepthEl = document.getElementById("lotDepth");
  const setbackFrontEl = document.getElementById("setbackFront");
  const setbackRearEl = document.getElementById("setbackRear");
  const setbackLeftEl = document.getElementById("setbackLeft");
  const setbackRightEl = document.getElementById("setbackRight");
  const gridXSpacingsEl = document.getElementById("gridXSpacings");
  const gridYSpacingsEl = document.getElementById("gridYSpacings");
  const createLotButton = document.getElementById("createLotButton");
  const createSetbackButton = document.getElementById("createSetbackButton");
  const createGridButton = document.getElementById("createGridButton");
  const createWallCenterlineButton = document.getElementById("createWallCenterlineButton");

  // Single source of truth for door visuals, mirrored from static/door_style.json.
  // The same JSON is read by the SVG exporter (cad/door_style.py) so the canvas
  // and exported drawings cannot drift apart. These inline values are only a
  // fallback for when the fetch has not resolved yet.
  let doorStyle = {
    frame_jamb_mm: 50,
    leaf_thickness_mm: 45,
    leaf_width_mm: { exterior: 900, interior: 800 },
    swing: { default_direction: "cw", default_hinge_side: "start" },
    leaf_thickness_px_min: 5,
    leaf_thickness_px_max: 12,
    jamb_px_min: 3,
    colors: {
      frame_fill: "#ffffff",
      frame_stroke: "#111827",
      leaf_fill: "#ffffff",
      leaf_fill_selected: "#fff7ed",
      leaf_stroke: "#111827",
      swing_stroke: "#64748b",
      selected: "#f97316",
    },
  };
  let lastDoorPanelId = null;

  const commandAliases = {
    SELECT: "select",
    ESC: "deselect",
    DESELECT: "deselect",
    LOT: "lot",
    LOTAREA: "lot",
    LA: "lot",
    SETBACK: "setback",
    SB: "setback",
    GRID: "grid",
    XLINE: "grid",
    WCL: "wall-centerline",
    WALLCL: "wall-centerline",
    L: "line",
    LINE: "line",
    W: "wall",
    WALL: "wall",
    REC: "rectangle",
    RECT: "rectangle",
    RECTANGLE: "rectangle",
    RW: "rectangle-wall",
    RECTWALL: "rectangle-wall",
    RECTANGLEWALL: "rectangle-wall",
    CONVERT: "convert-line-to-wall",
    TOWALL: "convert-line-to-wall",
    CONVERTWALL: "convert-line-to-wall",
    D: "door",
    DOOR: "door",
    WIN: "window",
    WINDOW: "window",
    ROOM: "room",
    R: "room",
    DIM: "dimension",
    DIMENSION: "dimension",
    P: "pan",
    PAN: "pan",
    M: "move",
    MOVE: "move",
    C: "copy",
    COPY: "copy",
    RO: "rotate-door",
    ROTATE: "rotate-door",
    TR: "trim",
    TRIM: "trim",
    EX: "extend",
    EXTEND: "extend",
    E: "erase",
    ERASE: "erase",
    DEL: "erase",
    DELETE: "erase",
    U: "undo",
    UNDO: "undo",
    REDO: "redo",
    SAVE: "save",
    OPEN: "open",
    EXPORT: "export-svg",
    SVG: "export-svg",
    PNG: "export-png",
  };

  const defaults = {
    exteriorWallThicknessMm: 150,
    interiorWallThicknessMm: 100,
    doorWidthM: 0.9,
    windowWidthM: 1.2,
    gridSizeM: 0.25,
  };
  const gridAnnotation = {
    labelOffsetM: 1.1,
    dimensionOffsetM: 0.55,
  };

  let project = createDefaultProject();
  let tool = "select";
  let selected = null;
  let selectedItems = [];
  let lotStart = null;
  let lineStart = null;
  let wallStart = null;
  let rectangleStart = null;
  let rectangleWallStart = null;
  let dimensionStart = null;
  let dimensionMeasureEnd = null;
  let moveAnchor = null;
  let hoverPoint = null;
  let snapCandidate = null;
  let isPanning = false;
  let panAnchor = null;
  let selectionDrag = null;
  let view = { x: 80, y: 80, scale: 80 };
  let undoStack = [];
  let redoStack = [];
  let keyboardCommandBuffer = "";
  let keyboardCommandTimer = null;

  function createDefaultProject() {
    return {
      schema_version: "abscissa-cad-v1",
      project: {
        name: "Untitled Abscissa Plan",
        units: { length: "m", wall_thickness: "mm" },
        grid_size_m: defaults.gridSizeM,
        defaults: {
          exterior_wall_thickness_mm: defaults.exteriorWallThicknessMm,
          interior_wall_thickness_mm: defaults.interiorWallThicknessMm,
          door_width_m: defaults.doorWidthM,
          window_width_m: defaults.windowWidthM,
        },
      },
      levels: [
        {
          level_id: "level-1",
          name: "Ground Floor",
          lots: [],
          lines: [],
          walls: [],
          openings: [],
          rooms: [],
          dimensions: [],
        },
      ],
    };
  }

  function activeLevel() {
    return project.levels[0];
  }

  function setStatus(message) {
    statusEl.textContent = message;
  }

  function uid(prefix) {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function remember() {
    undoStack.push(clone(project));
    if (undoStack.length > 80) undoStack.shift();
    redoStack = [];
  }

  function undo() {
    if (!undoStack.length) {
      setStatus("Nothing to undo.");
      return;
    }
    redoStack.push(clone(project));
    project = undoStack.pop();
    clearTransient();
    draw();
    setStatus("Undo.");
  }

  function redo() {
    if (!redoStack.length) {
      setStatus("Nothing to redo.");
      return;
    }
    undoStack.push(clone(project));
    project = redoStack.pop();
    clearTransient();
    draw();
    setStatus("Redo.");
  }

  function setTool(nextTool) {
    tool = nextTool;
    lotStart = null;
    lineStart = null;
    wallStart = null;
    rectangleStart = null;
    rectangleWallStart = null;
    dimensionStart = null;
    dimensionMeasureEnd = null;
    moveAnchor = null;
    selectionDrag = null;
    resetCommandLinePrompt();
    updateToolButtons();
    const labels = {
      select: "Select: click, or drag left-to-right for window select and right-to-left for crossing select.",
      lot: "LOT: click first corner, then click opposite corner for a rectangular lot area.",
      line: "Line: click start, then click end. Lines snap to grid/endpoints and stay orthogonal.",
      wall: "Wall: click start, then click end. Walls snap to grid and stay orthogonal.",
      rectangle: "Rectangle: click first corner, then click opposite corner or type width,height such as 5,8.",
      "rectangle-wall": "Rectangle wall: click first corner, then click opposite corner to create four walls.",
      door: "Door: click a wall to place a door. Exterior doors are 0.90 m; interior doors are 0.80 m. Select a door and use ROTATE to flip its swing.",
      window: "Window: click a wall to place a 1.20 m window.",
      room: "Room: click to place a room label.",
      dimension: () => `Dimension (${dimensionBasisLabel()}): click first endpoint, click second endpoint, then click to place the dimension line.`,
      pan: "Pan: drag anywhere on the board to move the view. Middle mouse, Shift-drag, and Space-drag also pan.",
      move: "Move: select an item, then click a new anchor point.",
      copy: "Copy: select an item, then click a new anchor point.",
      trim: "TRIM: click a draft line or wall near the end to remove up to the nearest crossing line or wall.",
      extend: "EXTEND: click a draft line or wall near the end to extend to the nearest crossing line or wall.",
      erase: "Erase: click an item to remove it.",
    };
    commandEcho.textContent = `Command: ${toolCommandName(nextTool)}`;
    const label = labels[nextTool];
    setStatus(typeof label === "function" ? label() : label || "Ready.");
    draw();
  }

  function toolCommandName(nextTool) {
    const names = {
      select: "SELECT",
      lot: "LOT",
      line: "LINE",
      wall: "WALL",
      rectangle: "REC",
      "rectangle-wall": "RECTWALL",
      door: "DOOR",
      window: "WINDOW",
      room: "ROOM",
      dimension: "DIM",
      pan: "PAN",
      move: "MOVE",
      copy: "COPY",
      trim: "TRIM",
      extend: "EXTEND",
      erase: "ERASE",
    };
    return names[nextTool] || nextTool.toUpperCase();
  }

  function updateToolButtons() {
    document.querySelectorAll("[data-command]").forEach((button) => {
      const action = commandAliases[button.dataset.command.toUpperCase()];
      button.classList.toggle("active", action === tool);
    });
    updateBoardCursor();
  }

  function updateBoardCursor() {
    canvas.classList.toggle("pan-tool", tool === "pan");
    canvas.classList.toggle("panning", isPanning);
  }

  function clearTransient() {
    selected = null;
    selectedItems = [];
    lotStart = null;
    lineStart = null;
    wallStart = null;
    rectangleStart = null;
    rectangleWallStart = null;
    dimensionStart = null;
    dimensionMeasureEnd = null;
    moveAnchor = null;
    selectionDrag = null;
    resetCommandLinePrompt();
  }

  function deselect() {
    clearTimeout(keyboardCommandTimer);
    keyboardCommandBuffer = "";
    clearTransient();
    setTool("select");
    setStatus("Selection cleared.");
  }

  function executeCommand(rawCommand) {
    const command = String(rawCommand || "").trim().toUpperCase();
    if (!command) return;
    const action = commandAliases[command];
    if (!action) {
      setStatus(`Unknown command: ${command}`);
      return;
    }
    if (action === "deselect") {
      deselect();
    } else if (action === "erase" && selected) {
      removeSelectedItems();
    } else if (action === "setback") {
      createSetbackFromInputs();
    } else if (action === "grid") {
      createGridFromInputs();
    } else if (action === "wall-centerline") {
      createWallCenterlineFromReference();
    } else if (["select", "lot", "line", "wall", "rectangle", "rectangle-wall", "door", "window", "room", "dimension", "pan", "move", "copy", "trim", "extend", "erase"].includes(action)) {
      setTool(action);
    } else if (action === "convert-line-to-wall") {
      convertSelectedLinesToWalls();
    } else if (action === "rotate-door") {
      rotateSelectedDoor();
    } else if (action === "undo") {
      undo();
    } else if (action === "redo") {
      redo();
    } else if (action === "save") {
      downloadJson();
    } else if (action === "open") {
      fileInput.click();
    } else if (action === "export-svg") {
      exportSvg();
    } else if (action === "export-png") {
      exportPng();
    }
  }

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function screenToWorld(screenX, screenY) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (screenX - rect.left - view.x) / view.scale,
      y: (screenY - rect.top - view.y) / view.scale,
    };
  }

  function worldToScreen(point) {
    return {
      x: point.x * view.scale + view.x,
      y: point.y * view.scale + view.y,
    };
  }

  function snapPoint(point) {
    const endpoint = nearestSnapEndpoint(point);
    if (endpoint) return clone(endpoint.point);
    const grid = project.project.grid_size_m || defaults.gridSizeM;
    return {
      x: Math.round(point.x / grid) * grid,
      y: Math.round(point.y / grid) * grid,
    };
  }

  function orthogonalPoint(start, end) {
    const dx = Math.abs(end.x - start.x);
    const dy = Math.abs(end.y - start.y);
    return dx >= dy ? { x: end.x, y: start.y } : { x: start.x, y: end.y };
  }

  function wallThicknessMm(wallType) {
    const projectDefaults = project.project.defaults || {};
    return wallType === "exterior"
      ? projectDefaults.exterior_wall_thickness_mm || defaults.exteriorWallThicknessMm
      : projectDefaults.interior_wall_thickness_mm || defaults.interiorWallThicknessMm;
  }

  function addWall(start, end) {
    if (samePoint(start, end)) {
      setStatus("Wall ignored: start and end are the same.");
      return;
    }
    remember();
    const wallType = wallTypeEl.value;
    activeLevel().walls.push({
      wall_id: uid("wall"),
      start,
      end,
      wall_type: wallType,
      thickness_mm: wallThicknessMm(wallType),
      exterior: wallType === "exterior",
    });
    setStatus(`${wallType} wall added.`);
    updateStats();
    draw();
  }

  function addRectangleWalls(cornerA, cornerB) {
    if (samePoint(cornerA, cornerB) || Math.abs(cornerA.x - cornerB.x) < 1e-9 || Math.abs(cornerA.y - cornerB.y) < 1e-9) {
      setStatus("Rectangle wall ignored: rectangle needs width and depth.");
      return;
    }

    remember();
    const wallType = wallTypeEl.value;
    const thicknessMm = wallThicknessMm(wallType);
    const walls = rectangleSegments(cornerA, cornerB).map((segment) => ({
      wall_id: uid("wall"),
      start: segment.start,
      end: segment.end,
      wall_type: wallType,
      thickness_mm: thicknessMm,
      exterior: wallType === "exterior",
    }));
    activeLevel().walls.push(...walls);
    selectedItems = walls.map((wall) => ({ type: "wall", item: wall }));
    selected = selectedItems[0] || null;
    setStatus(`${wallType} rectangle wall added: ${formatArea(cornerA, cornerB)}.`);
    updateStats();
    draw();
  }

  function addRectangleLines(cornerA, cornerB) {
    if (samePoint(cornerA, cornerB) || Math.abs(cornerA.x - cornerB.x) < 1e-9 || Math.abs(cornerA.y - cornerB.y) < 1e-9) {
      setStatus("Rectangle ignored: rectangle needs width and depth.");
      return;
    }

    remember();
    const lines = rectangleSegments(cornerA, cornerB).map((segment) => makeDraftLine(segment.start, segment.end));
    activeLevel().lines.push(...lines);
    selectedItems = lines.map((draftLine) => ({ type: "line", item: draftLine }));
    selected = selectedItems[0] || null;
    setStatus(`Draft rectangle added: ${formatRectangleSize(cornerA, cornerB)}.`);
    updateStats();
    draw();
  }

  function addLine(start, end) {
    if (samePoint(start, end)) {
      setStatus("Line ignored: start and end are the same.");
      return;
    }
    remember();
    activeLevel().lines.push(makeDraftLine(start, end));
    setStatus("Draft line added.");
    updateStats();
    draw();
  }

  function makeDraftLine(start, end, lineType = "draft", layer = "DRAFT_LINE", options = {}) {
    return {
      line_id: uid("line"),
      start: clone(start),
      end: clone(end),
      line_type: lineType,
      layer,
      grid_label: options.gridLabel || null,
      grid_axis: options.gridAxis || null,
    };
  }

  function addLotArea(cornerA, cornerB) {
    if (samePoint(cornerA, cornerB) || Math.abs(cornerA.x - cornerB.x) < 1e-9 || Math.abs(cornerA.y - cornerB.y) < 1e-9) {
      setStatus("Lot area ignored: rectangular lot needs width and depth.");
      return;
    }
    remember();
    const lot = {
      lot_id: uid("lot"),
      name: "Lot Area",
      corner_a: cornerA,
      corner_b: cornerB,
      boundary_thickness_mm: 35,
      dash_pattern: "lot_boundary_dash_circle",
    };
    activeLevel().lots.push(lot);
    selected = { type: "lot", item: lot };
    selectedItems = [selected];
    setStatus(`Lot area added: ${formatArea(cornerA, cornerB)}.`);
    updateStats();
    draw();
  }

  function createLotFromInputs() {
    const dimensions = readWidthDepthInputs(lotWidthEl, lotDepthEl);
    if (!dimensions) {
      setStatus("Lot needs positive width and depth in meters.");
      return;
    }
    createLotFromDimensions(dimensions.width, dimensions.depth);
  }

  function createLotFromDimensions(width, depth) {
    if (!Number.isFinite(width) || !Number.isFinite(depth) || width <= 0 || depth <= 0) {
      setStatus("Type lot dimensions as width,depth in meters, for example LOT 10,15.");
      return;
    }
    addLotArea({ x: 0, y: 0 }, { x: roundM(width), y: roundM(depth) });
  }

  function createSetbackFromInputs() {
    const setbacks = readSetbackInputs();
    if (!setbacks) {
      setStatus("Setbacks need non-negative front,rear,left,right values in meters.");
      return;
    }
    createSetbackLines(setbacks);
  }

  function createSetbackLines(setbacks) {
    const bounds = selectedLotBounds() || latestLotBounds();
    if (!bounds) {
      setStatus("Create or select a lot before creating setbacks.");
      return;
    }
    const inner = {
      minX: roundM(bounds.minX + setbacks.left),
      minY: roundM(bounds.minY + setbacks.rear),
      maxX: roundM(bounds.maxX - setbacks.right),
      maxY: roundM(bounds.maxY - setbacks.front),
    };
    if (inner.minX >= inner.maxX || inner.minY >= inner.maxY) {
      setStatus("Setbacks are larger than the selected lot.");
      return;
    }
    addGuideRectangle(inner, "setback", "SETBACK", `Setback created: ${formatRectangleBounds(inner)} buildable area.`);
  }

  function createGridFromInputs() {
    const xSpacings = parseSpacingList(gridXSpacingsEl.value);
    const ySpacings = parseSpacingList(gridYSpacingsEl.value);
    if (!xSpacings.length || !ySpacings.length) {
      setStatus("Grid needs X and Y target bay values or spacing lists, for example 4 and 4.");
      return;
    }
    createGridLines(xSpacings, ySpacings);
  }

  function createGridLines(xSpacings, ySpacings) {
    const bounds = latestGuideRectangleBounds("setback") || selectedLotBounds() || latestLotBounds();
    if (!bounds) {
      setStatus("Create a lot or setback before creating a grid.");
      return;
    }
    const width = bounds.maxX - bounds.minX;
    const depth = bounds.maxY - bounds.minY;
    const xPositions = structuralGridPositions(bounds.minX, bounds.maxX, xSpacings);
    const yPositions = structuralGridPositions(bounds.minY, bounds.maxY, ySpacings);
    const labels = gridLabelSets(xPositions.length, yPositions.length, width >= depth);
    const segments = [
      ...xPositions.map((x, index) => ({
        start: { x, y: bounds.minY },
        end: { x, y: bounds.maxY },
        gridLabel: labels.vertical[index],
        gridAxis: "vertical",
      })),
      ...yPositions.map((y, index) => ({
        start: { x: bounds.minX, y },
        end: { x: bounds.maxX, y },
        gridLabel: labels.horizontal[index],
        gridAxis: "horizontal",
      })),
    ];
    addGuideLines(
      segments,
      "grid",
      "GRID",
      `Structural grid added: ${labels.vertical.join(", ")} vertical and ${labels.horizontal.join(", ")} horizontal.`,
    );
  }

  function createWallCenterlineFromReference() {
    const bounds = latestGuideRectangleBounds("setback") || selectedLotBounds() || latestLotBounds();
    if (!bounds) {
      setStatus("Create a lot or setback before creating wall centerlines.");
      return;
    }
    addGuideRectangle(bounds, "wall_centerline", "WALL_CL", `Wall centerline rectangle added: ${formatRectangleBounds(bounds)}.`);
  }

  function addGuideRectangle(bounds, lineType, layer, message) {
    const cornerA = { x: bounds.minX, y: bounds.minY };
    const cornerB = { x: bounds.maxX, y: bounds.maxY };
    addGuideLines(rectangleSegments(cornerA, cornerB), lineType, layer, message);
  }

  function addGuideLines(segments, lineType, layer, message) {
    const validSegments = segments.filter((segment) => !samePoint(segment.start, segment.end));
    if (!validSegments.length) {
      setStatus("Guide ignored: no valid guide lines were created.");
      return;
    }
    remember();
    const lines = validSegments.map((segment) => makeDraftLine(segment.start, segment.end, lineType, layer, segment));
    activeLevel().lines.push(...lines);
    selectedItems = lines.map((draftLine) => ({ type: "line", item: draftLine }));
    selected = selectedItems[0] || null;
    setStatus(message);
    updateStats();
    draw();
  }

  function convertSelectedLinesToWalls() {
    const lineHits = selectedItems.filter((hit) => hit.type === "line");
    if (!lineHits.length && selected && selected.type === "line") {
      lineHits.push(selected);
    }
    if (!lineHits.length) {
      setStatus("Select one or more draft lines before converting to wall.");
      return;
    }

    remember();
    const level = activeLevel();
    const wallType = wallTypeEl.value;
    const selectedLineIds = new Set(lineHits.map((hit) => hit.item.line_id));
    const newWalls = lineHits.map((hit) => ({
      wall_id: uid("wall"),
      start: clone(hit.item.start),
      end: clone(hit.item.end),
      wall_type: wallType,
      thickness_mm: wallThicknessMm(wallType),
      exterior: wallType === "exterior",
    }));

    level.lines = level.lines.filter((lineItem) => !selectedLineIds.has(lineItem.line_id));
    level.walls.push(...newWalls);
    selectedItems = newWalls.map((wall) => ({ type: "wall", item: wall }));
    selected = selectedItems[0] || null;
    setStatus(`${newWalls.length} line${newWalls.length === 1 ? "" : "s"} converted to ${wallType} wall${newWalls.length === 1 ? "" : "s"}.`);
    updateStats();
    draw();
  }

  function addOpening(point, openingType) {
    const hit = nearestWall(point, 0.3);
    if (!hit) {
      setStatus(`No wall found for ${openingType}.`);
      return;
    }
    const width = openingType === "door"
      ? doorOpeningWidthForWall(hit.wall)
      : project.project.defaults.window_width_m;
    const wallLength = wallLengthM(hit.wall);
    if (wallLength < width) {
      setStatus(`${openingType} ignored: wall is shorter than ${width.toFixed(2)} m.`);
      return;
    }
    const offset = Math.max(0, Math.min(wallLength - width, hit.offset));
    const opening = {
      opening_id: uid(openingType),
      opening_type: openingType,
      parent_wall_id: hit.wall.wall_id,
      offset_m: roundM(offset),
      width_m: width,
      swing_direction: (doorStyle.swing && doorStyle.swing.default_direction) || "cw",
    };
    if (openingType === "door") {
      opening.hinge_side = (doorStyle.swing && doorStyle.swing.default_hinge_side) || "start";
    }
    if (openingType === "door") {
      const points = openingPoints(hit.wall, opening);
      opening.parent_wall_id = null;
      opening.start = points.start;
      opening.end = points.end;
      opening.wall_thickness_mm = hit.wall.thickness_mm;
      remember();
      splitWallAroundOpening(activeLevel(), hit.wall, points);
      activeLevel().openings.push(opening);
      selected = { type: "opening", item: opening };
      selectedItems = [selected];
      setStatus("Door placed and wall segment removed.");
      updateStats();
      draw();
      return;
    }
    remember();
    activeLevel().openings.push(opening);
    setStatus(`${openingType} placed on wall.`);
    updateStats();
    draw();
  }

  function doorLeafWidthForWall(wall) {
    const widths = doorStyle.leaf_width_mm || {};
    const mm = wall.wall_type === "exterior"
      ? widths.exterior ?? 900
      : widths.interior ?? 800;
    return mm / 1000;
  }

  function doorJambMeters(opening) {
    const mm = (opening && opening.frame_jamb_mm) || doorStyle.frame_jamb_mm || 50;
    return mm / 1000;
  }

  function doorOpeningWidthForWall(wall) {
    return doorLeafWidthForWall(wall) + 2 * doorJambMeters(null);
  }

  function doorLeafWidthMeters(opening) {
    return Math.max(0, opening.width_m - 2 * doorJambMeters(opening));
  }

  function doorJambLengthPx(opening) {
    return Math.max(doorStyle.jamb_px_min || 3, doorJambMeters(opening) * view.scale);
  }

  function doorLeafThicknessPx(opening) {
    const mm = (opening && opening.leaf_thickness_mm) || doorStyle.leaf_thickness_mm || 45;
    return Math.max(
      doorStyle.leaf_thickness_px_min || 5,
      Math.min(doorStyle.leaf_thickness_px_max || 12, (mm / 1000) * view.scale),
    );
  }

  function addRoom(point) {
    remember();
    activeLevel().rooms.push({
      room_id: uid("room"),
      name: roomNameEl.value.trim() || "Room",
      room_type: roomTypeEl.value,
      label: point,
      boundary_wall_ids: [],
    });
    setStatus("Room label added.");
    updateStats();
    draw();
  }

  function addDimension(start, end, placement) {
    if (samePoint(start, end)) {
      setStatus("Dimension ignored: start and end are the same.");
      return;
    }
    const basis = dimensionBasis();
    const resolved = resolveDimensionBasis(start, end, placement, basis);
    remember();
    const offsetM = dimensionOffsetFromPlacement(resolved.start, resolved.end, placement);
    activeLevel().dimensions.push({
      dimension_id: uid("dimension"),
      kind: "linear",
      basis,
      start: resolved.start,
      end: resolved.end,
      offset_m: offsetM,
      label: formatDistance(resolved.start, resolved.end),
      reference_ids: resolved.referenceIds,
    });
    setStatus(`${dimensionBasisLabel(basis)} dimension added.`);
    updateStats();
    draw();
  }

  function eraseAt(point) {
    const hit = hitTest(point);
    if (!hit) {
      setStatus("Nothing found to erase.");
      return;
    }
    remember();
    removeHit(hit);
    selected = null;
    selectedItems = [];
    updateStats();
    draw();
    setStatus("Erased selected item.");
  }

  function moveOrCopyTo(point, copyMode) {
    if (!selected) {
      const hit = hitTest(point);
      if (!hit) {
        setStatus(`${copyMode ? "Copy" : "Move"} needs a selected item.`);
        return;
      }
      setSelection([hit]);
      moveAnchor = point;
      setStatus(`${copyMode ? "Copy" : "Move"}: click destination point.`);
      return;
    }
    if (!moveAnchor) {
      moveAnchor = point;
      setStatus(`${copyMode ? "Copy" : "Move"}: click destination point.`);
      return;
    }
    const dx = point.x - moveAnchor.x;
    const dy = point.y - moveAnchor.y;
    remember();
    const hits = selectedItems.length ? selectedItems : [selected];
    if (copyMode) {
      hits.filter(Boolean).forEach((hit) => copyHit(hit, dx, dy));
    } else {
      hits.filter(Boolean).forEach((hit) => translateHit(hit, dx, dy));
    }
    clearTransient();
    updateStats();
    draw();
    setStatus(copyMode ? "Copied item." : "Moved item.");
  }

  function canvasPointer(event) {
    return snapPoint(screenToWorld(event.clientX, event.clientY));
  }

  function handlePrimaryClick(event) {
    const point = canvasPointer(event);
    if (tool === "lot") {
      if (!lotStart) {
        lotStart = point;
        setStatus("Lot first corner set. Click opposite corner.");
      } else {
        addLotArea(lotStart, point);
        lotStart = null;
      }
    } else if (tool === "line") {
      if (!lineStart) {
        lineStart = point;
        setStatus("Line start set. Click end point.");
      } else {
        addLine(lineStart, orthogonalPoint(lineStart, point));
        lineStart = null;
      }
    } else if (tool === "wall") {
      if (!wallStart) {
        wallStart = point;
        setStatus("Wall start set. Click end point.");
      } else {
        addWall(wallStart, orthogonalPoint(wallStart, point));
        wallStart = null;
      }
    } else if (tool === "rectangle") {
      if (!rectangleStart) {
        rectangleStart = point;
        promptRectangleDimensions("Rectangle first corner set. Click opposite corner or type width,height.");
      } else {
        addRectangleLines(rectangleStart, point);
        rectangleStart = null;
        resetCommandLinePrompt();
      }
    } else if (tool === "rectangle-wall") {
      if (!rectangleWallStart) {
        rectangleWallStart = point;
        promptRectangleDimensions("Rectangle wall first corner set. Click opposite corner or type width,height.");
      } else {
        addRectangleWalls(rectangleWallStart, point);
        rectangleWallStart = null;
        resetCommandLinePrompt();
      }
    } else if (tool === "door") {
      addOpening(point, "door");
    } else if (tool === "window") {
      addOpening(point, "window");
    } else if (tool === "room") {
      addRoom(point);
    } else if (tool === "dimension") {
      if (!dimensionStart) {
        dimensionStart = point;
        setStatus(`${dimensionBasisLabel()} dimension first endpoint set. Click second endpoint.`);
      } else if (!dimensionMeasureEnd) {
        const end = orthogonalPoint(dimensionStart, point);
        if (samePoint(dimensionStart, end)) {
          setStatus("Dimension second endpoint must be different from the first.");
          return;
        }
        dimensionMeasureEnd = end;
        setStatus(`${dimensionBasisLabel()} endpoints set. Move away and click to place the dimension line.`);
      } else {
        addDimension(dimensionStart, dimensionMeasureEnd, point);
        dimensionStart = null;
        dimensionMeasureEnd = null;
      }
    } else if (tool === "erase") {
      eraseAt(point);
    } else if (tool === "move") {
      moveOrCopyTo(point, false);
    } else if (tool === "copy") {
      moveOrCopyTo(point, true);
    } else if (tool === "trim") {
      trimAt(point);
    } else if (tool === "extend") {
      extendAt(point);
    } else {
      const hit = hitTest(point);
      setSelection(hit ? [hit] : []);
      setStatus(hit ? `${hit.type} selected.` : "Nothing selected.");
    }
  }

  function draw() {
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    drawGrid(rect.width, rect.height);
    drawLots();
    drawLines();
    drawGridColumnMarkers();
    drawGridDimensions();
    drawDimensions();
    drawWalls();
    drawOpenings();
    drawRooms();
    drawPreview();
    drawSelectionWindow();
    drawSnapMarker();
    drawAxisIndicator(rect.width, rect.height);
    updateStats();
    updateSelectionSummary();
  }

  function drawGrid(width, height) {
    const grid = project.project.grid_size_m || defaults.gridSizeM;
    const step = grid * view.scale;
    if (step < 8) return;
    const startX = view.x % step;
    const startY = view.y % step;
    ctx.save();
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    for (let x = startX; x < width; x += step) {
      line(x, 0, x, height);
    }
    for (let y = startY; y < height; y += step) {
      line(0, y, width, y);
    }
    ctx.restore();
  }

  function drawWalls() {
    activeLevel().walls.forEach((wall) => {
      drawWallSolid(wall, isSelected("wall", wall.wall_id));
    });
    drawWallJoints(activeLevel().walls);
  }

  function drawWallSolid(wall, selectedWall) {
    const polygon = wallSolidPolygon(wall);
    if (!polygon.length) return;
    ctx.save();
    fillWorldPolygon(
      polygon,
      wallFillColor(wall.wall_type),
      selectedWall ? "#f97316" : null,
      selectedWall ? 2 : 0,
    );
    ctx.restore();
  }

  function drawWallJoints(walls) {
    const suppressedKeys = doorOpeningCenterlineEndpointKeys(wallMap());
    wallJointPolygons(walls, suppressedKeys).forEach((joint) => {
      const selectedWall = joint.wallIds.some((wallId) => isSelected("wall", wallId));
      ctx.save();
      fillWorldPolygon(
        joint.points,
        wallFillColor(joint.wallType),
        selectedWall ? "#f97316" : null,
        selectedWall ? 2 : 0,
      );
      ctx.restore();
    });
  }

  function wallFillColor(wallType) {
    return wallType === "exterior" ? "#111827" : "#374151";
  }

  function drawLots() {
    activeLevel().lots.forEach((lot) => {
      drawLot(lot, isSelected("lot", lot.lot_id));
    });
  }

  function drawLot(lot, selectedLot) {
    const bounds = lotBounds(lot);
    const topLeft = worldToScreen({ x: bounds.minX, y: bounds.minY });
    const bottomRight = worldToScreen({ x: bounds.maxX, y: bounds.maxY });
    const width = bottomRight.x - topLeft.x;
    const height = bottomRight.y - topLeft.y;
    const corners = lotCorners(lot).map(worldToScreen);

    ctx.save();
    ctx.strokeStyle = selectedLot ? "#f97316" : "#0f766e";
    ctx.lineWidth = selectedLot ? 2 : Math.max(1, ((lot.boundary_thickness_mm || 35) / 1000) * view.scale);
    ctx.setLineDash([12, 6, 2, 6]);
    ctx.strokeRect(topLeft.x, topLeft.y, width, height);
    ctx.setLineDash([]);
    corners.forEach((corner) => {
      ctx.beginPath();
      ctx.arc(corner.x, corner.y, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = "#f8fafc";
      ctx.fill();
      ctx.strokeStyle = selectedLot ? "#f97316" : "#0f766e";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
    ctx.restore();
  }

  function drawLines() {
    activeLevel().lines.forEach((draftLine) => {
      const start = worldToScreen(draftLine.start);
      const end = worldToScreen(draftLine.end);
      const selectedLine = isSelected("line", draftLine.line_id);
      const style = draftLineStyle(draftLine.line_type);
      ctx.save();
      ctx.strokeStyle = selectedLine ? "#f97316" : style.stroke;
      ctx.lineWidth = selectedLine ? 2.5 : style.lineWidth;
      ctx.setLineDash(selectedLine ? [] : style.dash);
      line(start.x, start.y, end.x, end.y);
      ctx.restore();
      drawGridLineLabels(draftLine);
    });
  }

  function draftLineStyle(lineType) {
    if (lineType === "setback") return { stroke: "#0891b2", lineWidth: 1.25, dash: [8, 6] };
    if (lineType === "grid") return { stroke: "#94a3b8", lineWidth: 1, dash: [2, 7] };
    if (lineType === "wall_centerline") return { stroke: "#dc2626", lineWidth: 1.25, dash: [10, 4, 2, 4] };
    return { stroke: "#64748b", lineWidth: 1.5, dash: [7, 5] };
  }

  function drawGridLineLabels(draftLine) {
    if (draftLine.line_type !== "grid" || !draftLine.grid_label) return;
    const vertical = draftLine.grid_axis === "vertical" || Math.abs(draftLine.start.x - draftLine.end.x) < 1e-9;
    const minY = Math.min(draftLine.start.y, draftLine.end.y);
    const maxY = Math.max(draftLine.start.y, draftLine.end.y);
    const minX = Math.min(draftLine.start.x, draftLine.end.x);
    const maxX = Math.max(draftLine.start.x, draftLine.end.x);
    const labelPairs = vertical
      ? [
          {
            anchor: { x: draftLine.start.x, y: minY },
            label: { x: draftLine.start.x, y: minY - gridAnnotation.labelOffsetM },
          },
          {
            anchor: { x: draftLine.start.x, y: maxY },
            label: { x: draftLine.start.x, y: maxY + gridAnnotation.labelOffsetM },
          },
        ]
      : [
          {
            anchor: { x: minX, y: draftLine.start.y },
            label: { x: minX - gridAnnotation.labelOffsetM, y: draftLine.start.y },
          },
          {
            anchor: { x: maxX, y: draftLine.start.y },
            label: { x: maxX + gridAnnotation.labelOffsetM, y: draftLine.start.y },
          },
        ];
    labelPairs.forEach(({ anchor, label }) => {
      drawGridExtension(anchor, label);
      drawGridBubble(label, draftLine.grid_label);
    });
  }

  function drawGridExtension(anchor, labelPoint) {
    const start = worldToScreen(anchor);
    const end = worldToScreen(labelPoint);
    ctx.save();
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    line(start.x, start.y, end.x, end.y);
    ctx.restore();
  }

  function drawGridBubble(point, label) {
    const screen = worldToScreen(point);
    ctx.save();
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#0f172a";
    ctx.font = "11px Inter, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, screen.x, screen.y);
    ctx.restore();
  }

  function drawGridColumnMarkers() {
    const gridLines = activeLevel().lines.filter((draftLine) => draftLine.line_type === "grid");
    const { vertical, horizontal } = gridLineGroups(gridLines);
    if (!vertical.length || !horizontal.length) return;
    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.14)";
    ctx.strokeStyle = "rgba(15, 23, 42, 0.35)";
    ctx.lineWidth = 1;
    vertical.forEach((vLine) => {
      horizontal.forEach((hLine) => {
        const point = { x: vLine.start.x, y: hLine.start.y };
        if (!pointOnSegment(point, vLine.start, vLine.end) || !pointOnSegment(point, hLine.start, hLine.end)) return;
        const screen = worldToScreen(point);
        const size = Math.max(5, Math.min(12, 0.18 * view.scale));
        ctx.fillRect(screen.x - size / 2, screen.y - size / 2, size, size);
        ctx.strokeRect(screen.x - size / 2, screen.y - size / 2, size, size);
      });
    });
    ctx.restore();
  }

  function drawGridDimensions() {
    const { vertical, horizontal } = gridLineGroups(activeLevel().lines.filter((draftLine) => draftLine.line_type === "grid"));
    if (!vertical.length && !horizontal.length) return;
    const bounds = gridAnnotationBounds(vertical, horizontal);
    if (!bounds) return;
    if (vertical.length > 1) {
      drawHorizontalGridDimensionChain(vertical, bounds.minY - gridAnnotation.dimensionOffsetM);
    }
    if (horizontal.length > 1) {
      drawVerticalGridDimensionChain(horizontal, bounds.minX - gridAnnotation.dimensionOffsetM);
    }
  }

  function drawHorizontalGridDimensionChain(verticalLines, y) {
    const points = verticalLines.map((draftLine) => ({ x: draftLine.start.x, y }));
    ctx.save();
    ctx.strokeStyle = "#475569";
    ctx.fillStyle = "#334155";
    ctx.lineWidth = 1;
    ctx.font = "11px Inter, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    for (let index = 0; index < points.length - 1; index += 1) {
      const start = worldToScreen(points[index]);
      const end = worldToScreen(points[index + 1]);
      line(start.x, start.y, end.x, end.y);
      drawGridDimensionTick(start, true);
      drawGridDimensionTick(end, true);
      const distanceM = Math.abs(points[index + 1].x - points[index].x);
      ctx.fillText(`${distanceM.toFixed(2)} m`, (start.x + end.x) / 2, start.y - 5);
    }
    ctx.restore();
  }

  function drawVerticalGridDimensionChain(horizontalLines, x) {
    const points = horizontalLines.map((draftLine) => ({ x, y: draftLine.start.y }));
    ctx.save();
    ctx.strokeStyle = "#475569";
    ctx.fillStyle = "#334155";
    ctx.lineWidth = 1;
    ctx.font = "11px Inter, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    for (let index = 0; index < points.length - 1; index += 1) {
      const start = worldToScreen(points[index]);
      const end = worldToScreen(points[index + 1]);
      line(start.x, start.y, end.x, end.y);
      drawGridDimensionTick(start, false);
      drawGridDimensionTick(end, false);
      const distanceM = Math.abs(points[index + 1].y - points[index].y);
      ctx.save();
      ctx.translate(start.x - 5, (start.y + end.y) / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(`${distanceM.toFixed(2)} m`, 0, 0);
      ctx.restore();
    }
    ctx.restore();
  }

  function drawGridDimensionTick(point, horizontal) {
    const half = 4;
    if (horizontal) {
      line(point.x, point.y - half, point.x, point.y + half);
    } else {
      line(point.x - half, point.y, point.x + half, point.y);
    }
  }

  function gridLineGroups(gridLines) {
    return {
      vertical: uniqueGridLines(
        gridLines.filter((draftLine) => draftLine.grid_axis === "vertical" || Math.abs(draftLine.start.x - draftLine.end.x) < 1e-9),
        "x",
      ),
      horizontal: uniqueGridLines(
        gridLines.filter((draftLine) => draftLine.grid_axis === "horizontal" || Math.abs(draftLine.start.y - draftLine.end.y) < 1e-9),
        "y",
      ),
    };
  }

  function uniqueGridLines(gridLines, axis) {
    const byCoordinate = new Map();
    gridLines.forEach((draftLine) => {
      const coordinate = axis === "x" ? draftLine.start.x : draftLine.start.y;
      byCoordinate.set(roundM(coordinate), draftLine);
    });
    return Array.from(byCoordinate.values()).sort((a, b) => (
      axis === "x" ? a.start.x - b.start.x : a.start.y - b.start.y
    ));
  }

  function gridAnnotationBounds(verticalLines, horizontalLines) {
    const points = [
      ...verticalLines.flatMap((draftLine) => [draftLine.start, draftLine.end]),
      ...horizontalLines.flatMap((draftLine) => [draftLine.start, draftLine.end]),
    ];
    if (!points.length) return null;
    return {
      minX: Math.min(...points.map((point) => point.x)),
      minY: Math.min(...points.map((point) => point.y)),
      maxX: Math.max(...points.map((point) => point.x)),
      maxY: Math.max(...points.map((point) => point.y)),
    };
  }

  function drawOpenings() {
    const walls = wallMap();
    activeLevel().openings.forEach((opening) => {
      const geometry = openingGeometry(opening, walls);
      if (!geometry) return;
      const points = geometry.points;
      const start = worldToScreen(points.start);
      const end = worldToScreen(points.end);
      const selectedOpening = isSelected("opening", opening.opening_id);
      ctx.save();
      if (opening.opening_type === "door") {
        drawDoorFrame(opening, start, end, geometry.thicknessMm, selectedOpening);
        drawDoorSwing(opening, walls, selectedOpening);
      } else {
        drawWindowFrame(start, end, geometry.thicknessMm, selectedOpening);
      }
      ctx.restore();
    });
  }

  function drawWindowFrame(start, end, thicknessMm, selectedOpening) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy);
    if (length <= 0) return;

    const tangent = { x: dx / length, y: dy / length };
    const perpendicular = { x: -tangent.y, y: tangent.x };
    const halfDepth = Math.max(2, ((thicknessMm || defaults.interiorWallThicknessMm) / 1000) * view.scale / 2);
    const stroke = selectedOpening ? "#f97316" : "#111827";

    drawWindowPanel(start, end, perpendicular, -halfDepth, 0, stroke, selectedOpening);
    drawWindowPanel(start, end, perpendicular, 0, halfDepth, stroke, selectedOpening);
  }

  function drawWindowPanel(start, end, perpendicular, offsetA, offsetB, stroke, selectedOpening) {
    const corners = [
      { x: start.x + perpendicular.x * offsetA, y: start.y + perpendicular.y * offsetA },
      { x: end.x + perpendicular.x * offsetA, y: end.y + perpendicular.y * offsetA },
      { x: end.x + perpendicular.x * offsetB, y: end.y + perpendicular.y * offsetB },
      { x: start.x + perpendicular.x * offsetB, y: start.y + perpendicular.y * offsetB },
    ];
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = stroke;
    ctx.lineWidth = selectedOpening ? 2 : 1.25;
    ctx.beginPath();
    ctx.moveTo(corners[0].x, corners[0].y);
    corners.slice(1).forEach((corner) => ctx.lineTo(corner.x, corner.y));
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  function drawDoorFrame(opening, start, end, thicknessMm, selectedOpening) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy);
    if (length <= 0) return;

    const tangent = { x: dx / length, y: dy / length };
    const perpendicular = { x: -tangent.y, y: tangent.x };
    const frameDepth = Math.max(10, (thicknessMm / 1000) * view.scale + 6);
    const halfDepth = frameDepth / 2;
    const jambLength = doorJambLengthPx(opening);
    const jambStroke = selectedOpening ? doorStyle.colors.selected : doorStyle.colors.frame_stroke;

    drawDoorJamb(start, tangent, perpendicular, halfDepth, jambLength, jambStroke, selectedOpening);
    drawDoorJamb(end, { x: -tangent.x, y: -tangent.y }, perpendicular, halfDepth, jambLength, jambStroke, selectedOpening);
  }

  function drawDoorJamb(anchor, inward, perpendicular, halfDepth, jambLength, jambStroke, selectedOpening) {
    const inner = {
      x: anchor.x + inward.x * jambLength,
      y: anchor.y + inward.y * jambLength,
    };
    const corners = [
      { x: anchor.x + perpendicular.x * halfDepth, y: anchor.y + perpendicular.y * halfDepth },
      { x: inner.x + perpendicular.x * halfDepth, y: inner.y + perpendicular.y * halfDepth },
      { x: inner.x - perpendicular.x * halfDepth, y: inner.y - perpendicular.y * halfDepth },
      { x: anchor.x - perpendicular.x * halfDepth, y: anchor.y - perpendicular.y * halfDepth },
    ];

    ctx.fillStyle = doorStyle.colors.frame_fill;
    ctx.strokeStyle = jambStroke;
    ctx.lineWidth = selectedOpening ? 2 : 1.5;
    ctx.beginPath();
    ctx.moveTo(corners[0].x, corners[0].y);
    corners.slice(1).forEach((corner) => ctx.lineTo(corner.x, corner.y));
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  function drawDoorSwing(opening, walls, selectedOpening) {
    const geometry = doorSwingGeometry(opening, walls);
    if (!geometry) return;
    const hingeAnchor = worldToScreen(geometry.hinge);
    const latchAnchor = worldToScreen(geometry.latch);
    const jambInset = doorJambLengthPx(opening);
    const frameDepth = Math.max(10, (geometry.thicknessMm / 1000) * view.scale + 6);
    const hingeCornerOffset = frameDepth / 2;
    const hinge = {
      x: hingeAnchor.x + geometry.screenTangent.x * jambInset + geometry.screenNormal.x * hingeCornerOffset,
      y: hingeAnchor.y + geometry.screenTangent.y * jambInset + geometry.screenNormal.y * hingeCornerOffset,
    };
    const closedEnd = {
      x: latchAnchor.x - geometry.screenTangent.x * jambInset + geometry.screenNormal.x * hingeCornerOffset,
      y: latchAnchor.y - geometry.screenTangent.y * jambInset + geometry.screenNormal.y * hingeCornerOffset,
    };
    const leafLength = Math.max(10, Math.hypot(closedEnd.x - hinge.x, closedEnd.y - hinge.y));
    const leafEnd = {
      x: hinge.x + geometry.screenNormal.x * leafLength,
      y: hinge.y + geometry.screenNormal.y * leafLength,
    };
    const swingColor = selectedOpening ? doorStyle.colors.selected : doorStyle.colors.swing_stroke;
    const doorColor = selectedOpening ? doorStyle.colors.leaf_fill_selected : doorStyle.colors.leaf_fill;
    const doorStroke = selectedOpening ? doorStyle.colors.selected : doorStyle.colors.leaf_stroke;
    const leafThickness = doorLeafThicknessPx(opening);

    ctx.strokeStyle = swingColor;
    ctx.lineWidth = selectedOpening ? 2.5 : 2;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(
      hinge.x,
      hinge.y,
      leafLength,
      geometry.startAngle,
      geometry.endAngle,
      geometry.counterclockwise,
    );
    ctx.stroke();
    drawDoorSwingArrow(hinge, leafEnd, geometry.counterclockwise, swingColor);

    ctx.fillStyle = doorColor;
    ctx.strokeStyle = doorStroke;
    ctx.lineWidth = selectedOpening ? 2.5 : 2;
    ctx.beginPath();
    ctx.moveTo(
      hinge.x,
      hinge.y,
    );
    ctx.lineTo(
      leafEnd.x,
      leafEnd.y,
    );
    ctx.lineTo(
      leafEnd.x + geometry.screenTangent.x * leafThickness,
      leafEnd.y + geometry.screenTangent.y * leafThickness,
    );
    ctx.lineTo(
      hinge.x + geometry.screenTangent.x * leafThickness,
      hinge.y + geometry.screenTangent.y * leafThickness,
    );
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  function drawDoorSwingArrow(hinge, arcEnd, counterclockwise, color) {
    const radialAngle = Math.atan2(arcEnd.y - hinge.y, arcEnd.x - hinge.x);
    const tangentAngle = radialAngle + (counterclockwise ? -Math.PI / 2 : Math.PI / 2);
    const size = 8;
    ctx.save();
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(arcEnd.x, arcEnd.y);
    ctx.lineTo(
      arcEnd.x - size * Math.cos(tangentAngle - Math.PI / 6),
      arcEnd.y - size * Math.sin(tangentAngle - Math.PI / 6),
    );
    ctx.lineTo(
      arcEnd.x - size * Math.cos(tangentAngle + Math.PI / 6),
      arcEnd.y - size * Math.sin(tangentAngle + Math.PI / 6),
    );
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function drawRooms() {
    activeLevel().rooms.forEach((room) => {
      const point = worldToScreen(room.label);
      const selectedRoom = isSelected("room", room.room_id);
      ctx.save();
      ctx.fillStyle = selectedRoom ? "#f97316" : "#0f172a";
      ctx.font = "600 15px Inter, Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(room.name, point.x, point.y);
      ctx.font = "12px Inter, Arial, sans-serif";
      ctx.fillStyle = "#64748b";
      ctx.fillText(room.room_type.replace(/_/g, " "), point.x, point.y + 16);
      ctx.restore();
    });
  }

  function drawDimensions() {
    activeLevel().dimensions.forEach((dimension) => {
      const display = dimensionDisplayPoints(dimension);
      const start = worldToScreen(display.start);
      const end = worldToScreen(display.end);
      const measureStart = worldToScreen(dimension.start);
      const measureEnd = worldToScreen(dimension.end);
      const selectedDimension = isSelected("dimension", dimension.dimension_id);
      ctx.save();
      ctx.strokeStyle = selectedDimension ? "#f97316" : "#94a3b8";
      ctx.lineWidth = 1;
      line(measureStart.x, measureStart.y, start.x, start.y);
      line(measureEnd.x, measureEnd.y, end.x, end.y);
      ctx.strokeStyle = selectedDimension ? "#f97316" : "#64748b";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 5]);
      line(start.x, start.y, end.x, end.y);
      ctx.setLineDash([]);
      ctx.fillStyle = selectedDimension ? "#f97316" : "#475569";
      ctx.font = "12px Inter, Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(dimension.label || formatDistance(dimension.start, dimension.end), (start.x + end.x) / 2, (start.y + end.y) / 2 - 8);
      ctx.restore();
    });
  }

  function drawPreview() {
    if (!hoverPoint) return;
    if (tool === "lot" && lotStart) {
      drawLot(
        {
          lot_id: "lot-preview",
          corner_a: lotStart,
          corner_b: hoverPoint,
          boundary_thickness_mm: 35,
        },
        true,
      );
    }
    if (tool === "line" && lineStart) {
      const end = orthogonalPoint(lineStart, hoverPoint);
      const startScreen = worldToScreen(lineStart);
      const endScreen = worldToScreen(end);
      ctx.save();
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 6]);
      line(startScreen.x, startScreen.y, endScreen.x, endScreen.y);
      ctx.restore();
    }
    if (tool === "wall" && wallStart) {
      const end = orthogonalPoint(wallStart, hoverPoint);
      ctx.save();
      drawWallPreviewSolids([
        {
          start: wallStart,
          end,
          wall_type: wallTypeEl.value,
          thickness_mm: wallThicknessMm(wallTypeEl.value),
        },
      ]);
      ctx.restore();
    }
    if (tool === "rectangle" && rectangleStart) {
      drawRectangleLinePreview(rectangleStart, hoverPoint);
    }
    if (tool === "rectangle-wall" && rectangleWallStart) {
      drawRectangleWallPreview(rectangleWallStart, hoverPoint);
    }
    if (tool === "dimension" && dimensionStart && !dimensionMeasureEnd) {
      const end = orthogonalPoint(dimensionStart, hoverPoint);
      const startScreen = worldToScreen(dimensionStart);
      const endScreen = worldToScreen(end);
      ctx.save();
      ctx.strokeStyle = "#2563eb";
      ctx.setLineDash([5, 5]);
      line(startScreen.x, startScreen.y, endScreen.x, endScreen.y);
      ctx.restore();
    }
    if (tool === "dimension" && dimensionStart && dimensionMeasureEnd) {
      const resolved = resolveDimensionBasis(dimensionStart, dimensionMeasureEnd, hoverPoint, dimensionBasis());
      const offsetM = dimensionOffsetFromPlacement(resolved.start, resolved.end, hoverPoint);
      const display = dimensionDisplayPoints({
        start: resolved.start,
        end: resolved.end,
        offset_m: offsetM,
      });
      const measureStart = worldToScreen(resolved.start);
      const measureEnd = worldToScreen(resolved.end);
      const displayStart = worldToScreen(display.start);
      const displayEnd = worldToScreen(display.end);
      ctx.save();
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1;
      line(measureStart.x, measureStart.y, displayStart.x, displayStart.y);
      line(measureEnd.x, measureEnd.y, displayEnd.x, displayEnd.y);
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 5]);
      line(displayStart.x, displayStart.y, displayEnd.x, displayEnd.y);
      ctx.setLineDash([]);
      ctx.fillStyle = "#2563eb";
      ctx.font = "12px Inter, Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(formatDistance(resolved.start, resolved.end), (displayStart.x + displayEnd.x) / 2, (displayStart.y + displayEnd.y) / 2 - 8);
      ctx.restore();
    }
  }

  function drawSnapMarker() {
    if (!snapCandidate) return;
    const point = worldToScreen(snapCandidate.point);
    const size = 10;
    ctx.save();
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 2;
    if (snapCandidate.type.includes("midpoint")) {
      ctx.beginPath();
      ctx.moveTo(point.x, point.y - size / 2);
      ctx.lineTo(point.x + size / 2, point.y + size / 2);
      ctx.lineTo(point.x - size / 2, point.y + size / 2);
      ctx.closePath();
      ctx.stroke();
    } else {
      ctx.strokeRect(point.x - size / 2, point.y - size / 2, size, size);
    }
    ctx.restore();
  }

  function drawRectangleLinePreview(cornerA, cornerB) {
    if (samePoint(cornerA, cornerB) || Math.abs(cornerA.x - cornerB.x) < 1e-9 || Math.abs(cornerA.y - cornerB.y) < 1e-9) return;
    ctx.save();
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    rectangleSegments(cornerA, cornerB).forEach((segment) => {
      const start = worldToScreen(segment.start);
      const end = worldToScreen(segment.end);
      line(start.x, start.y, end.x, end.y);
    });
    ctx.restore();
  }

  function drawRectangleWallPreview(cornerA, cornerB) {
    if (samePoint(cornerA, cornerB) || Math.abs(cornerA.x - cornerB.x) < 1e-9 || Math.abs(cornerA.y - cornerB.y) < 1e-9) return;
    const walls = rectangleSegments(cornerA, cornerB).map((segment, index) => ({
      wall_id: `preview-wall-${index}`,
      start: segment.start,
      end: segment.end,
      wall_type: wallTypeEl.value,
      thickness_mm: wallThicknessMm(wallTypeEl.value),
    }));
    ctx.save();
    drawWallPreviewSolids(walls);
    ctx.restore();
  }

  function drawWallPreviewSolids(walls) {
    ctx.setLineDash([8, 6]);
    walls.forEach((wall) => {
      fillWorldPolygon(wallSolidPolygon(wall), "rgba(37, 99, 235, 0.18)", "#2563eb", 1.5);
    });
    wallJointPolygons(walls).forEach((joint) => {
      fillWorldPolygon(joint.points, "rgba(37, 99, 235, 0.18)", "#2563eb", 1.5);
    });
    ctx.setLineDash([]);
  }

  function drawSelectionWindow() {
    if (!selectionDrag) return;
    const x = Math.min(selectionDrag.startScreen.x, selectionDrag.currentScreen.x);
    const y = Math.min(selectionDrag.startScreen.y, selectionDrag.currentScreen.y);
    const width = Math.abs(selectionDrag.currentScreen.x - selectionDrag.startScreen.x);
    const height = Math.abs(selectionDrag.currentScreen.y - selectionDrag.startScreen.y);
    const crossing = selectionDrag.currentScreen.x < selectionDrag.startScreen.x;
    ctx.save();
    ctx.fillStyle = crossing ? "rgba(34, 197, 94, 0.12)" : "rgba(37, 99, 235, 0.12)";
    ctx.strokeStyle = crossing ? "#22c55e" : "#2563eb";
    ctx.lineWidth = 1.5;
    if (crossing) ctx.setLineDash([6, 5]);
    ctx.fillRect(x, y, width, height);
    ctx.strokeRect(x, y, width, height);
    ctx.restore();
  }

  function drawAxisIndicator(width, height) {
    const axisLength = Math.max(22, Math.min(34, Math.floor(Math.min(width, height) * 0.16)));
    const badgeWidth = axisLength + 64;
    const badgeHeight = axisLength + 48;
    const badgeX = 12;
    const badgeY = Math.max(12, height - badgeHeight - 12);
    const origin = { x: badgeX + 28, y: badgeY + badgeHeight - 20 };
    const xEnd = { x: origin.x + axisLength, y: origin.y };
    const yEnd = { x: origin.x, y: origin.y - axisLength };
    const arrowSize = 6;

    ctx.save();
    ctx.lineWidth = 2;
    ctx.font = "700 12px Inter, Arial, sans-serif";
    ctx.textBaseline = "middle";

    ctx.fillStyle = "rgba(248, 250, 252, 0.86)";
    ctx.strokeStyle = "rgba(148, 163, 184, 0.7)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(badgeX, badgeY, badgeWidth, badgeHeight, 8);
    ctx.fill();
    ctx.stroke();

    ctx.lineWidth = 2;
    ctx.strokeStyle = "#dc2626";
    ctx.fillStyle = "#dc2626";
    drawAxisArrow(origin.x, origin.y, xEnd.x, xEnd.y, arrowSize);
    ctx.textAlign = "left";
    ctx.fillText("X", xEnd.x + 10, xEnd.y);

    ctx.strokeStyle = "#16a34a";
    ctx.fillStyle = "#16a34a";
    drawAxisArrow(origin.x, origin.y, yEnd.x, yEnd.y, arrowSize);
    ctx.textAlign = "center";
    ctx.fillText("Y", yEnd.x, yEnd.y - 11);

    ctx.fillStyle = "#334155";
    ctx.beginPath();
    ctx.arc(origin.x, origin.y, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawAxisArrow(x1, y1, x2, y2, arrowSize) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    const angle = Math.atan2(y2 - y1, x2 - x1);
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(
      x2 - arrowSize * Math.cos(angle - Math.PI / 6),
      y2 - arrowSize * Math.sin(angle - Math.PI / 6),
    );
    ctx.lineTo(
      x2 - arrowSize * Math.cos(angle + Math.PI / 6),
      y2 - arrowSize * Math.sin(angle + Math.PI / 6),
    );
    ctx.closePath();
    ctx.fill();
  }

  function line(x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  function fillWorldPolygon(points, fillStyle, strokeStyle = null, lineWidth = 0) {
    if (!points.length) return;
    const screenPoints = points.map(worldToScreen);
    ctx.beginPath();
    ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
    screenPoints.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
    ctx.closePath();
    ctx.fillStyle = fillStyle;
    ctx.fill();
    if (strokeStyle && lineWidth > 0) {
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
  }

  function wallSolidPolygon(wall) {
    const dx = wall.end.x - wall.start.x;
    const dy = wall.end.y - wall.start.y;
    const length = Math.hypot(dx, dy);
    if (length <= 0) return [];
    const half = ((wall.thickness_mm || wallThicknessMm(wall.wall_type || "interior")) / 1000) / 2;
    const normal = { x: -dy / length, y: dx / length };
    return [
      { x: wall.start.x + normal.x * half, y: wall.start.y + normal.y * half },
      { x: wall.end.x + normal.x * half, y: wall.end.y + normal.y * half },
      { x: wall.end.x - normal.x * half, y: wall.end.y - normal.y * half },
      { x: wall.start.x - normal.x * half, y: wall.start.y - normal.y * half },
    ];
  }

  function wallJointPolygons(walls, suppressedKeys = new Set()) {
    const endpointGroups = new Map();
    walls.forEach((wall) => {
      [wall.start, wall.end].forEach((point) => {
        const key = pointKey(point);
        if (!endpointGroups.has(key)) endpointGroups.set(key, []);
        endpointGroups.get(key).push({ wall, point });
      });
    });

    const joints = [];
    endpointGroups.forEach((entries, key) => {
      if (suppressedKeys.has(key) || entries.length < 2) return;
      const orientations = new Set(entries.map(({ wall }) => wallOrientation(wall)));
      if (orientations.size < 2) return;
      const point = entries[0].point;
      const thicknessMm = Math.max(...entries.map(({ wall }) => wall.thickness_mm || wallThicknessMm(wall.wall_type || "interior")));
      const half = thicknessMm / 2000;
      joints.push({
        key,
        wallIds: entries.map(({ wall }) => wall.wall_id),
        wallType: entries.some(({ wall }) => wall.wall_type === "exterior") ? "exterior" : "interior",
        points: [
          { x: point.x - half, y: point.y - half },
          { x: point.x + half, y: point.y - half },
          { x: point.x + half, y: point.y + half },
          { x: point.x - half, y: point.y + half },
        ],
      });
    });
    return joints;
  }

  function wallOrientation(wall) {
    return Math.abs(wall.start.y - wall.end.y) < 1e-9 ? "horizontal" : "vertical";
  }

  function isSelected(type, id) {
    return selectedItems.some((hit) => hit.type === type && entityId(hit) === id);
  }

  function setSelection(hits) {
    selectedItems = hits;
    selected = selectedItems[0] || null;
    updateSelectionSummary();
    draw();
  }

  function entityId(hit) {
    if (!hit) return "";
    if (hit.type === "lot") return hit.item.lot_id;
    if (hit.type === "line") return hit.item.line_id;
    if (hit.type === "wall") return hit.item.wall_id;
    if (hit.type === "opening") return hit.item.opening_id;
    if (hit.type === "room") return hit.item.room_id;
    if (hit.type === "dimension") return hit.item.dimension_id;
    return "";
  }

  function wallMap() {
    return new Map(activeLevel().walls.map((wall) => [wall.wall_id, wall]));
  }

  function endpointCandidates() {
    const level = activeLevel();
    const walls = wallMap();
    const suppressedWallEndpointKeys = doorOpeningCenterlineEndpointKeys(walls);
    const candidates = [];
    level.lots.forEach((lot) => {
      lotCorners(lot).forEach((point) => candidates.push({ type: "lot", id: lot.lot_id, point }));
      lotSegments(lot).forEach((segment, index) => {
        candidates.push({
          type: "lot-midpoint",
          id: `${lot.lot_id}-${index}`,
          point: segmentMidpoint(segment.start, segment.end),
        });
      });
    });
    level.lines.forEach((draftLine) => {
      candidates.push({ type: "line", id: draftLine.line_id, point: draftLine.start });
      candidates.push({ type: "line", id: draftLine.line_id, point: draftLine.end });
      candidates.push({ type: "line-midpoint", id: draftLine.line_id, point: segmentMidpoint(draftLine.start, draftLine.end) });
    });
    level.openings.forEach((opening) => {
      const geometry = openingGeometry(opening, walls);
      if (geometry) {
        candidates.push({ type: "opening-midpoint", id: opening.opening_id, point: segmentMidpoint(geometry.points.start, geometry.points.end) });
      }
      if (opening.opening_type !== "door") return;
      doorFrameSnapPoints(opening, walls).forEach((point, index) => {
        candidates.push({ type: "door-jamb", id: `${opening.opening_id}-${index}`, point });
      });
    });
    level.walls.forEach((wall) => {
      if (!suppressedWallEndpointKeys.has(pointKey(wall.start))) {
        candidates.push({ type: "wall", id: wall.wall_id, point: wall.start });
      }
      if (!suppressedWallEndpointKeys.has(pointKey(wall.end))) {
        candidates.push({ type: "wall", id: wall.wall_id, point: wall.end });
      }
      candidates.push({ type: "wall-midpoint", id: wall.wall_id, point: segmentMidpoint(wall.start, wall.end) });
    });
    level.dimensions.forEach((dimension) => {
      candidates.push({ type: "dimension", id: dimension.dimension_id, point: dimension.start });
      candidates.push({ type: "dimension", id: dimension.dimension_id, point: dimension.end });
      candidates.push({ type: "dimension-midpoint", id: dimension.dimension_id, point: segmentMidpoint(dimension.start, dimension.end) });
    });
    return candidates;
  }

  function doorOpeningCenterlineEndpointKeys(walls) {
    const keys = new Set();
    activeLevel().openings.forEach((opening) => {
      if (opening.opening_type !== "door") return;
      const geometry = openingGeometry(opening, walls);
      if (!geometry) return;
      keys.add(pointKey(geometry.points.start));
      keys.add(pointKey(geometry.points.end));
    });
    return keys;
  }

  function doorFrameSnapPoints(opening, walls) {
    const geometry = openingGeometry(opening, walls);
    if (!geometry) return [];
    const start = geometry.points.start;
    const end = geometry.points.end;
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy);
    if (length <= 0) return [];

    const tangent = { x: dx / length, y: dy / length };
    const perpendicular = { x: -tangent.y, y: tangent.x };
    const halfDepth = ((geometry.thicknessMm || defaults.interiorWallThicknessMm) / 1000) / 2;
    const jambLength = doorJambMeters(opening);
    return [
      ...doorJambSnapCorners(start, tangent, perpendicular, halfDepth, jambLength),
      ...doorJambSnapCorners(end, { x: -tangent.x, y: -tangent.y }, perpendicular, halfDepth, jambLength),
    ];
  }

  function doorJambSnapCorners(anchor, inward, perpendicular, halfDepth, jambLength) {
    const inner = {
      x: anchor.x + inward.x * jambLength,
      y: anchor.y + inward.y * jambLength,
    };
    return [
      { x: roundM(anchor.x + perpendicular.x * halfDepth), y: roundM(anchor.y + perpendicular.y * halfDepth) },
      { x: roundM(inner.x + perpendicular.x * halfDepth), y: roundM(inner.y + perpendicular.y * halfDepth) },
      { x: roundM(inner.x - perpendicular.x * halfDepth), y: roundM(inner.y - perpendicular.y * halfDepth) },
      { x: roundM(anchor.x - perpendicular.x * halfDepth), y: roundM(anchor.y - perpendicular.y * halfDepth) },
    ];
  }

  function pointKey(point) {
    return `${roundM(point.x)}:${roundM(point.y)}`;
  }

  function nearestSnapEndpoint(point) {
    const radiusPx = 12;
    const screenPoint = worldToScreen(point);
    let best = null;
    endpointCandidates().forEach((candidate) => {
      const candidateScreen = worldToScreen(candidate.point);
      const distancePx = Math.hypot(candidateScreen.x - screenPoint.x, candidateScreen.y - screenPoint.y);
      if (distancePx <= radiusPx && (!best || distancePx < best.distancePx)) {
        best = { ...candidate, distancePx };
      }
    });
    return best;
  }

  function wallLengthM(wall) {
    return Math.abs(wall.end.x - wall.start.x) + Math.abs(wall.end.y - wall.start.y);
  }

  function segmentMidpoint(start, end) {
    return {
      x: roundM((start.x + end.x) / 2),
      y: roundM((start.y + end.y) / 2),
    };
  }

  function parseRectangleDimensions(value) {
    const cleaned = String(value || "").trim().replace(/^@/, "").replace(/\s+/g, "");
    const parts = cleaned.split(/[x,]/i);
    if (parts.length !== 2) return null;
    const width = Number(parts[0]);
    const depth = Number(parts[1]);
    if (!Number.isFinite(width) || !Number.isFinite(depth) || width <= 0 || depth <= 0) return null;
    return { width, depth };
  }

  function readWidthDepthInputs(widthEl, depthEl) {
    const width = Number(widthEl.value);
    const depth = Number(depthEl.value);
    if (!Number.isFinite(width) || !Number.isFinite(depth) || width <= 0 || depth <= 0) return null;
    return { width, depth };
  }

  function readSetbackInputs() {
    const setbacks = {
      front: Number(setbackFrontEl.value),
      rear: Number(setbackRearEl.value),
      left: Number(setbackLeftEl.value),
      right: Number(setbackRightEl.value),
    };
    if (Object.values(setbacks).some((value) => !Number.isFinite(value) || value < 0)) return null;
    return setbacks;
  }

  function parseSetbackValues(value) {
    const parts = String(value || "").trim().replace(/\s+/g, "").split(",");
    if (parts.length !== 4) return null;
    const [front, rear, left, right] = parts.map(Number);
    if ([front, rear, left, right].some((number) => !Number.isFinite(number) || number < 0)) return null;
    return { front, rear, left, right };
  }

  function parseSpacingList(value) {
    return String(value || "")
      .trim()
      .replace(/\s+/g, "")
      .split(",")
      .map(Number)
      .filter((number) => Number.isFinite(number) && number > 0);
  }

  function parseGridValues(value) {
    const parts = String(value || "").split("|");
    if (parts.length !== 2) return null;
    const xSpacings = parseSpacingList(parts[0]);
    const ySpacings = parseSpacingList(parts[1]);
    if (!xSpacings.length || !ySpacings.length) return null;
    return { xSpacings, ySpacings };
  }

  function selectedLotBounds() {
    if (selected && selected.type === "lot") return lotBounds(selected.item);
    return null;
  }

  function latestLotBounds() {
    const lots = activeLevel().lots;
    if (!lots.length) return null;
    return lotBounds(lots[lots.length - 1]);
  }

  function latestGuideRectangleBounds(lineType) {
    const lines = activeLevel().lines.filter((draftLine) => draftLine.line_type === lineType);
    if (lines.length < 4) return null;
    return lineRectangleBounds(lines.slice(-4));
  }

  function lineRectangleBounds(lines) {
    const points = lines.flatMap((draftLine) => [draftLine.start, draftLine.end]);
    return {
      minX: roundM(Math.min(...points.map((point) => point.x))),
      minY: roundM(Math.min(...points.map((point) => point.y))),
      maxX: roundM(Math.max(...points.map((point) => point.x))),
      maxY: roundM(Math.max(...points.map((point) => point.y))),
    };
  }

  function structuralGridPositions(minValue, maxValue, requestedSpacings) {
    const length = maxValue - minValue;
    if (length <= 0) return [roundM(minValue)];
    const requested = requestedSpacings.filter((spacing) => Number.isFinite(spacing) && spacing > 0);
    const exact = exactRegularRequestedGrid(minValue, maxValue, requested);
    if (exact) return exact;

    const target = requested.length ? average(requested) : 4;
    const bayCount = structuralBayCount(length, target);
    const baySize = length / bayCount;
    return Array.from({ length: bayCount + 1 }, (_value, index) => roundM(minValue + baySize * index));
  }

  function exactRegularRequestedGrid(minValue, maxValue, spacings) {
    if (spacings.length < 2) return null;
    const length = maxValue - minValue;
    const total = spacings.reduce((sum, spacing) => sum + spacing, 0);
    const regular = spacings.every((spacing) => spacing >= 3 && spacing <= 5);
    if (!regular || Math.abs(total - length) > 1e-6) return null;
    const positions = [roundM(minValue)];
    let cursor = minValue;
    spacings.forEach((spacing) => {
      cursor = roundM(cursor + spacing);
      positions.push(cursor);
    });
    return positions;
  }

  function structuralBayCount(length, target) {
    const minBay = 3;
    const maxBay = 5;
    if (length <= maxBay) return 1;
    const minCount = Math.ceil(length / maxBay);
    const maxCount = Math.floor(length / minBay);
    if (minCount <= maxCount) {
      let best = minCount;
      for (let count = minCount; count <= maxCount; count += 1) {
        if (Math.abs(length / count - target) < Math.abs(length / best - target)) {
          best = count;
        }
      }
      return best;
    }
    return Math.max(1, Math.round(length / Math.max(minBay, Math.min(maxBay, target || 4))));
  }

  function average(values) {
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }

  function gridLabelSets(verticalCount, horizontalCount, numbersFollowX) {
    return {
      vertical: numbersFollowX ? numberLabels(verticalCount) : letterLabels(verticalCount),
      horizontal: numbersFollowX ? letterLabels(horizontalCount) : numberLabels(horizontalCount),
    };
  }

  function letterLabels(count) {
    return Array.from({ length: count }, (_value, index) => spreadsheetColumnLabel(index));
  }

  function numberLabels(count) {
    return Array.from({ length: count }, (_value, index) => String(index + 1));
  }

  function spreadsheetColumnLabel(index) {
    let label = "";
    let value = index + 1;
    while (value > 0) {
      const remainder = (value - 1) % 26;
      label = String.fromCharCode(65 + remainder) + label;
      value = Math.floor((value - 1) / 26);
    }
    return label;
  }

  function cornerFromRectangleDimensions(corner, dimensions) {
    return {
      x: roundM(corner.x + dimensions.width),
      y: roundM(corner.y + dimensions.depth),
    };
  }

  function handleActiveGeometryInput(value) {
    if (tool !== "rectangle" && tool !== "rectangle-wall") return false;
    const start = tool === "rectangle" ? rectangleStart : rectangleWallStart;
    if (!start) return false;
    const dimensions = parseRectangleDimensions(value);
    if (!dimensions) {
      setStatus("Type rectangle dimensions as width,height in meters, for example 5,8.");
      return true;
    }
    const oppositeCorner = cornerFromRectangleDimensions(start, dimensions);
    if (tool === "rectangle") {
      addRectangleLines(start, oppositeCorner);
      rectangleStart = null;
    } else {
      addRectangleWalls(start, oppositeCorner);
      rectangleWallStart = null;
    }
    resetCommandLinePrompt();
    return true;
  }

  function handleCommandLineInput(value) {
    if (handleActiveGeometryInput(value)) return;
    if (handleWorkflowCommand(value)) return;
    executeCommand(value);
  }

  function handleWorkflowCommand(value) {
    const trimmed = String(value || "").trim();
    const match = trimmed.match(/^(\S+)\s+(.+)$/);
    if (!match) return false;
    const command = match[1].toUpperCase();
    const args = match[2];

    if (command === "LOT" || command === "LOTAREA" || command === "LA") {
      const dimensions = parseRectangleDimensions(args);
      if (!dimensions) {
        setStatus("Type lot dimensions as width,depth in meters, for example LOT 10,15.");
        return true;
      }
      lotWidthEl.value = dimensions.width;
      lotDepthEl.value = dimensions.depth;
      createLotFromDimensions(dimensions.width, dimensions.depth);
      return true;
    }

    if (command === "SETBACK" || command === "SB") {
      const setbacks = parseSetbackValues(args);
      if (!setbacks) {
        setStatus("Type setbacks as front,rear,left,right in meters, for example SETBACK 3,2,2,2.");
        return true;
      }
      setbackFrontEl.value = setbacks.front;
      setbackRearEl.value = setbacks.rear;
      setbackLeftEl.value = setbacks.left;
      setbackRightEl.value = setbacks.right;
      createSetbackLines(setbacks);
      return true;
    }

    if (command === "GRID" || command === "XLINE") {
      const values = parseGridValues(args);
      if (!values) {
        setStatus("Type grid target bays as X|Y, for example GRID 4|4, or exact regular lists such as GRID 3,3|5,5.");
        return true;
      }
      gridXSpacingsEl.value = values.xSpacings.join(",");
      gridYSpacingsEl.value = values.ySpacings.join(",");
      createGridLines(values.xSpacings, values.ySpacings);
      return true;
    }

    return false;
  }

  function promptRectangleDimensions(status) {
    commandLine.placeholder = "Width,Height in meters e.g. 5,8";
    commandLine.focus();
    setStatus(status);
  }

  function resetCommandLinePrompt() {
    commandLine.placeholder = "Command";
  }

  function dimensionBasis() {
    return dimensionBasisEl ? dimensionBasisEl.value : "centerline";
  }

  function dimensionBasisLabel(basis = dimensionBasis()) {
    const labels = {
      centerline: "Centerline",
      outside_face: "Outside Face",
      inside_face: "Inside Face",
    };
    return labels[basis] || "Centerline";
  }

  function resolveDimensionBasis(rawStart, rawEnd, placement, basis) {
    const centerStart = clone(rawStart);
    const centerEnd = orthogonalPoint(centerStart, rawEnd);
    if (basis === "centerline") {
      return { start: centerStart, end: centerEnd, referenceIds: [] };
    }

    const horizontal = Math.abs(centerStart.y - centerEnd.y) < 1e-9;
    const axisSign = horizontal
      ? Math.sign(centerEnd.x - centerStart.x) || 1
      : Math.sign(centerEnd.y - centerStart.y) || 1;
    const faceSide = dimensionPlacementSide(centerStart, centerEnd, placement, horizontal);
    const parallelInfo = dimensionParallelWallInfo(centerStart, centerEnd, horizontal);
    const startInfo = connectedPerpendicularWallInfo(centerStart, horizontal);
    const endInfo = connectedPerpendicularWallInfo(centerEnd, horizontal);
    const expand = basis === "outside_face" ? 1 : -1;
    const start = clone(centerStart);
    const end = clone(centerEnd);

    if (horizontal) {
      const y = roundM(centerStart.y + faceSide * parallelInfo.halfThicknessM);
      start.x = roundM(centerStart.x - axisSign * startInfo.halfThicknessM * expand);
      start.y = y;
      end.x = roundM(centerEnd.x + axisSign * endInfo.halfThicknessM * expand);
      end.y = y;
    } else {
      const x = roundM(centerStart.x + faceSide * parallelInfo.halfThicknessM);
      start.x = x;
      start.y = roundM(centerStart.y - axisSign * startInfo.halfThicknessM * expand);
      end.x = x;
      end.y = roundM(centerEnd.y + axisSign * endInfo.halfThicknessM * expand);
    }

    return {
      start,
      end,
      referenceIds: uniqueIds([
        ...parallelInfo.wallIds,
        ...startInfo.wallIds,
        ...endInfo.wallIds,
      ]),
    };
  }

  function dimensionPlacementSide(start, end, placement, horizontal) {
    const delta = horizontal ? placement.y - start.y : placement.x - start.x;
    if (Math.abs(delta) < 1e-9) return 1;
    return delta < 0 ? -1 : 1;
  }

  function dimensionParallelWallInfo(start, end, horizontal) {
    const candidates = activeLevel().walls.filter((wall) => {
      if (wallOrientation(wall) !== (horizontal ? "horizontal" : "vertical")) return false;
      if (horizontal) {
        if (Math.abs(wall.start.y - start.y) > 1e-9) return false;
        return rangesOverlap(
          Math.min(start.x, end.x),
          Math.max(start.x, end.x),
          Math.min(wall.start.x, wall.end.x),
          Math.max(wall.start.x, wall.end.x),
        );
      }
      if (Math.abs(wall.start.x - start.x) > 1e-9) return false;
      return rangesOverlap(
        Math.min(start.y, end.y),
        Math.max(start.y, end.y),
        Math.min(wall.start.y, wall.end.y),
        Math.max(wall.start.y, wall.end.y),
      );
    });
    return wallThicknessInfo(candidates);
  }

  function connectedPerpendicularWallInfo(point, dimensionHorizontal) {
    const orientation = dimensionHorizontal ? "vertical" : "horizontal";
    const candidates = activeLevel().walls.filter((wall) => (
      wallOrientation(wall) === orientation
      && (
        samePoint(wall.start, point)
        || samePoint(wall.end, point)
        || pointOnSegment(point, wall.start, wall.end)
      )
    ));
    return wallThicknessInfo(candidates);
  }

  function wallThicknessInfo(walls) {
    if (!walls.length) return { halfThicknessM: 0, wallIds: [] };
    const thicknessMm = Math.max(...walls.map((wall) => wall.thickness_mm || wallThicknessMm(wall.wall_type || "interior")));
    return {
      halfThicknessM: thicknessMm / 2000,
      wallIds: walls.map((wall) => wall.wall_id),
    };
  }

  function rangesOverlap(aMin, aMax, bMin, bMax) {
    return Math.max(aMin, bMin) <= Math.min(aMax, bMax) + 1e-9;
  }

  function uniqueIds(ids) {
    return Array.from(new Set(ids.filter(Boolean)));
  }

  function lotBounds(lot) {
    return {
      minX: Math.min(lot.corner_a.x, lot.corner_b.x),
      minY: Math.min(lot.corner_a.y, lot.corner_b.y),
      maxX: Math.max(lot.corner_a.x, lot.corner_b.x),
      maxY: Math.max(lot.corner_a.y, lot.corner_b.y),
    };
  }

  function lotCorners(lot) {
    const bounds = lotBounds(lot);
    return [
      { x: bounds.minX, y: bounds.minY },
      { x: bounds.maxX, y: bounds.minY },
      { x: bounds.maxX, y: bounds.maxY },
      { x: bounds.minX, y: bounds.maxY },
    ];
  }

  function lotSegments(lot) {
    const corners = lotCorners(lot);
    return [
      { start: corners[0], end: corners[1] },
      { start: corners[1], end: corners[2] },
      { start: corners[2], end: corners[3] },
      { start: corners[3], end: corners[0] },
    ];
  }

  function rectangleSegments(cornerA, cornerB) {
    const minX = Math.min(cornerA.x, cornerB.x);
    const minY = Math.min(cornerA.y, cornerB.y);
    const maxX = Math.max(cornerA.x, cornerB.x);
    const maxY = Math.max(cornerA.y, cornerB.y);
    const topLeft = { x: minX, y: minY };
    const topRight = { x: maxX, y: minY };
    const bottomRight = { x: maxX, y: maxY };
    const bottomLeft = { x: minX, y: maxY };
    return [
      { start: topLeft, end: topRight },
      { start: topRight, end: bottomRight },
      { start: bottomRight, end: bottomLeft },
      { start: bottomLeft, end: topLeft },
    ];
  }

  function lotAreaSqm(lot) {
    return Math.abs((lot.corner_b.x - lot.corner_a.x) * (lot.corner_b.y - lot.corner_a.y));
  }

  function formatArea(cornerA, cornerB) {
    const area = Math.abs((cornerB.x - cornerA.x) * (cornerB.y - cornerA.y));
    return `${area.toFixed(2)} sqm`;
  }

  function formatRectangleSize(cornerA, cornerB) {
    const width = Math.abs(cornerB.x - cornerA.x);
    const depth = Math.abs(cornerB.y - cornerA.y);
    return `${width.toFixed(2)} m x ${depth.toFixed(2)} m`;
  }

  function formatRectangleBounds(bounds) {
    const width = Math.abs(bounds.maxX - bounds.minX);
    const depth = Math.abs(bounds.maxY - bounds.minY);
    return `${width.toFixed(2)} m x ${depth.toFixed(2)} m`;
  }

  function nearestWall(point, toleranceM) {
    let best = null;
    activeLevel().walls.forEach((wall) => {
      const projected = projectPointToWall(point, wall);
      if (projected.distance <= toleranceM && (!best || projected.distance < best.distance)) {
        best = { wall, distance: projected.distance, offset: projected.offset };
      }
    });
    return best;
  }

  function projectPointToWall(point, wall) {
    const horizontal = Math.abs(wall.start.y - wall.end.y) < 1e-9;
    if (horizontal) {
      const minX = Math.min(wall.start.x, wall.end.x);
      const maxX = Math.max(wall.start.x, wall.end.x);
      const clampedX = Math.max(minX, Math.min(maxX, point.x));
      const offset = Math.abs(clampedX - wall.start.x);
      return { distance: Math.abs(point.y - wall.start.y), offset };
    }
    const minY = Math.min(wall.start.y, wall.end.y);
    const maxY = Math.max(wall.start.y, wall.end.y);
    const clampedY = Math.max(minY, Math.min(maxY, point.y));
    const offset = Math.abs(clampedY - wall.start.y);
    return { distance: Math.abs(point.x - wall.start.x), offset };
  }

  function openingPoints(wall, opening) {
    const length = wallLengthM(wall);
    const startRatio = opening.offset_m / length;
    const endRatio = Math.min(length, opening.offset_m + opening.width_m) / length;
    const dx = wall.end.x - wall.start.x;
    const dy = wall.end.y - wall.start.y;
    return {
      start: { x: wall.start.x + dx * startRatio, y: wall.start.y + dy * startRatio },
      end: { x: wall.start.x + dx * endRatio, y: wall.start.y + dy * endRatio },
    };
  }

  function openingGeometry(opening, walls) {
    if (opening.start && opening.end) {
      return {
        points: { start: opening.start, end: opening.end },
        thicknessMm: opening.wall_thickness_mm || defaults.interiorWallThicknessMm,
      };
    }
    const wall = walls.get(opening.parent_wall_id);
    if (!wall) return null;
    return {
      points: openingPoints(wall, opening),
      thicknessMm: wall.thickness_mm,
      wall,
    };
  }

  function doorSwingGeometry(opening, walls) {
    const geometry = openingGeometry(opening, walls);
    if (!geometry) return null;
    const points = geometry.points;
    const hingeWorld = opening.hinge_side === "end" ? points.end : points.start;
    const latchWorld = opening.hinge_side === "end" ? points.start : points.end;
    const dx = latchWorld.x - hingeWorld.x;
    const dy = latchWorld.y - hingeWorld.y;
    const length = Math.hypot(dx, dy);
    if (length <= 0) return null;
    const tangent = { x: dx / length, y: dy / length };
    const normal = opening.swing_direction === "ccw"
      ? { x: tangent.y, y: -tangent.x }
      : { x: -tangent.y, y: tangent.x };
    const startAngle = Math.atan2(tangent.y, tangent.x);
    const endAngle = Math.atan2(normal.y, normal.x);
    return {
      hinge: hingeWorld,
      latch: latchWorld,
      thicknessMm: geometry.thicknessMm,
      screenTangent: tangent,
      screenNormal: normal,
      startAngle,
      endAngle,
      counterclockwise: opening.swing_direction === "ccw",
    };
  }

  function hitTest(point) {
    const level = activeLevel();
    for (const room of level.rooms) {
      if (distance(point, room.label) < 0.35) return { type: "room", item: room };
    }
    for (const dimension of level.dimensions) {
      const display = dimensionDisplayPoints(dimension);
      if (distanceToSegment(point, display.start, display.end) < 0.2) {
        return { type: "dimension", item: dimension };
      }
    }
    for (const opening of level.openings) {
      const geometry = openingGeometry(opening, wallMap());
      if (!geometry) continue;
      const points = geometry.points;
      if (distanceToSegment(point, points.start, points.end) < 0.22) {
        return { type: "opening", item: opening };
      }
    }
    for (const wall of level.walls) {
      if (distanceToSegment(point, wall.start, wall.end) < Math.max(0.2, wall.thickness_mm / 1000)) {
        return { type: "wall", item: wall };
      }
    }
    for (const draftLine of level.lines) {
      if (distanceToSegment(point, draftLine.start, draftLine.end) < 0.18) {
        return { type: "line", item: draftLine };
      }
    }
    for (const lot of level.lots) {
      if (lotSegments(lot).some((segment) => distanceToSegment(point, segment.start, segment.end) < 0.18)) {
        return { type: "lot", item: lot };
      }
    }
    return null;
  }

  function finishSelectionDrag(event) {
    const drag = selectionDrag;
    selectionDrag = null;
    const rect = canvas.getBoundingClientRect();
    const endScreen = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    const movePx = Math.hypot(endScreen.x - drag.startScreen.x, endScreen.y - drag.startScreen.y);
    if (movePx < 5) {
      const hit = hitTest(snapPoint(screenToWorld(event.clientX, event.clientY)));
      setSelection(hit ? [hit] : []);
      setStatus(hit ? `${hit.type} selected.` : "Nothing selected.");
      return;
    }

    const crossing = endScreen.x < drag.startScreen.x;
    const selectionRect = normalizedWorldRect(drag.startWorld, screenToWorld(event.clientX, event.clientY));
    const hits = allSelectableHits().filter((hit) => (
      crossing ? hitCrossesRect(hit, selectionRect) : hitInsideRect(hit, selectionRect)
    ));
    setSelection(hits);
    setStatus(
      `${crossing ? "Crossing" : "Window"} selection: ${hits.length} item${hits.length === 1 ? "" : "s"} selected.`
    );
  }

  function allSelectableHits() {
    const level = activeLevel();
    const hits = [];
    level.lots.forEach((item) => hits.push({ type: "lot", item }));
    level.lines.forEach((item) => hits.push({ type: "line", item }));
    level.walls.forEach((item) => hits.push({ type: "wall", item }));
    level.openings.forEach((item) => hits.push({ type: "opening", item }));
    level.rooms.forEach((item) => hits.push({ type: "room", item }));
    level.dimensions.forEach((item) => hits.push({ type: "dimension", item }));
    return hits;
  }

  function normalizedWorldRect(start, end) {
    return {
      minX: Math.min(start.x, end.x),
      maxX: Math.max(start.x, end.x),
      minY: Math.min(start.y, end.y),
      maxY: Math.max(start.y, end.y),
    };
  }

  function hitInsideRect(hit, rect) {
    const points = hitPoints(hit);
    return points.length > 0 && points.every((point) => pointInsideRect(point, rect));
  }

  function hitCrossesRect(hit, rect) {
    if (hitInsideRect(hit, rect)) return true;
    return hitSegments(hit).some((segment) => segmentIntersectsRect(segment.start, segment.end, rect));
  }

  function hitPoints(hit) {
    if (hit.type === "lot") {
      return lotCorners(hit.item);
    }
    if (hit.type === "dimension") {
      const display = dimensionDisplayPoints(hit.item);
      return [hit.item.start, hit.item.end, display.start, display.end];
    }
    if (hit.type === "line" || hit.type === "wall") {
      return [hit.item.start, hit.item.end];
    }
    if (hit.type === "room") {
      return [hit.item.label];
    }
    if (hit.type === "opening") {
      const geometry = openingGeometry(hit.item, wallMap());
      if (!geometry) return [];
      const points = geometry.points;
      return [points.start, points.end];
    }
    return [];
  }

  function hitSegments(hit) {
    if (hit.type === "lot") {
      return lotSegments(hit.item);
    }
    if (hit.type === "dimension") {
      const display = dimensionDisplayPoints(hit.item);
      return [
        { start: display.start, end: display.end },
        { start: hit.item.start, end: display.start },
        { start: hit.item.end, end: display.end },
      ];
    }
    if (hit.type === "line" || hit.type === "wall") {
      return [{ start: hit.item.start, end: hit.item.end }];
    }
    if (hit.type === "opening") {
      const geometry = openingGeometry(hit.item, wallMap());
      if (!geometry) return [];
      const points = geometry.points;
      return [{ start: points.start, end: points.end }];
    }
    return [];
  }

  function pointInsideRect(point, rect) {
    return point.x >= rect.minX && point.x <= rect.maxX && point.y >= rect.minY && point.y <= rect.maxY;
  }

  function segmentIntersectsRect(start, end, rect) {
    if (pointInsideRect(start, rect) || pointInsideRect(end, rect)) return true;
    if (Math.abs(start.y - end.y) < 1e-9) {
      const minX = Math.min(start.x, end.x);
      const maxX = Math.max(start.x, end.x);
      return start.y >= rect.minY && start.y <= rect.maxY && maxX >= rect.minX && minX <= rect.maxX;
    }
    if (Math.abs(start.x - end.x) < 1e-9) {
      const minY = Math.min(start.y, end.y);
      const maxY = Math.max(start.y, end.y);
      return start.x >= rect.minX && start.x <= rect.maxX && maxY >= rect.minY && minY <= rect.maxY;
    }
    return false;
  }

  function removeHit(hit) {
    const level = activeLevel();
    if (hit.type === "lot") {
      level.lots = level.lots.filter((lot) => lot.lot_id !== hit.item.lot_id);
    } else if (hit.type === "line") {
      level.lines = level.lines.filter((lineItem) => lineItem.line_id !== hit.item.line_id);
    } else if (hit.type === "wall") {
      level.walls = level.walls.filter((wall) => wall.wall_id !== hit.item.wall_id);
      level.openings = level.openings.filter((opening) => opening.parent_wall_id !== hit.item.wall_id);
      level.rooms.forEach((room) => {
        room.boundary_wall_ids = room.boundary_wall_ids.filter((wallId) => wallId !== hit.item.wall_id);
      });
    } else if (hit.type === "opening") {
      level.openings = level.openings.filter((opening) => opening.opening_id !== hit.item.opening_id);
    } else if (hit.type === "room") {
      level.rooms = level.rooms.filter((room) => room.room_id !== hit.item.room_id);
    } else if (hit.type === "dimension") {
      level.dimensions = level.dimensions.filter((dimension) => dimension.dimension_id !== hit.item.dimension_id);
    }
  }

  function splitWallAroundOpening(level, wall, points) {
    const replacementWalls = [];
    const before = wallSegmentClone(wall, wall.start, points.start, "a");
    const after = wallSegmentClone(wall, points.end, wall.end, "b");
    if (before) replacementWalls.push(before);
    if (after) replacementWalls.push(after);

    level.walls = level.walls.filter((wallItem) => wallItem.wall_id !== wall.wall_id);
    level.walls.push(...replacementWalls);
    reassignRoomBoundaryWallIds(level, wall.wall_id, replacementWalls.map((replacement) => replacement.wall_id));
    reassignOpeningsFromSplitWall(level, wall, replacementWalls);
  }

  function wallSegmentClone(wall, start, end, suffix) {
    if (samePoint(start, end)) return null;
    return {
      wall_id: uid(`${wall.wall_id}-${suffix}`),
      start: clone(start),
      end: clone(end),
      wall_type: wall.wall_type,
      thickness_mm: wall.thickness_mm,
      exterior: wall.exterior,
    };
  }

  function reassignRoomBoundaryWallIds(level, oldWallId, replacementWallIds) {
    level.rooms.forEach((room) => {
      if (!room.boundary_wall_ids.includes(oldWallId)) return;
      room.boundary_wall_ids = room.boundary_wall_ids.flatMap((wallId) => (
        wallId === oldWallId ? replacementWallIds : [wallId]
      ));
    });
  }

  function reassignOpeningsFromSplitWall(level, oldWall, replacementWalls) {
    level.openings = level.openings
      .map((opening) => {
        if (opening.parent_wall_id !== oldWall.wall_id) return opening;
        const points = openingPoints(oldWall, opening);
        const parentWall = replacementWalls.find((wall) => pointOnSegment(points.start, wall.start, wall.end) && pointOnSegment(points.end, wall.start, wall.end));
        if (!parentWall) return null;
        const nextOpening = clone(opening);
        nextOpening.parent_wall_id = parentWall.wall_id;
        nextOpening.offset_m = roundM(offsetAlongWall(points.start, parentWall));
        return nextOpening;
      })
      .filter(Boolean);
  }

  function trimAt(point) {
    const hit = hitTest(point);
    if (!hit || !["line", "wall"].includes(hit.type)) {
      setStatus("Trim needs a draft line or wall.");
      return;
    }

    const intersections = trimIntersections(hit);
    if (!intersections.length) {
      setStatus("No crossing line or wall found to trim to.");
      return;
    }

    const clickT = segmentParameter(point, hit.item.start, hit.item.end);
    const trim = intersections.reduce((best, candidate) => {
      if (!best || Math.abs(candidate.t - clickT) < Math.abs(best.t - clickT)) return candidate;
      return best;
    }, null);
    if (!trim) return;

    const trimStart = clickT <= trim.t;
    const newStart = trimStart ? trim.point : hit.item.start;
    const newEnd = trimStart ? hit.item.end : trim.point;
    if (samePoint(newStart, newEnd)) {
      setStatus("Trim ignored: result would have zero length.");
      return;
    }

    remember();
    const oldStart = clone(hit.item.start);
    const oldEnd = clone(hit.item.end);
    hit.item.start = clone(newStart);
    hit.item.end = clone(newEnd);
    if (hit.type === "wall") {
      reconcileOpeningsAfterWallTrim(hit.item, oldStart, oldEnd);
    }
    selected = hit;
    selectedItems = [hit];
    updateStats();
    draw();
    setStatus(`${hit.type === "wall" ? "Wall" : "Draft line"} trimmed.`);
  }

  function trimIntersections(targetHit) {
    const targetId = entityId(targetHit);
    return allSelectableHits()
      .filter((hit) => ["line", "wall"].includes(hit.type) && entityId(hit) !== targetId)
      .map((hit) => segmentIntersection(targetHit.item.start, targetHit.item.end, hit.item.start, hit.item.end))
      .filter((intersection) => intersection && intersection.t > 1e-9 && intersection.t < 1 - 1e-9);
  }

  function extendAt(point) {
    const hit = hitTest(point);
    if (!hit || !["line", "wall"].includes(hit.type)) {
      setStatus("Extend needs a draft line or wall.");
      return;
    }

    const extension = nearestExtension(hit, point);
    if (!extension) {
      setStatus("No crossing line or wall found to extend to.");
      return;
    }

    remember();
    const oldStart = clone(hit.item.start);
    const oldEnd = clone(hit.item.end);
    if (extension.extendStart) {
      hit.item.start = extension.point;
    } else {
      hit.item.end = extension.point;
    }
    if (hit.type === "wall") {
      reconcileOpeningsAfterWallTrim(hit.item, oldStart, oldEnd);
    }
    selected = hit;
    selectedItems = [hit];
    updateStats();
    draw();
    setStatus(`${hit.type === "wall" ? "Wall" : "Draft line"} extended.`);
  }

  function nearestExtension(targetHit, clickPoint) {
    const clickT = segmentParameter(clickPoint, targetHit.item.start, targetHit.item.end);
    const extendStart = clickT < 0.5;
    const endpoint = extendStart ? targetHit.item.start : targetHit.item.end;
    const otherEndpoint = extendStart ? targetHit.item.end : targetHit.item.start;
    const targetId = entityId(targetHit);
    return allSelectableHits()
      .filter((hit) => ["line", "wall"].includes(hit.type) && entityId(hit) !== targetId)
      .map((hit) => extensionIntersection(endpoint, otherEndpoint, hit.item.start, hit.item.end, extendStart))
      .filter(Boolean)
      .reduce((best, candidate) => (!best || candidate.distance < best.distance ? candidate : best), null);
  }

  function extensionIntersection(endpoint, otherEndpoint, candidateStart, candidateEnd, extendStart) {
    const targetHorizontal = Math.abs(endpoint.y - otherEndpoint.y) < 1e-9;
    const candidateHorizontal = Math.abs(candidateStart.y - candidateEnd.y) < 1e-9;
    if (targetHorizontal === candidateHorizontal) return null;

    const point = targetHorizontal
      ? { x: candidateStart.x, y: endpoint.y }
      : { x: endpoint.x, y: candidateStart.y };
    if (!pointOnSegment(point, candidateStart, candidateEnd)) return null;

    const direction = {
      x: endpoint.x - otherEndpoint.x,
      y: endpoint.y - otherEndpoint.y,
    };
    const delta = {
      x: point.x - endpoint.x,
      y: point.y - endpoint.y,
    };
    const alongRay = Math.abs(direction.x) >= Math.abs(direction.y)
      ? delta.x * direction.x > 1e-9
      : delta.y * direction.y > 1e-9;
    if (!alongRay) return null;

    return {
      point: { x: roundM(point.x), y: roundM(point.y) },
      distance: Math.hypot(delta.x, delta.y),
      extendStart,
    };
  }

  function segmentIntersection(aStart, aEnd, bStart, bEnd) {
    const aHorizontal = Math.abs(aStart.y - aEnd.y) < 1e-9;
    const bHorizontal = Math.abs(bStart.y - bEnd.y) < 1e-9;
    if (aHorizontal === bHorizontal) return null;

    const horizontal = aHorizontal ? { start: aStart, end: aEnd } : { start: bStart, end: bEnd };
    const vertical = aHorizontal ? { start: bStart, end: bEnd } : { start: aStart, end: aEnd };
    const point = { x: vertical.start.x, y: horizontal.start.y };
    if (!pointOnSegment(point, horizontal.start, horizontal.end) || !pointOnSegment(point, vertical.start, vertical.end)) {
      return null;
    }
    return {
      point: { x: roundM(point.x), y: roundM(point.y) },
      t: segmentParameter(point, aStart, aEnd),
    };
  }

  function pointOnSegment(point, start, end) {
    const minX = Math.min(start.x, end.x) - 1e-9;
    const maxX = Math.max(start.x, end.x) + 1e-9;
    const minY = Math.min(start.y, end.y) - 1e-9;
    const maxY = Math.max(start.y, end.y) + 1e-9;
    return point.x >= minX && point.x <= maxX && point.y >= minY && point.y <= maxY;
  }

  function segmentParameter(point, start, end) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    if (Math.abs(dx) >= Math.abs(dy)) {
      return dx === 0 ? 0 : (point.x - start.x) / dx;
    }
    return dy === 0 ? 0 : (point.y - start.y) / dy;
  }

  function reconcileOpeningsAfterWallTrim(wall, oldStart, oldEnd) {
    const newLength = wallLengthM(wall);
    activeLevel().openings = activeLevel().openings
      .map((opening) => {
        if (opening.parent_wall_id !== wall.wall_id) return opening;
        const oldPoints = openingPoints({ start: oldStart, end: oldEnd }, opening);
        const nextOpening = clone(opening);
        nextOpening.offset_m = roundM(offsetAlongWall(oldPoints.start, wall));
        return nextOpening;
      })
      .filter((opening) => {
        if (opening.parent_wall_id !== wall.wall_id) return true;
        if (newLength <= 0) return false;
        return opening.offset_m >= 0 && opening.offset_m + opening.width_m <= newLength + 1e-9;
      });
  }

  function offsetAlongWall(point, wall) {
    return segmentParameter(point, wall.start, wall.end) * wallLengthM(wall);
  }

  function rotateSelectedDoor() {
    const hits = selectedItems.length ? selectedItems : [selected].filter(Boolean);
    const doorHit = hits.find((hit) => hit.type === "opening" && hit.item.opening_type === "door");
    if (!doorHit) {
      setStatus("Select a door before using ROTATE.");
      return;
    }
    remember();
    doorHit.item.swing_direction = doorHit.item.swing_direction === "ccw" ? "cw" : "ccw";
    setStatus(`Door swing rotated ${doorHit.item.swing_direction.toUpperCase()}.`);
    draw();
  }

  function removeSelectedItems() {
    const hits = selectedItems.length ? selectedItems : [selected].filter(Boolean);
    if (!hits.length) return;
    remember();
    hits.forEach((hit) => removeHit(hit));
    selected = null;
    selectedItems = [];
    updateStats();
    draw();
    setStatus(`${hits.length} item${hits.length === 1 ? "" : "s"} erased.`);
  }

  function translateHit(hit, dx, dy) {
    if (hit.type === "lot") {
      hit.item.corner_a = translatePoint(hit.item.corner_a, dx, dy);
      hit.item.corner_b = translatePoint(hit.item.corner_b, dx, dy);
    } else if (hit.type === "line") {
      hit.item.start = translatePoint(hit.item.start, dx, dy);
      hit.item.end = translatePoint(hit.item.end, dx, dy);
    } else if (hit.type === "wall") {
      hit.item.start = translatePoint(hit.item.start, dx, dy);
      hit.item.end = translatePoint(hit.item.end, dx, dy);
    } else if (hit.type === "room") {
      hit.item.label = translatePoint(hit.item.label, dx, dy);
    } else if (hit.type === "dimension") {
      hit.item.start = translatePoint(hit.item.start, dx, dy);
      hit.item.end = translatePoint(hit.item.end, dx, dy);
    }
  }

  function copyHit(hit, dx, dy) {
    const level = activeLevel();
    const item = clone(hit.item);
    if (hit.type === "lot") {
      item.lot_id = uid("lot");
      item.corner_a = translatePoint(item.corner_a, dx, dy);
      item.corner_b = translatePoint(item.corner_b, dx, dy);
      level.lots.push(item);
    } else if (hit.type === "line") {
      item.line_id = uid("line");
      item.start = translatePoint(item.start, dx, dy);
      item.end = translatePoint(item.end, dx, dy);
      level.lines.push(item);
    } else if (hit.type === "wall") {
      item.wall_id = uid("wall");
      item.start = translatePoint(item.start, dx, dy);
      item.end = translatePoint(item.end, dx, dy);
      level.walls.push(item);
    } else if (hit.type === "room") {
      item.room_id = uid("room");
      item.label = translatePoint(item.label, dx, dy);
      level.rooms.push(item);
    } else if (hit.type === "dimension") {
      item.dimension_id = uid("dimension");
      item.start = translatePoint(item.start, dx, dy);
      item.end = translatePoint(item.end, dx, dy);
      level.dimensions.push(item);
    } else if (hit.type === "opening") {
      item.opening_id = uid(item.opening_type);
      level.openings.push(item);
    }
  }

  function queueKeyboardCommand(command) {
    const nextBuffer = `${keyboardCommandBuffer}${command}`;
    clearTimeout(keyboardCommandTimer);
    keyboardCommandTimer = setTimeout(() => {
      keyboardCommandBuffer = "";
    }, 900);

    if (commandAliases[nextBuffer]) {
      keyboardCommandBuffer = "";
      executeCommand(nextBuffer);
      return true;
    }
    if (Object.keys(commandAliases).some((alias) => alias.startsWith(nextBuffer))) {
      keyboardCommandBuffer = nextBuffer;
      return true;
    }
    keyboardCommandBuffer = "";
    if (commandAliases[command]) {
      executeCommand(command);
      return true;
    }
    return false;
  }

  function translatePoint(point, dx, dy) {
    return { x: roundM(point.x + dx), y: roundM(point.y + dy) };
  }

  function distance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function distanceToSegment(point, start, end) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const lengthSq = dx * dx + dy * dy;
    if (lengthSq === 0) return distance(point, start);
    let t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));
    return distance(point, { x: start.x + t * dx, y: start.y + t * dy });
  }

  function samePoint(a, b) {
    return Math.abs(a.x - b.x) < 1e-9 && Math.abs(a.y - b.y) < 1e-9;
  }

  function roundM(value) {
    return Math.round(value * 1000) / 1000;
  }

  function formatDistance(start, end) {
    return `${Math.hypot(end.x - start.x, end.y - start.y).toFixed(2)} m`;
  }

  function dimensionOffsetFromPlacement(start, end, placement) {
    if (Math.abs(start.y - end.y) < 1e-9) {
      return roundM(placement.y - start.y);
    }
    return roundM(placement.x - start.x);
  }

  function dimensionDisplayPoints(dimension) {
    const offset = dimension.offset_m || 0;
    if (Math.abs(dimension.start.y - dimension.end.y) < 1e-9) {
      return {
        start: { x: dimension.start.x, y: roundM(dimension.start.y + offset) },
        end: { x: dimension.end.x, y: roundM(dimension.end.y + offset) },
      };
    }
    return {
      start: { x: roundM(dimension.start.x + offset), y: dimension.start.y },
      end: { x: roundM(dimension.end.x + offset), y: dimension.end.y },
    };
  }

  async function downloadJson() {
    const normalized = await validateProject();
    if (!normalized) return;
    project = normalized;
    downloadBlob(JSON.stringify(project, null, 2), "abscissa-plan.json", "application/json");
    setStatus("Project JSON saved.");
  }

  async function validateProject() {
    try {
      const response = await fetch("/api/validate-project", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(project),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setStatus(`Project validation failed: ${payload.error || response.statusText}`);
        return null;
      }
      return payload.project;
    } catch (error) {
      setStatus(`Project validation failed: ${error.message}`);
      return null;
    }
  }

  async function exportSvg() {
    try {
      const response = await fetch("/api/export/svg", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(project),
      });
      if (!response.ok) {
        const payload = await response.json();
        setStatus(`SVG export failed: ${payload.error || response.statusText}`);
        return;
      }
      const svg = await response.text();
      downloadBlob(svg, "abscissa-plan.svg", "image/svg+xml");
      setStatus("SVG exported.");
    } catch (error) {
      setStatus(`SVG export failed: ${error.message}`);
    }
  }

  function exportPng() {
    canvas.toBlob((blob) => {
      if (!blob) {
        setStatus("PNG export failed.");
        return;
      }
      downloadBlob(blob, "abscissa-plan.png", "image/png");
      setStatus("PNG exported.");
    });
  }

  function downloadBlob(content, filename, type) {
    const blob = content instanceof Blob ? content : new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function loadProjectFromFile(file) {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const candidate = JSON.parse(reader.result);
        const response = await fetch("/api/validate-project", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(candidate),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          setStatus(`Open failed: ${payload.error || response.statusText}`);
          return;
        }
        remember();
        project = payload.project;
        clearTransient();
        draw();
        setStatus("Project loaded.");
      } catch (error) {
        setStatus(`Open failed: ${error.message}`);
      }
    };
    reader.readAsText(file);
  }

  function updateStats() {
    const level = activeLevel();
    document.getElementById("lotCount").textContent = String(level.lots.length);
    document.getElementById("lineCount").textContent = String(level.lines.length);
    document.getElementById("wallCount").textContent = String(level.walls.length);
    document.getElementById("openingCount").textContent = String(level.openings.length);
    document.getElementById("roomCount").textContent = String(level.rooms.length);
    document.getElementById("dimensionCount").textContent = String(level.dimensions.length);
  }

  function selectedDoor() {
    if (selectedItems.length > 1) return null;
    if (selected && selected.type === "opening" && selected.item.opening_type === "door") {
      return selected.item;
    }
    return null;
  }

  function syncDoorPanel() {
    if (!doorPanel) return;
    const door = selectedDoor();
    if (!door) {
      doorPanel.hidden = true;
      lastDoorPanelId = null;
      return;
    }
    doorPanel.hidden = false;
    if (door.opening_id === lastDoorPanelId) return;
    lastDoorPanelId = door.opening_id;
    if (doorLeafWidthEl) doorLeafWidthEl.value = Math.round(doorLeafWidthMeters(door) * 1000);
    if (doorJambEl) doorJambEl.value = Math.round(doorJambMeters(door) * 1000);
    if (doorLeafThicknessEl) {
      doorLeafThicknessEl.value = Math.round(
        door.leaf_thickness_mm || doorStyle.leaf_thickness_mm || 45,
      );
    }
    if (doorSwingEl) doorSwingEl.value = door.swing_direction || "cw";
    if (doorHingeSideEl) doorHingeSideEl.value = door.hinge_side || "start";
  }

  function applyDoorEdit(mutate) {
    const door = selectedDoor();
    if (!door) return;
    remember();
    mutate(door);
    if (doorLeafWidthEl) doorLeafWidthEl.value = Math.round(doorLeafWidthMeters(door) * 1000);
    updateStats();
    draw();
  }

  function updateSelectionSummary() {
    syncDoorPanel();
    const el = document.getElementById("selectionSummary");
    if (!selected) {
      el.textContent = "Nothing selected.";
      return;
    }
    if (selectedItems.length > 1) {
      const counts = selectedItems.reduce((acc, hit) => {
        acc[hit.type] = (acc[hit.type] || 0) + 1;
        return acc;
      }, {});
      el.textContent = Object.entries(counts)
        .map(([type, count]) => `${count} ${type}${count === 1 ? "" : "s"}`)
        .join(", ");
      return;
    }
    if (selected.type === "lot") {
      const lot = selected.item;
      el.textContent = `${lot.name || "Lot Area"}, ${lotAreaSqm(lot).toFixed(2)} sqm, thin dashed boundary.`;
    } else if (selected.type === "line") {
      const draftLine = selected.item;
      el.textContent = `${draftLineLabel(draftLine)}, ${formatDistance(draftLine.start, draftLine.end)}.`;
    } else if (selected.type === "wall") {
      const wall = selected.item;
      el.textContent = `${wall.wall_type} wall, ${wallLengthM(wall).toFixed(2)} m, ${wall.thickness_mm} mm thick.`;
    } else if (selected.type === "opening") {
      const opening = selected.item;
      const swing = opening.opening_type === "door" ? `, ${opening.swing_direction || "cw"} swing` : "";
      if (opening.opening_type === "door") {
        const leafWidth = doorLeafWidthMeters(opening);
        el.textContent = `door, ${leafWidth.toFixed(2)} m leaf, ${opening.width_m.toFixed(2)} m framed opening${swing}.`;
      } else {
        el.textContent = `${opening.opening_type}, ${opening.width_m.toFixed(2)} m wide${swing}.`;
      }
    } else if (selected.type === "room") {
      el.textContent = `${selected.item.name} (${selected.item.room_type}).`;
    } else if (selected.type === "dimension") {
      const dimension = selected.item;
      el.textContent = `${dimensionBasisLabel(dimension.basis)} dimension, ${dimension.label || formatDistance(dimension.start, dimension.end)}.`;
    }
  }

  function draftLineLabel(draftLine) {
    const labels = {
      draft: "draft line",
      setback: "setback line",
      grid: "grid line",
      wall_centerline: "wall centerline",
    };
    const label = labels[draftLine.line_type] || "draft line";
    return draftLine.layer ? `${label} (${draftLine.layer})` : label;
  }

  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => executeCommand(button.dataset.command));
  });

  createLotButton.addEventListener("click", createLotFromInputs);
  createSetbackButton.addEventListener("click", createSetbackFromInputs);
  createGridButton.addEventListener("click", createGridFromInputs);
  createWallCenterlineButton.addEventListener("click", createWallCenterlineFromReference);

  commandLine.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    handleCommandLineInput(commandLine.value);
    commandLine.value = "";
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) {
      loadProjectFromFile(fileInput.files[0]);
    }
    fileInput.value = "";
  });

  dimensionBasisEl.addEventListener("change", () => {
    if (tool === "dimension") {
      setStatus(`Dimension (${dimensionBasisLabel()}): click first endpoint, click second endpoint, then click to place the dimension line.`);
    }
    draw();
  });

  canvas.addEventListener("pointerdown", (event) => {
    if (tool === "pan" && event.button === 0) {
      startPan(event);
      return;
    }
    if (event.button === 1 || event.shiftKey || event.code === "Space") {
      startPan(event);
      return;
    }
    if (tool === "select" && event.button === 0) {
      const rect = canvas.getBoundingClientRect();
      selectionDrag = {
        startScreen: { x: event.clientX - rect.left, y: event.clientY - rect.top },
        currentScreen: { x: event.clientX - rect.left, y: event.clientY - rect.top },
        startWorld: screenToWorld(event.clientX, event.clientY),
        currentWorld: screenToWorld(event.clientX, event.clientY),
      };
      canvas.setPointerCapture(event.pointerId);
      return;
    }
    handlePrimaryClick(event);
  });

  function startPan(event) {
    isPanning = true;
    panAnchor = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
    canvas.setPointerCapture(event.pointerId);
    updateBoardCursor();
  }

  canvas.addEventListener("pointermove", (event) => {
    if (isPanning && panAnchor) {
      view.x = panAnchor.viewX + event.clientX - panAnchor.x;
      view.y = panAnchor.viewY + event.clientY - panAnchor.y;
      draw();
      return;
    }
    const rawPoint = screenToWorld(event.clientX, event.clientY);
    snapCandidate = nearestSnapEndpoint(rawPoint);
    hoverPoint = snapPoint(rawPoint);
    coordinateReadout.textContent = `X ${hoverPoint.x.toFixed(2)}, Y ${hoverPoint.y.toFixed(2)}`;
    if (selectionDrag) {
      const rect = canvas.getBoundingClientRect();
      selectionDrag.currentScreen = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      selectionDrag.currentWorld = rawPoint;
    }
    draw();
  });

  canvas.addEventListener("pointerup", (event) => {
    if (isPanning) {
      isPanning = false;
      panAnchor = null;
      canvas.releasePointerCapture(event.pointerId);
      updateBoardCursor();
    }
    if (selectionDrag) {
      finishSelectionDrag(event);
      canvas.releasePointerCapture(event.pointerId);
    }
  });

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    const before = screenToWorld(event.clientX, event.clientY);
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    view.scale = Math.max(25, Math.min(220, view.scale * factor));
    const rect = canvas.getBoundingClientRect();
    view.x = event.clientX - rect.left - before.x * view.scale;
    view.y = event.clientY - rect.top - before.y * view.scale;
    draw();
  }, { passive: false });

  window.addEventListener("keydown", (event) => {
    if (event.target === commandLine || event.target.tagName === "INPUT" || event.target.tagName === "SELECT") {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      deselect();
      return;
    }
    if (event.metaKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      event.shiftKey ? redo() : undo();
      return;
    }
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      if (selected) {
        removeSelectedItems();
      }
      return;
    }
    if (!event.metaKey && !event.ctrlKey && !event.altKey && event.key.length === 1) {
      const command = event.key.toUpperCase();
      if (queueKeyboardCommand(command)) {
        event.preventDefault();
      }
    }
  });

  window.addEventListener("resize", resizeCanvas);

  function clampMm(value, fallback, min, max) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.max(min, Math.min(max, parsed));
  }

  if (doorJambEl) {
    doorJambEl.addEventListener("change", () => {
      applyDoorEdit((door) => {
        door.frame_jamb_mm = clampMm(doorJambEl.value, doorStyle.frame_jamb_mm || 50, 5, 200);
      });
      setStatus("Door frame/jamb updated.");
    });
  }
  if (doorLeafThicknessEl) {
    doorLeafThicknessEl.addEventListener("change", () => {
      applyDoorEdit((door) => {
        door.leaf_thickness_mm = clampMm(doorLeafThicknessEl.value, doorStyle.leaf_thickness_mm || 45, 10, 120);
      });
      setStatus("Door leaf thickness updated.");
    });
  }
  if (doorSwingEl) {
    doorSwingEl.addEventListener("change", () => {
      applyDoorEdit((door) => {
        door.swing_direction = doorSwingEl.value === "ccw" ? "ccw" : "cw";
      });
      setStatus(`Door swing set to ${doorSwingEl.value.toUpperCase()}.`);
    });
  }
  if (doorHingeSideEl) {
    doorHingeSideEl.addEventListener("change", () => {
      applyDoorEdit((door) => {
        door.hinge_side = doorHingeSideEl.value === "end" ? "end" : "start";
      });
      setStatus(`Door hinge set to ${doorHingeSideEl.value} side.`);
    });
  }

  function loadDoorStyle() {
    fetch("/door_style.json")
      .then((response) => (response.ok ? response.json() : null))
      .then((style) => {
        if (!style) return;
        doorStyle = Object.assign({}, doorStyle, style);
        doorStyle.colors = Object.assign({}, doorStyle.colors, style.colors || {});
        lastDoorPanelId = null;
        draw();
      })
      .catch(() => {
        /* keep inline fallback door style */
      });
  }

  function resetAppScroll() {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
    const panel = document.querySelector(".panel");
    if (panel) panel.scrollTop = 0;
  }

  window.AbscissaCad = {
    commandAliases,
    getProject: () => clone(project),
    executeCommand,
    getDoorStyle: () => clone(doorStyle),
  };

  loadDoorStyle();
  resetAppScroll();
  resizeCanvas();
  setTool("select");
})();
