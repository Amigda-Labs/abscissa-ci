---
name: tile-area-computation
description: Computes floor area from rectangular or polygon construction floor-plan parts. Use when a task needs area from rectangles, decomposed L/T/plus shapes, voids, or rectilinear polygons described by metric vertex coordinates.
compatibility: Requires Python 3.12+.
---

# Tile Area Computation

Use this skill after floor-plan dimensions have been extracted into rectangles
or vertex-coordinate polygons.

This skill does not read images. It computes area from structured geometry data.

## Polygon Rules (preferred)

- Describe each included floor area as an `add` polygon with `points` listed in
  order around the boundary, in meters, without repeating the first point.
- Edge `i` connects point `i` to point `i + 1`; the last edge closes the ring.
- Attach every printed dimension as an `edge_labels` entry
  (`edge_index`, `length_m`, `source_text`). Labels are cross-checked against
  the vertex coordinates and mismatches block computation.
- Describe interior voids as `subtract` polygons contained inside an `add`
  polygon. Included polygons must not overlap each other.

## Rectangle Rules (fallback)

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

Polygon input format:

```json
{
  "polygons": [
    {
      "name": "L Shape Footprint",
      "operation": "add",
      "points": [
        {"x_m": 0, "y_m": 0},
        {"x_m": 12, "y_m": 0},
        {"x_m": 12, "y_m": 5},
        {"x_m": 7, "y_m": 5},
        {"x_m": 7, "y_m": 9},
        {"x_m": 0, "y_m": 9}
      ],
      "edge_labels": [
        {"edge_index": 0, "length_m": 12, "source_text": "12.00 m"},
        {"edge_index": 4, "length_m": 7, "source_text": "7.00 m"}
      ]
    }
  ]
}
```

Rectangle input format:

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
  "polygon_zones": [],
  "total_floor_area_sqm": 60,
  "warnings": []
}
```

Use the JSON output as the input to the `tile-counting` skill.
