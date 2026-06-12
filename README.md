# Abscissa CI

Abscissa CI means Abscissa Construction Intelligence / Coordinate Intelligence.

The name comes from coordinate geometry: the abscissa is the input axis. For
this project, the inputs are construction drawings, scope notes, specs,
measurements, assumptions, photos, and site decisions.

The initial direction is service-first, not full SaaS. Abscissa CI should begin
as a human-reviewed construction AI workflow that helps contractors turn messy
project inputs into draft estimates, BOQs, schedules, assumptions, RFIs, change
orders, proposals, and review notes.

The first implementation work should stay small, traceable, and practical for
real contractor service delivery.

## First Workflow: Tile Area + Tile Count

The first workflow estimates floor area and needed `600mm x 600mm` floor tiles
from extracted floor-plan geometry.

The preferred representation is coordinate-based polygons:

- each included floor area is an `add` polygon described by metric vertex
  coordinates listed in order around the boundary
- interior voids or exclusions are `subtract` polygons contained inside an
  included floor polygon
- each printed dimension is attached to the boundary edge it measures via
  `edge_labels`, and the deterministic validator cross-checks every label
  against the vertex-derived edge length
- areas come from the shoelace formula over each ring; validation failures
  (label mismatches, self-intersections, overlapping floor polygons,
  uncontained voids) block computation and surface as warnings for review
- the overall printed plan dimensions (`bounding_width_m`, `bounding_height_m`)
  are cross-checked against the vertex span, and every printed dimension in
  `dimension_inventory` must be attached to an edge or be an overall dimension,
  so simplified or invented shapes that ignore printed labels are rejected

The image extraction agent works in two passes, like a land survey:

- a perception pass (the survey) records every printed dimension exactly as
  printed, grouped into dimension chains lane by lane, with each chain's
  anchoring to the outline's extremes; the survey is deterministically
  validated (chain sums, entry/chain consistency, axis determinability) and
  retried with the validator's errors before any shape reasoning happens
- the chains deterministically define a station grid: the extension-line
  positions where footprint corners can exist
- when the grid is determined on both axes, the assembly pass only classifies
  each grid cell as floor or not - stated twice (cell list and boolean
  matrix), which must agree - and the polygon, voids included, is traced
  deterministically from the cell union; the model never outputs coordinates
- when the grid is not determined (under-dimensioned drawings), assembly
  falls back to a closed surveyor's traverse: compass moves (`E`/`N`/`W`/`S`)
  whose lengths must cite a surveyed label or state their chain arithmetic,
  with per-axis closure checked first (east totals must equal west totals)
- derived shapes are validated against the printed evidence: bounding span,
  edge-label lengths, dimension coverage, station alignment, and station
  usage (every interior station must host a corner); the validator's error
  list is fed back to the model for up to 3 attempts, and one full re-survey
  round runs if assembly keeps failing
- extraction-time validation errors travel with the draft as
  `validation_errors` and block computation downstream; a failed extraction
  shows the attempted shape next to the errors instead of a wrong number

Known limitation: a drawing whose printed dimensions admit more than one
cell-occupancy solution (for example a cross versus its row-complement) can
only be disambiguated by actually seeing the floor fill, so a vision mistake
there can still produce a plausible wrong draft. This is why every result
stays draft-only and the preview renders the extracted shape beside the
image for human review.

Rectangle decomposition remains supported as a fallback:

- included floor areas are `add` rectangles
- voids or exclusions are `subtract` rectangles
- the final floor area is the sum of signed rectangle areas

Rectangles carry no positions, so they cannot be cross-validated the way
polygons can. Prefer polygons whenever vertex placement is possible.

Install dependencies:

```bash
uv sync
```

Create local environment configuration:

```bash
cp .env.example .env
```

Then set `ABSCISSA_TILE_ENGINEER_API_KEY` in `.env`. `OPENAI_API_KEY` is only a
fallback; the tile agent prefers `ABSCISSA_TILE_ENGINEER_API_KEY` when both are
set.

The default extraction model is `gpt-5.2` with high-detail image input. It must
be a vision + reasoning model; image-generation models such as `gpt-image-2`
cannot do structured extraction. Override the default with `ABSCISSA_MODEL`
only when you want a cheaper or experimental evaluation run.

Run deterministic calculations from JSON:

```bash
uv run abscissa-tile estimate-json example_floor_plans/json/inputs/sample_l_shape_polygon.json
uv run abscissa-tile estimate-json example_floor_plans/json/inputs/sample_rectangles.json
```

Run the image agent against one floor plan image:

```bash
uv run abscissa-tile estimate example_floor_plans/training/images/rectangular_floor_plan.png
```

For local Agent Skills evaluation with shell tools, use a model that supports
`ShellTool` and pass `--use-shell-skills`:

```bash
uv run abscissa-tile estimate --model gpt-5.2 --use-shell-skills example_floor_plans/training/images/rectangular_floor_plan.png
```

Run the image agent against every supported image in the examples folder:

```bash
uv run abscissa-tile batch example_floor_plans/training/images
```

For inputs under `example_floor_plans`, outputs are organized as:

- `example_floor_plans/json/tile_estimates/*.tile_estimate.json`
- `example_floor_plans/reports/tile_estimates/*.tile_estimate.md`

For other input folders, outputs are written beside the source input as:

- `*.tile_estimate.json`
- `*.tile_estimate.md`

The image-extraction output is draft-only and must be evaluated by a human
reviewer.

## Agent Skills

Agent Skills-compatible bundles live in `.agents/skills/`.

- `tile-area-computation` computes total floor area from vertex-coordinate
  polygons (preferred) or add/subtract rectangles.
- `tile-counting` converts total floor area into a `600mm x 600mm` tile quantity.
- `tile-installation-setup` produces draft material, tool, prep, safety, and
  review checklists for tile installation setup.

Each skill has a `SKILL.md` manifest. Computational skills may also include a
standalone JSON-in/JSON-out script in `scripts/`, following the Agent Skills
convention.

The image extraction agent exposes the computational skill folders to the
OpenAI Agents SDK through a local `ShellTool` environment. The local shell
executor is restricted to the bundled tile scripts only; it rejects unrelated
shell commands.

Internal product code does not use the name `skills` anymore:

- `src/abscissa_ci/calculators/` contains deterministic math functions.
- `src/abscissa_ci/workflows/` contains workflow orchestration.
- `.agents/skills/` contains model/tool-facing Agent Skills.
