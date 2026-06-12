# Step 6: Give The User The Plan

## Goal

Return a contractor-friendly draft plan that combines quantities, labor,
schedule, materials, tools, assumptions, and review items.

## Required Format

```markdown
## Tile Installation Plan Draft

### Confirmed Inputs
- ...

### Assumptions
- ...

### Area Calculation
- ...

### Tile Quantity
- ...

### Labor / Timeline Basis
- ...

### Draft Schedule
| Phase | Estimated Duration | Labor | Notes |
| --- | ---: | --- | --- |
| ... | ... | ... | ... |

### Materials
| Item | Status | Why Needed | Notes / Verify |
| --- | --- | --- | --- |
| ... | ... | ... | ... |

### Tools
| Tool | Status | Why Needed | Notes / Verify |
| --- | --- | --- | --- |
| ... | ... | ... | ... |

### Missing Inputs / Review Items
- ...

### Draft Status
This is a planning draft only. A qualified contractor or tilesetter must review
the floor-plan dimensions, substrate condition, product compatibility,
manufacturer wait times, movement joints, and site constraints before work
starts.
```

## Rules

- Do not call the output final.
- Do not hide missing inputs.
- Keep calculations visible.
- State whether productivity came from the user or from the default assumption.
- If the user only provided a floor plan image and the dimensions were inferred,
  say that dimensions need confirmation before procurement or work starts.
