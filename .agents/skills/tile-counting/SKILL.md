---
name: tile-counting
description: Counts needed metric floor tiles from total floor area. Use after area computation when estimating 600mm x 600mm tile quantity with a waste allowance.
compatibility: Requires Python 3.12+.
---

# Tile Counting

Use this skill after total floor area is known.

This skill does not read images and does not compute geometry. It converts floor area into a tile quantity.

## Default Rules

- Tile size defaults to `600mm x 600mm`.
- Tile area is `0.36 sqm`.
- Waste allowance defaults to `10%`.
- Base tile count is rounded up.
- Order tile count with waste is rounded up.

## Script

Run from the skill root with a JSON area result:

```bash
python3 scripts/count_tiles.py area_result.json
```

Or pass area directly:

```bash
python3 scripts/count_tiles.py --area-sqm 88
```

Optional parameters:

```bash
python3 scripts/count_tiles.py --area-sqm 88 --tile-length-mm 600 --tile-width-mm 600 --waste-percent 10
```

Output format:

```json
{
  "can_compute": true,
  "total_floor_area_sqm": 88,
  "tile_area_sqm": 0.36,
  "base_tile_count": 245,
  "order_tile_count": 270,
  "waste_percent": 10
}
```
