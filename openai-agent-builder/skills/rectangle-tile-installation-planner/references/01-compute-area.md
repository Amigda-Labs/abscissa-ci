# Step 1: Compute Area

## Goal

Compute the floor area from a rectangular floor plan.

## Inputs Needed

- Length.
- Width.
- Unit of measurement.
- Source reference from the floor plan or user message.

## Rules

- Assume one rectangle only.
- Do not invent missing length or width.
- If the image, drawing, or message does not clearly show both dimensions, ask:
  `What are the length and width of the rectangular tile area?`
- Convert to meters before computing area.
- Preserve the source reference, such as a dimension label or user-provided
  measurement.

## Formula

```text
area_sqm = length_m * width_m
```

## Output Shape

```json
{
  "step": "compute_area",
  "can_compute": true,
  "confirmed_facts": [
    {
      "name": "Length",
      "value": 10,
      "unit": "m",
      "source": "floor plan label"
    },
    {
      "name": "Width",
      "value": 5,
      "unit": "m",
      "source": "floor plan label"
    }
  ],
  "assumptions": [
    "The floor area is treated as one rectangle."
  ],
  "area_sqm": 50,
  "calculation": "10m * 5m = 50 sqm",
  "warnings": []
}
```

If the area cannot be computed, return `can_compute: false` and ask only for
the missing dimensions.
