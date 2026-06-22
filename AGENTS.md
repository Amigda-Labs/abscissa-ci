# Abscissa CI Agent Instructions

## Current Scope

This repository is being rebuilt from scratch around construction intelligence
for floor plans. The first working agent is the Area Agent.

The Area Agent determines draft room areas from architectural plan images. It
must keep extracted drawing facts separate from assumptions and must not present
area results as final construction quantities without human review.

## Area Agent Rules

- Prefer net internal room area by default: measure to the inside face of walls.
- Treat wall thickness carefully. Do not count thick wall area as room area
  unless the requested basis is gross area.
- Dissect irregular rooms into traceable components such as rectangles and
  subtractions.
- Subtract true negative spaces such as shafts, voids, courtyards, stairs, and
  excluded openings when they fall inside an included room or floor area.
- Do not subtract outside missing corners if the room was already decomposed
  into included shapes.
- Do not invent missing scales, dimensions, units, or room boundaries.
- Detect measurements that do not make sense, including conflicting dimensions,
  impossible segment sums, negative net areas, oversized subtractions,
  ambiguous units, and area labels that disagree with computed dimensions.
- Ask targeted questions when the drawing cannot support a reliable area
  computation.
- Return structured data that a later layout/text agent can consume.

## Reporting

When reporting work:

- State what changed.
- List files created or modified.
- Mention tests or verification performed.
- Call out assumptions, risks, or missing inputs.
- Tell the user what to do next if there is a useful next step.
