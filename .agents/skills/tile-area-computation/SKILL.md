---
name: tile-area-computation
description: Computes floor area from rectangular construction floor-plan parts. Use when a task needs area from one rectangle, an L/T/plus shape decomposed into rectangles, or a void/exclusion that should be subtracted.
compatibility: Requires Python 3.12+.
---

# Tile Area Computation

Use this skill after floor-plan dimensions have been extracted into rectangles.

This skill does not read images. It computes area from structured rectangle data.

## Rectangle Rules

- Represent each included floor region as an `add` rectangle.
- Represent voids, openings, or excluded floor regions as a `subtract` rectangle.
- L-shaped, T-shaped, and plus-shaped footprints must be decomposed into non-overlapping `add` rectangles.
- Do not invent missing dimensions. Return warnings when the input is incomplete.

## Script

Run the bundled script from the skill root:

```bash
python3 scripts/compute_area.py input.json
```

Or pass JSON directly:

```bash
python3 scripts/compute_area.py --json '{"rectangles":[{"name":"Main","length_m":12,"width_m":5,"operation":"add"}]}'
```

Write output to a file:

```bash
python3 scripts/compute_area.py input.json --output area_result.json
```

Input format:

```json
{
  "rectangles": [
    {
      "name": "Main Rectangle",
      "length_m": 12,
      "width_m": 5,
      "operation": "add",
      "source_text": "12.00 m x 5.00 m"
    }
  ]
}
```

Output format:

```json
{
  "can_compute": true,
  "rooms": [],
  "total_floor_area_sqm": 60,
  "warnings": []
}
```

Use the JSON output as the input to the `tile-counting` skill.
