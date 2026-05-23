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
from rectangular floor-plan dimensions.

For L-shaped, T-shaped, plus-shaped, or voided footprints, the first checkpoint
uses rectangle decomposition:

- included floor areas are `add` rectangles
- voids or exclusions are `subtract` rectangles
- the final floor area is the sum of signed rectangle areas

Coordinate-based polygons are a better later representation for layout and edge
cuts, but rectangle decomposition is simpler and easier to review for the first
area and tile-count checkpoint.

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

The default extraction model is `gpt-5.2` with high-detail image input. Override
it with `ABSCISSA_MODEL` only when you want a cheaper or experimental evaluation
run.

Run deterministic calculations from JSON:

```bash
uv run abscissa-tile estimate-json example_floor_plans/sample_rectangles.json
```

Run the image agent against one floor plan image:

```bash
uv run abscissa-tile estimate example_floor_plans/rectangular_floor_plan.png
```

For local Agent Skills evaluation with shell tools, use a model that supports
`ShellTool` and pass `--use-shell-skills`:

```bash
uv run abscissa-tile estimate --model gpt-5.2 --use-shell-skills example_floor_plans/rectangular_floor_plan.png
```

Run the image agent against every supported image in the examples folder:

```bash
uv run abscissa-tile batch example_floor_plans
```

Outputs are written beside the source input as:

- `*.tile_estimate.json`
- `*.tile_estimate.md`

The image-extraction output is draft-only and must be evaluated by a human
reviewer.

## Agent Skills

Agent Skills-compatible bundles live in `.agents/skills/`.

- `tile-area-computation` computes total floor area from add/subtract rectangles.
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
