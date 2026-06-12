# Step 2: Compute Tiles Required

## Goal

Convert total floor area into the number of tiles to order.

## Required Input

- `area_sqm` from step 1.

## Defaults

- Tile length: `600mm`.
- Tile width: `600mm`.
- Tile area: `0.36 sqm`.
- Waste allowance: `10%`.

If the user gives a different tile size or waste allowance, use the user's
values and show the calculation.

## Formulas

```text
tile_area_sqm = (tile_length_mm / 1000) * (tile_width_mm / 1000)
base_tile_count = ceil(area_sqm / tile_area_sqm)
order_tile_count = ceil(base_tile_count * (1 + waste_percent / 100))
```

## Output Shape

```json
{
  "step": "compute_tiles_required",
  "can_compute": true,
  "area_sqm": 50,
  "tile_length_mm": 600,
  "tile_width_mm": 600,
  "tile_area_sqm": 0.36,
  "base_tile_count": 139,
  "waste_percent": 10,
  "order_tile_count": 153,
  "calculation": "ceil(50 / 0.36) = 139; ceil(139 * 1.10) = 153",
  "assumptions": [
    "Tile size is assumed to be 600mm x 600mm.",
    "Waste allowance is assumed to be 10%."
  ],
  "warnings": []
}
```

Do not proceed directly to scheduling after this step. Continue to step 3 and
ask the required labor or timeline question.
