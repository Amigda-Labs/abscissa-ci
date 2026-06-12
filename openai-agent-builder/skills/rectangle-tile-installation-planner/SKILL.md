---
name: rectangle-tile-installation-planner
description: Compute rectangular tile floor area, estimate 600mm x 600mm tile quantity, collect labor or timeline inputs, draft a labor schedule, and produce a materials/tools/labor plan for human review.
---

# Rectangle Tile Installation Planner

Use this skill when the user provides a floor plan or dimensions for a
rectangular tile area and wants a practical tile installation plan.

This skill assumes the floor area is a rectangle unless the user states
otherwise. If the floor plan is unclear or does not show both length and width,
ask for the missing dimension before computing quantities.

## Required Workflow

Follow the references in order:

1. `references/01-compute-area.md`
2. `references/02-compute-tiles-required.md`
3. `references/03-labor-or-timeline-gate.md`
4. `references/04-create-schedule.md`
5. `references/05-materials-and-tools.md`
6. `references/06-final-plan.md`

Do not skip step 3. After area and tile quantity are computed, stop and ask the
user whether they have the number of laborers or an ideal timeline before
creating the schedule.

## Core Rules

- Treat every output as a draft for contractor or qualified installer review.
- Separate extracted facts from assumptions.
- Do not invent floor-plan dimensions. Ask for missing length or width.
- Use metric units unless the user explicitly provides another unit.
- Label default labor productivity as an assumption.
- Do not imply code compliance, engineering approval, or final installation
  approval.
- Keep the final plan contractor-friendly and practical.

## Default Calculation Assumptions

- Tile size: `600mm x 600mm`
- Tile area: `0.36 sqm`
- Waste allowance: `10%`
- Workday: `8 hours/day`
- Default tilesetter productivity: `2.0 sqm/hour/person`

The productivity default is only a planning assumption for setting floor tile
after the substrate is ready. It excludes major substrate repair, demolition,
waterproofing, curing delays, long material handling, complex cuts, and rework.

## Output Requirement

The final answer must include:

- Confirmed inputs.
- Assumptions.
- Area calculation.
- Tile quantity calculation.
- Labor/timeline basis.
- Draft installation schedule.
- Materials list.
- Tools list.
- Missing inputs and review items.
- Draft status.
