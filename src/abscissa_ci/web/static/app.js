const samples = {
  polygon: {
    project_name: "Sample L Shape Floor Plan",
    input_source: "manual",
    polygons: [
      {
        name: "L Shape Footprint",
        operation: "add",
        points: [
          { x_m: 0, y_m: 0 },
          { x_m: 12, y_m: 0 },
          { x_m: 12, y_m: 5 },
          { x_m: 7, y_m: 5 },
          { x_m: 7, y_m: 9 },
          { x_m: 0, y_m: 9 }
        ],
        edge_labels: [
          { edge_index: 0, length_m: 12, source_text: "12.00 m" },
          { edge_index: 1, length_m: 5, source_text: "5.00 m" },
          { edge_index: 2, length_m: 5, source_text: "5.00 m" },
          { edge_index: 3, length_m: 4, source_text: "4.00 m" },
          { edge_index: 4, length_m: 7, source_text: "7.00 m" },
          { edge_index: 5, length_m: 9, source_text: "9.00 m" }
        ],
        source_text: "L shape floor plan dimensions in meters"
      }
    ],
    waste_percent: 10,
    assumptions: [
      "Vertex coordinates are derived from labeled metric dimensions."
    ]
  },
  rectangles: {
    project_name: "Sample L Shape Rectangles",
    input_source: "manual",
    rectangles: [
      {
        name: "Lower Wing",
        length_m: 12,
        width_m: 5,
        operation: "add",
        source_text: "12.00 m x 5.00 m"
      },
      {
        name: "Upper Wing",
        length_m: 7,
        width_m: 4,
        operation: "add",
        source_text: "7.00 m x 4.00 m"
      }
    ],
    waste_percent: 10,
    assumptions: [
      "The L shape is decomposed into non-overlapping rectangles."
    ]
  },
  void: {
    project_name: "Sample Floor With Void",
    input_source: "manual",
    polygons: [
      {
        name: "Outer Floor",
        operation: "add",
        points: [
          { x_m: 0, y_m: 0 },
          { x_m: 16, y_m: 0 },
          { x_m: 16, y_m: 10 },
          { x_m: 0, y_m: 10 }
        ],
        edge_labels: [
          { edge_index: 0, length_m: 16, source_text: "16.00 m" },
          { edge_index: 1, length_m: 10, source_text: "10.00 m" }
        ],
        source_text: "Outer floor boundary"
      },
      {
        name: "Interior Void",
        operation: "subtract",
        points: [
          { x_m: 5, y_m: 3 },
          { x_m: 10, y_m: 3 },
          { x_m: 10, y_m: 6 },
          { x_m: 5, y_m: 6 }
        ],
        edge_labels: [
          { edge_index: 0, length_m: 5, source_text: "5.00 m" },
          { edge_index: 1, length_m: 3, source_text: "3.00 m" }
        ],
        source_text: "Interior opening"
      }
    ],
    waste_percent: 10,
    assumptions: [
      "The interior void is excluded from tiled floor area."
    ]
  }
};

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

const PROGRESS_STEPS = [
  "Surveying the printed dimensions…",
  "Deriving the station grid…",
  "Classifying floor cells…",
  "Validating the geometry…",
  "Still working — complex plans retry with validator feedback…"
];

const els = {};
const state = {
  stagedFile: null,
  stagedUrl: null,
  busy: false,
  progressTimer: null
};

document.addEventListener("DOMContentLoaded", () => {
  [
    "reviewStatus",
    "composer",
    "dropzone",
    "fileInput",
    "staged",
    "stagedThumb",
    "stagedName",
    "stagedMeta",
    "removeStaged",
    "computeArea",
    "progress",
    "progressText",
    "workspaceResults",
    "exampleResults",
    "projectJson",
    "runJson",
    "formatJson"
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });

  wireTabs();
  wireComposer();
  wireExamples();

  els.workspaceResults.innerHTML = emptyState(
    "No analysis yet. Drop a floor plan above and press Compute Area."
  );
  els.exampleResults.innerHTML = emptyState(
    "Run an example to see the full solution layout."
  );
  setInput(samples.polygon);
});

/* ---------- tabs ---------- */

function wireTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab"));
  const pages = {
    workspace: document.getElementById("tab-workspace"),
    examples: document.getElementById("tab-examples")
  };
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((other) => {
        const active = other === tab;
        other.classList.toggle("active", active);
        other.setAttribute("aria-selected", String(active));
      });
      Object.entries(pages).forEach(([name, page]) => {
        const active = name === tab.dataset.tab;
        page.classList.toggle("active", active);
        page.hidden = !active;
      });
    });
  });
}

/* ---------- composer: stage image, compute ---------- */

function wireComposer() {
  els.dropzone.addEventListener("click", () => els.fileInput.click());
  els.dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      els.fileInput.click();
    }
  });

  ["dragover", "dragenter"].forEach((type) => {
    els.composer.addEventListener(type, (event) => {
      event.preventDefault();
      els.composer.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((type) => {
    els.composer.addEventListener(type, (event) => {
      event.preventDefault();
      els.composer.classList.remove("drag-over");
    });
  });
  els.composer.addEventListener("drop", (event) => {
    if (!state.busy) {
      stageFile(event.dataTransfer.files[0]);
    }
  });

  els.fileInput.addEventListener("change", () => {
    stageFile(els.fileInput.files[0]);
    els.fileInput.value = "";
  });

  els.removeStaged.addEventListener("click", clearStaged);
  els.computeArea.addEventListener("click", computeFromImage);
}

function stageFile(file) {
  if (!file) {
    return;
  }
  if (!IMAGE_TYPES.includes(file.type)) {
    els.workspaceResults.innerHTML = errorPanel(
      "Unsupported image type",
      "Use a PNG, JPG, or WEBP floor plan image."
    );
    return;
  }

  if (state.stagedUrl) {
    URL.revokeObjectURL(state.stagedUrl);
  }
  state.stagedFile = file;
  state.stagedUrl = URL.createObjectURL(file);

  els.stagedThumb.src = state.stagedUrl;
  els.stagedName.textContent = file.name;
  els.stagedMeta.textContent = `${file.type.replace("image/", "").toUpperCase()} · ${formatBytes(file.size)}`;
  els.staged.hidden = false;
  els.dropzone.hidden = true;
  els.computeArea.disabled = false;
}

function clearStaged() {
  if (state.stagedUrl) {
    URL.revokeObjectURL(state.stagedUrl);
  }
  state.stagedFile = null;
  state.stagedUrl = null;
  els.staged.hidden = true;
  els.dropzone.hidden = false;
  els.computeArea.disabled = true;
}

async function computeFromImage() {
  if (!state.stagedFile || state.busy) {
    return;
  }

  setBusy(true);
  els.workspaceResults.innerHTML = "";
  try {
    const dataUrl = await readFileAsDataUrl(state.stagedFile);
    const extractResponse = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: state.stagedFile.name,
        image_data_url: dataUrl
      })
    });
    const extractResult = await extractResponse.json();
    if (!extractResponse.ok) {
      els.workspaceResults.innerHTML = errorPanel(
        "Extraction unavailable",
        extractResult.message || "The floor plan image could not be extracted."
      );
      return;
    }

    setProgressText("Computing area and tile count…");
    const estimateResponse = await fetch("/api/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(extractResult.estimate_input)
    });
    const result = await estimateResponse.json();
    if (!estimateResponse.ok) {
      els.workspaceResults.innerHTML = errorPanel(
        "Estimate failed",
        result.message || "The extracted geometry could not be computed."
      );
      return;
    }

    renderResultInto(els.workspaceResults, result, extractResult.estimate_input);
  } catch (error) {
    els.workspaceResults.innerHTML = errorPanel(
      "Request failed",
      "The local estimate server did not respond. Is abscissa-serve running?"
    );
  } finally {
    setBusy(false);
  }
}

function setBusy(busy) {
  state.busy = busy;
  els.computeArea.disabled = busy || !state.stagedFile;
  els.computeArea.textContent = busy ? "Computing…" : "Compute Area";
  els.progress.hidden = !busy;
  els.dropzone.classList.toggle("busy", busy);

  if (busy) {
    let step = 0;
    setProgressText(PROGRESS_STEPS[0]);
    state.progressTimer = setInterval(() => {
      step = Math.min(step + 1, PROGRESS_STEPS.length - 1);
      setProgressText(PROGRESS_STEPS[step]);
    }, 14000);
  } else if (state.progressTimer) {
    clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}

function setProgressText(text) {
  els.progressText.textContent = text;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/* ---------- examples + manual JSON ---------- */

function wireExamples() {
  document.querySelectorAll("[data-sample]").forEach((button) => {
    button.addEventListener("click", () => {
      setInput(samples[button.dataset.sample]);
      runEstimateInto(els.exampleResults, samples[button.dataset.sample]);
    });
  });

  els.runJson.addEventListener("click", () => {
    let payload;
    try {
      payload = JSON.parse(els.projectJson.value);
    } catch (error) {
      els.exampleResults.innerHTML = errorPanel(
        "Invalid JSON",
        "The project JSON could not be parsed."
      );
      return;
    }
    runEstimateInto(els.exampleResults, payload);
  });

  els.formatJson.addEventListener("click", () => {
    try {
      setInput(JSON.parse(els.projectJson.value));
    } catch (error) {
      els.exampleResults.innerHTML = errorPanel(
        "Invalid JSON",
        "The project JSON could not be parsed."
      );
    }
  });
}

function setInput(value) {
  els.projectJson.value = JSON.stringify(value, null, 2);
}

async function runEstimateInto(container, payload) {
  container.innerHTML = emptyState("Computing…");
  try {
    const response = await fetch("/api/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) {
      container.innerHTML = errorPanel(
        "Estimate failed",
        result.message || "The estimate could not be computed."
      );
      return;
    }
    renderResultInto(container, result, null);
  } catch (error) {
    container.innerHTML = errorPanel(
      "Request failed",
      "The local estimate server did not respond. Is abscissa-serve running?"
    );
  }
}

/* ---------- result rendering ---------- */

function emptyState(message) {
  return `<div class="results-empty">${escapeHtml(message)}</div>`;
}

function errorPanel(title, message) {
  return `
    <section class="panel error-panel">
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(message)}</p>
    </section>
  `;
}

function renderResultInto(container, result, extractionInput) {
  els.reviewStatus.textContent = sentenceCase(result.review_status);
  container.innerHTML = [
    planSection(result),
    areaSection(result),
    tileSection(result),
    reviewSection(result),
    extractionInput ? extractionSection(extractionInput) : ""
  ].join("");
}

function planSection(result) {
  const shapes = collectShapes(result);
  const badge = result.can_compute
    ? `<span class="badge ok">Computed</span>`
    : `<span class="badge review">Needs review</span>`;
  return `
    <section class="panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Plan</p>
          <h2>Geometry Preview</h2>
        </div>
        <div>
          ${badge}
          <span class="status-text">&nbsp;${shapes.length} ${shapes.length === 1 ? "shape" : "shapes"}</span>
        </div>
      </div>
      <div class="drawing-wrap">${previewSvg(shapes)}</div>
    </section>
  `;
}

function areaSection(result) {
  const facts = [
    fact("Rectangles", result.rooms.length),
    fact("Polygons", result.polygons.length),
    fact("Net area", result.total_floor_area_sqm === null ? "--" : `${fmt(result.total_floor_area_sqm)} sqm`)
  ].join("");

  const roomRows = result.rooms.map((room) => `
    <tr>
      <td>${escapeHtml(room.name)}</td>
      <td><span class="op ${room.operation}">${room.operation}</span></td>
      <td><code>${escapeHtml(room.calculation)}</code></td>
      <td>${fmt(room.signed_area_sqm)} sqm</td>
    </tr>
  `);

  const polygonRows = result.polygons.map((zone) => `
    <tr>
      <td>${escapeHtml(zone.name)}</td>
      <td><span class="op ${zone.operation}">${zone.operation}</span></td>
      <td><code>${escapeHtml(zone.calculation)}</code></td>
      <td>${zone.signed_area_sqm === null ? "--" : `${fmt(zone.signed_area_sqm)} sqm`}</td>
    </tr>
  `);

  const rows = [...roomRows, ...polygonRows].join("")
    || `<tr><td colspan="4">No computed area rows.</td></tr>`;

  const solutions = [
    ...result.rooms.map(renderRectangleSolution),
    ...result.polygons.map((zone) => {
      const draft = result.extracted_polygons.find((item) => item.name === zone.name);
      return renderPolygonSolution(zone, draft);
    })
  ].join("");

  return `
    <section class="panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Area</p>
          <h2>Area Solver</h2>
        </div>
        <strong>${result.total_floor_area_sqm === null ? "-- sqm" : `${fmt(result.total_floor_area_sqm)} sqm`}</strong>
      </div>
      <div class="facts-row">${facts}</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Zone</th><th>Operation</th><th>Formula</th><th>Net area</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="solution-list">${solutions}</div>
    </section>
  `;
}

function renderRectangleSolution(room) {
  const signed = room.operation === "subtract" ? `-${fmt(room.area_sqm)}` : fmt(room.area_sqm);
  return `
    <article class="solution-block">
      <h3>${escapeHtml(room.name)}</h3>
      <p><code>${room.operation} area = ${fmt(room.length_m)}m x ${fmt(room.width_m)}m = ${signed} sqm</code></p>
      ${room.source_text ? `<p class="muted">Source: ${escapeHtml(room.source_text)}</p>` : ""}
    </article>
  `;
}

function renderPolygonSolution(zone, draft) {
  if (!draft || !draft.points || draft.points.length < 3) {
    return `
      <article class="solution-block">
        <h3>${escapeHtml(zone.name)}</h3>
        <p><code>${escapeHtml(zone.calculation)}</code></p>
      </article>
    `;
  }

  const solution = shoelace(draft.points);
  const signedArea = zone.operation === "subtract" ? -solution.area : solution.area;
  const edgeRows = (draft.edge_labels || []).map((label) => {
    const measured = edgeLength(draft.points, label.edge_index);
    const delta = measured === null ? "--" : fmt(Math.abs(measured - label.length_m));
    return `
      <tr>
        <td>${label.edge_index}</td>
        <td>${measured === null ? "--" : `${fmt(measured)} m`}</td>
        <td>${fmt(label.length_m)} m</td>
        <td>${delta}</td>
      </tr>
    `;
  }).join("");

  return `
    <article class="solution-block">
      <h3>${escapeHtml(zone.name)}</h3>
      <p><code>abs(${fmt(solution.forwardSum)} - ${fmt(solution.backwardSum)}) / 2 = ${fmt(solution.area)} sqm</code></p>
      <p><code>${zone.operation} signed area = ${fmt(signedArea)} sqm</code></p>
      <div class="table-wrap compact">
        <table>
          <thead>
            <tr><th>Edge</th><th>Vertex length</th><th>Label</th><th>Delta</th></tr>
          </thead>
          <tbody>${edgeRows || `<tr><td colspan="4">No edge labels recorded.</td></tr>`}</tbody>
        </table>
      </div>
    </article>
  `;
}

function tileSection(result) {
  const facts = [
    fact("Tile size", `${fmt(result.tile_spec.length_mm)}mm x ${fmt(result.tile_spec.width_mm)}mm`),
    fact("Tile area", `${fmt(result.tile_area_sqm)} sqm`),
    fact("Waste", `${fmt(result.waste_percent)}%`)
  ].join("");

  let steps;
  if (!result.can_compute) {
    steps = `<p class="muted">Tile count is held until the floor area passes validation.</p>`;
  } else {
    const multiplier = 1 + result.waste_percent / 100;
    steps = `
      <div class="step-line">
        <span>Base tiles</span>
        <code>ceil(${fmt(result.total_floor_area_sqm)} / ${fmt(result.tile_area_sqm)}) = ${result.base_tile_count}</code>
      </div>
      <div class="step-line">
        <span>Order tiles</span>
        <code>ceil(${result.base_tile_count} x ${fmt(multiplier)}) = ${result.order_tile_count}</code>
      </div>
    `;
  }

  return `
    <section class="panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Tiles</p>
          <h2>Tile Solver</h2>
        </div>
        <strong>${result.order_tile_count === null ? "-- pcs" : `${result.order_tile_count} pcs`}</strong>
      </div>
      <div class="facts-row">${facts}</div>
      <div class="tile-steps">${steps}</div>
    </section>
  `;
}

function reviewSection(result) {
  const warnings = (result.warnings.length ? result.warnings : ["No warnings recorded."])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const assumptions = (result.assumptions.length ? result.assumptions : ["No assumptions recorded."])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  return `
    <section class="panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Review</p>
          <h2>Warnings and Assumptions</h2>
        </div>
        <span class="status-text">${result.can_compute ? "Computed" : "Needs review"}</span>
      </div>
      <div class="review-grid">
        <div>
          <h3>Warnings</h3>
          <ul>${warnings}</ul>
        </div>
        <div>
          <h3>Assumptions</h3>
          <ul>${assumptions}</ul>
        </div>
      </div>
    </section>
  `;
}

function extractionSection(extractionInput) {
  return `
    <section class="panel">
      <details class="json-details">
        <summary>Extracted geometry JSON</summary>
        <pre>${escapeHtml(JSON.stringify(extractionInput, null, 2))}</pre>
      </details>
    </section>
  `;
}

/* ---------- plan drawing ---------- */

function previewSvg(shapes) {
  if (!shapes.length) {
    return `<div class="empty-preview">No geometry</div>`;
  }

  const bounds = shapeBounds(shapes);
  // SVG space: x unchanged, y flipped so north is up like a floor plan.
  const sb = {
    minX: bounds.minX,
    maxX: bounds.maxX,
    minY: -bounds.maxY,
    maxY: -bounds.minY
  };
  const width = Math.max(sb.maxX - sb.minX, 1);
  const height = Math.max(sb.maxY - sb.minY, 1);
  const U = Math.max(width, height) * 0.045;

  const specs = collectDimSpecs(shapes, U);
  const laneCounts = assignDimLanes(specs, U);

  const BASE = U * 1.8;
  const SPACING = U * 2.0;
  const sideExtent = (side) =>
    laneCounts[side] ? BASE + (laneCounts[side] - 1) * SPACING + U * 1.6 : 0;

  const marginTop = U * 1.6 + sideExtent("top");
  const marginBottom = U * 1.6 + sideExtent("bottom");
  const marginLeft = U * 1.6 + sideExtent("left");
  const marginRight = U * 1.6 + sideExtent("right");
  const viewBox = [
    f(sb.minX - marginLeft),
    f(sb.minY - marginTop),
    f(width + marginLeft + marginRight),
    f(height + marginTop + marginBottom)
  ].join(" ");

  const paths = shapes.map((shape) => {
    const d = shape.points
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${-point.y}`)
      .join(" ");
    return `<path class="${shape.operation}" d="${d} Z"></path>`;
  }).join("");

  const placedLabels = [];
  const shapeLabels = shapes.map((shape) => {
    const center = centroid(shape.points);
    let x = center.x;
    let y = -center.y;
    // Nudge downward until clear of previously placed shape names.
    while (placedLabels.some((p) => Math.abs(p.x - x) < U * 6 && Math.abs(p.y - y) < U * 1.4)) {
      y += U * 1.5;
    }
    placedLabels.push({ x, y });
    return `<text x="${f(x)}" y="${f(y)}" text-anchor="middle"
      style="font-size:${f(U * 0.95)}px">${escapeHtml(shape.name)}</text>`;
  }).join("");

  const dims = specs.map((spec) => renderDimSpec(spec, sb, U, BASE, SPACING)).join("");

  return `
    <svg viewBox="${viewBox}" role="img" aria-label="Floor geometry preview">
      ${paths}
      ${shapeLabels}
      ${dims}
    </svg>
  `;
}

function collectShapes(result) {
  const shapes = [];
  (result.extracted_polygons || []).forEach((polygon) => {
    shapes.push({
      name: polygon.name,
      operation: polygon.operation,
      points: polygon.points.map((point) => ({ x: point.x_m, y: point.y_m })),
      edgeLabels: polygon.edge_labels || []
    });
  });

  let cursor = 0;
  (result.extracted_rectangles || []).forEach((rectangle) => {
    const gap = 1;
    shapes.push({
      name: rectangle.name,
      operation: rectangle.operation,
      points: [
        { x: cursor, y: 0 },
        { x: cursor + rectangle.length_m, y: 0 },
        { x: cursor + rectangle.length_m, y: rectangle.width_m },
        { x: cursor, y: rectangle.width_m }
      ],
      edgeLabels: [
        { edge_index: 0, length_m: rectangle.length_m, source_text: `${rectangle.length_m} m` },
        { edge_index: 1, length_m: rectangle.width_m, source_text: `${rectangle.width_m} m` }
      ]
    });
    cursor += rectangle.length_m + gap;
  });
  return shapes;
}

function shoelace(points) {
  let forwardSum = 0;
  let backwardSum = 0;
  points.forEach((point, index) => {
    const next = points[(index + 1) % points.length];
    forwardSum += point.x_m * next.y_m;
    backwardSum += point.y_m * next.x_m;
  });
  return {
    forwardSum,
    backwardSum,
    area: Math.abs(forwardSum - backwardSum) / 2
  };
}

function edgeLength(points, edgeIndex) {
  if (edgeIndex < 0 || edgeIndex >= points.length) {
    return null;
  }
  const start = points[edgeIndex];
  const end = points[(edgeIndex + 1) % points.length];
  return Math.hypot(end.x_m - start.x_m, end.y_m - start.y_m);
}

function f(n) {
  return Math.round(n * 10000) / 10000;
}

function collectDimSpecs(shapes, U) {
  const specs = [];
  shapes.forEach((shape) => {
    const pts = shape.points.map((point) => ({ x: point.x, y: -point.y }));
    const n = pts.length;
    const cx = pts.reduce((sum, p) => sum + p.x, 0) / n;
    const cy = pts.reduce((sum, p) => sum + p.y, 0) / n;

    (shape.edgeLabels || []).forEach((label) => {
      const i = label.edge_index;
      if (i < 0 || i >= n) return;
      const a = pts[i];
      const b = pts[(i + 1) % n];
      const dx = b.x - a.x, dy = b.y - a.y;
      const len = Math.hypot(dx, dy);
      if (len < 1e-9) return;

      // Outward normal: away from the shape centroid.
      let nx = -dy / len, ny = dx / len;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      if ((mx - cx) * nx + (my - cy) * ny < 0) {
        nx = -nx;
        ny = -ny;
      }

      const text = label.source_text || `${label.length_m} m`;
      const horizontal = Math.abs(dy) <= len * 1e-6;
      const vertical = Math.abs(dx) <= len * 1e-6;
      let side = "free";
      if (horizontal) side = ny < 0 ? "top" : "bottom";
      else if (vertical) side = nx < 0 ? "left" : "right";

      // Occupied interval along the side axis, widened to cover the label text.
      let s0 = 0, s1 = 0;
      if (side === "top" || side === "bottom") {
        s0 = Math.min(a.x, b.x);
        s1 = Math.max(a.x, b.x);
      } else if (side === "left" || side === "right") {
        s0 = Math.min(a.y, b.y);
        s1 = Math.max(a.y, b.y);
      }
      const mid = side === "left" || side === "right" ? my : mx;
      const textHalf = text.length * U * 0.34;
      if (side !== "free") {
        s0 = Math.min(s0, mid - textHalf);
        s1 = Math.max(s1, mid + textHalf);
      }

      specs.push({ a, b, nx, ny, side, s0, s1, text, lane: 0 });
    });
  });
  return specs;
}

function assignDimLanes(specs, U) {
  const counts = { top: 0, bottom: 0, left: 0, right: 0 };
  const pad = U * 0.6;

  ["top", "bottom", "left", "right"].forEach((side) => {
    const sideSpecs = specs
      .filter((spec) => spec.side === side)
      .sort((s1, s2) => s1.s0 - s2.s0 || s1.s1 - s2.s1);
    const lanes = [];
    sideSpecs.forEach((spec) => {
      let lane = lanes.findIndex(
        (intervals) => intervals.every(([i0, i1]) => spec.s1 + pad <= i0 || spec.s0 - pad >= i1)
      );
      if (lane === -1) {
        lane = lanes.length;
        lanes.push([]);
      }
      lanes[lane].push([spec.s0, spec.s1]);
      spec.lane = lane;
    });
    counts[side] = lanes.length;
  });
  return counts;
}

function renderDimSpec(spec, sb, U, BASE, SPACING) {
  const tick = U * 0.42;
  const overrun = U * 0.45;
  const gap = U * 0.25;
  const offset = BASE + spec.lane * SPACING;
  const { a, b, side, text } = spec;

  let dl1, dl2, ext, textPos, rotate;
  if (side === "top" || side === "bottom") {
    const lineY = side === "top" ? sb.minY - offset : sb.maxY + offset;
    const dir = side === "top" ? -1 : 1;
    dl1 = { x: a.x, y: lineY };
    dl2 = { x: b.x, y: lineY };
    ext = [
      { x1: a.x, y1: a.y + dir * gap, x2: a.x, y2: lineY + dir * overrun },
      { x1: b.x, y1: b.y + dir * gap, x2: b.x, y2: lineY + dir * overrun }
    ];
    textPos = { x: (a.x + b.x) / 2, y: lineY - U * 0.55 };
    rotate = 0;
  } else if (side === "left" || side === "right") {
    const lineX = side === "left" ? sb.minX - offset : sb.maxX + offset;
    const dir = side === "left" ? -1 : 1;
    dl1 = { x: lineX, y: a.y };
    dl2 = { x: lineX, y: b.y };
    ext = [
      { x1: a.x + dir * gap, y1: a.y, x2: lineX + dir * overrun, y2: a.y },
      { x1: b.x + dir * gap, y1: b.y, x2: lineX + dir * overrun, y2: b.y }
    ];
    textPos = { x: lineX + dir * U * 0.55, y: (a.y + b.y) / 2 };
    rotate = -90;
  } else {
    // Non-axis-aligned edge: offset along its own outward normal.
    const { nx, ny } = spec;
    dl1 = { x: a.x + nx * BASE, y: a.y + ny * BASE };
    dl2 = { x: b.x + nx * BASE, y: b.y + ny * BASE };
    ext = [
      { x1: a.x + nx * gap, y1: a.y + ny * gap, x2: dl1.x + nx * overrun, y2: dl1.y + ny * overrun },
      { x1: b.x + nx * gap, y1: b.y + ny * gap, x2: dl2.x + nx * overrun, y2: dl2.y + ny * overrun }
    ];
    textPos = {
      x: (dl1.x + dl2.x) / 2 + nx * U * 0.55,
      y: (dl1.y + dl2.y) / 2 + ny * U * 0.55
    };
    rotate = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
    if (rotate > 90 || rotate < -90) rotate += 180;
  }

  // Oblique 45-degree tick slashes at both ends (architecture convention).
  const tickLines = [dl1, dl2].map((p) => `
    <line class="dim-tick" x1="${f(p.x - tick)}" y1="${f(p.y + tick)}" x2="${f(p.x + tick)}" y2="${f(p.y - tick)}"/>
  `).join("");

  return `
    ${ext.map((e) => `<line class="dim-ext" x1="${f(e.x1)}" y1="${f(e.y1)}" x2="${f(e.x2)}" y2="${f(e.y2)}"/>`).join("")}
    <line class="dim-line" x1="${f(dl1.x)}" y1="${f(dl1.y)}" x2="${f(dl2.x)}" y2="${f(dl2.y)}"/>
    ${tickLines}
    <text class="dim-text" x="${f(textPos.x)}" y="${f(textPos.y)}"
      text-anchor="middle" dominant-baseline="middle" style="font-size:${f(U * 0.95)}px"
      ${rotate ? `transform="rotate(${f(rotate)},${f(textPos.x)},${f(textPos.y)})"` : ""}
    >${escapeHtml(text)}</text>
  `;
}

function shapeBounds(shapes) {
  const allPoints = shapes.flatMap((shape) => shape.points);
  return {
    minX: Math.min(...allPoints.map((point) => point.x)),
    maxX: Math.max(...allPoints.map((point) => point.x)),
    minY: Math.min(...allPoints.map((point) => point.y)),
    maxY: Math.max(...allPoints.map((point) => point.y))
  };
}

function centroid(points) {
  return {
    x: points.reduce((total, point) => total + point.x, 0) / points.length,
    y: points.reduce((total, point) => total + point.y, 0) / points.length
  };
}

/* ---------- small helpers ---------- */

function fact(label, value) {
  return `
    <div class="fact">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </div>
  `;
}

function sentenceCase(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/^\w/, (letter) => letter.toUpperCase());
}

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 4
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
