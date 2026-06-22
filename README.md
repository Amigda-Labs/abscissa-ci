# Abscissa CI

Draft construction intelligence workspace for floor-plan reasoning and
lightweight semantic drafting.

## Abscissa CAD

Abscissa CAD is a local 2D floor-plan draft board for Mac-capable browser use.
It is intentionally lightweight: a Python static/API server with a vanilla
JavaScript canvas editor.

Run the draft board:

```bash
PYTHONPATH=src .venv/bin/python -m abscissa_ci.cad.server
```

Then open `http://127.0.0.1:8765`.

The app supports:

- CAD-style command aliases: `LOT`, `LOTAREA`, `L`, `LINE`, `W`, `WALL`,
  `CONVERT`, `D`, `DOOR`, `WIN`, `WINDOW`, `ROOM`, `DIM`, `M`, `MOVE`,
  `C`, `COPY`, `E`, `ERASE`, `U`, `UNDO`, `REDO`, `SAVE`, `OPEN`, and
  `EXPORT`
- visible command echo such as `Command: LINE` when a tool is active
- rectangular lot areas with thin dashed boundaries and circular corner markers
- grid-snapped orthogonal line and wall drawing
- draft-line selection and conversion into exterior or interior walls
- endpoint snap markers and live coordinate readout
- AutoCAD-style blue window selection and green crossing selection
- CAD-style three-click dimensions: first endpoint, second endpoint, then
  dimension-line placement offset
- exterior and interior walls with 150 mm and 100 mm default thicknesses
- doors and windows attached to parent walls
- room labels, linear dimensions, selection, move/copy, erase, undo/redo
- semantic JSON save/load and SVG/PNG export

The project JSON is the source of truth. SVG and PNG are visual exports only.

## Area Agent

Draft implementation for an OpenAI Agents SDK based Area Agent.

The first workflow focuses only on determining room areas from architectural
plan images. A vision-capable model extracts structured room geometry, and the
local harness computes and validates areas deterministically.

## Design

```text
plan image
  -> Area Agent extracts room geometry, dimensions, wall basis, voids, warnings
  -> validation harness computes areas
  -> harness rejects impossible or suspicious measurements
  -> JSON report returns computed areas or targeted questions
```

The model is not trusted to be the calculator. It provides a draft takeoff; the
Python validation layer computes area and detects conflicts.

## Commands

Install/sync dependencies:

```bash
uv sync
```

Validate an extracted JSON draft without calling the API:

```bash
PYTHONPATH=src .venv/bin/python -m abscissa_ci.cli validate-json path/to/extraction.json
```

Analyze an image with the Area Agent:

```bash
PYTHONPATH=src .venv/bin/python -m abscissa_ci.cli image path/to/floor-plan.png
```

Set `OPENAI_API_KEY` or `ABSCISSA_AREA_AGENT_API_KEY` before running image
analysis. Override the model with `ABSCISSA_AREA_MODEL` or `--model`.

Generate the synthetic floor-plan fixtures:

```bash
PYTHONPATH=src .venv/bin/python tools/generate_synthetic_floorplans.py
```

Run the Area Agent against the synthetic fixtures and compare against answer
sheets:

```bash
PYTHONPATH=src .venv/bin/python -m abscissa_ci.cli eval-samples \
  --output samples/floorplans/agent_outputs/summary.json
```

Add `--force` to make fresh OpenAI API calls instead of reusing saved reports.

The current sample run is saved at
`samples/floorplans/agent_outputs/summary.json` and passed all five fixtures.

## Output

The final report includes:

- `can_compute`
- room-level area results
- total area
- detected negative spaces
- warnings and errors
- questions for the user when measurements do not make sense

All outputs are draft-only until reviewed against the original drawing.

## Synthetic Samples

The repository includes five generated metric floor plans under
`samples/floorplans`:

- compact apartment
- L-shaped family flat
- courtyard/void unit
- townhouse ground floor
- small clinic suite

Each fixture includes:

- a PNG image for model input
- an SVG source drawing
- a JSON answer sheet
- a Markdown answer sheet
- a gold extraction JSON file for deterministic harness tests

The images include room names and metric dimensions only. They do not include
room area values or total area values.
