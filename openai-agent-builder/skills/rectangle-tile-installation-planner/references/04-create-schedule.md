# Step 4: Create Schedule

## Goal

Create a draft labor schedule only after step 3 has collected either laborers
or ideal timeline.

## Required Inputs

- `area_sqm`.
- `order_tile_count`.
- Either laborer count or target timeline.
- Productivity basis.
- Workday hours.

## Schedule Rules

- Keep the schedule simple and contractor-friendly.
- Make setting-tile productivity visible.
- Do not hide curing, grout wait times, waterproofing, demolition, substrate
  correction, or client decisions if they are unknown.
- If site conditions are unknown, mark prep and review items as assumptions.
- Use workdays rather than exact dates unless the user gives a start date.

## Default Work Breakdown

Use these phases unless the user gives a different scope:

1. Site check and layout confirmation.
2. Substrate cleaning and minor prep.
3. Tile layout and setting.
4. Grouting and cleanup.
5. Final inspection and punch list.

## Draft Schedule Format

```markdown
### Draft Labor Schedule

| Phase | Estimated Duration | Labor | Notes |
| --- | ---: | --- | --- |
| Site check and layout confirmation | 0.25 day | 1 lead installer | Verify dimensions, tile layout, substrate, and transitions. |
| Substrate cleaning and minor prep | 0.50 day | Crew | Assumes no major leveling, repairs, or demolition. |
| Tile layout and setting | 1.56 days | 2 tilesetters | Based on 50 sqm at 2.0 sqm/hour/person and 8 hours/day. |
| Grouting and cleanup | 0.50 day | Crew | Product wait times must be verified. |
| Final inspection and punch list | 0.25 day | 1 lead installer | Review alignment, grout, lippage, movement joints, and cleanup. |
```

## Review Notes

Always include that the schedule is a draft and must be checked against:

- Actual substrate condition.
- Mortar/grout manufacturer wait times.
- Tile type and cut complexity.
- Site access and material staging.
- Wet-area, exterior, or movement-joint requirements.
