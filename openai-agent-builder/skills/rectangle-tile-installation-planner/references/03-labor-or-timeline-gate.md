# Step 3: Labor Or Timeline Gate

## Goal

Stop after tile counting and collect the planning basis before creating a
schedule.

## Required Stop

After steps 1 and 2, ask the user:

```text
Before I make the schedule, do you already know the number of laborers, or do
you have an ideal timeline?
```

Do not create a schedule until one of these is known:

- Number of laborers.
- Ideal timeline.

## If The User Gives Laborers

Ask whether they know the tilesetter productivity:

```text
Do you know how fast each tilesetter can install tile in sqm/hour? If not, I
can use the planning default of 2.0 sqm/hour/person.
```

If the user does not know, use:

```text
default_productivity_sqm_per_hour_per_person = 2.0
```

Label this as an assumption.

## If The User Gives Ideal Timeline

Ask for work hours per day only if the timeline cannot be converted into labor
hours. If not provided, use:

```text
workday_hours = 8
```

Use the default productivity unless the user gives a known productivity rate.

## Planning Formulas

If laborers are given:

```text
total_labor_hours = area_sqm / productivity_sqm_per_hour_per_person
duration_hours = total_labor_hours / laborer_count
duration_workdays = duration_hours / workday_hours
```

If ideal timeline is given:

```text
available_hours_per_laborer = target_workdays * workday_hours
total_labor_hours = area_sqm / productivity_sqm_per_hour_per_person
required_laborers = ceil(total_labor_hours / available_hours_per_laborer)
```

## Output Shape

```json
{
  "step": "labor_or_timeline_gate",
  "planning_basis": "laborers_given",
  "laborer_count": 2,
  "target_workdays": null,
  "workday_hours": 8,
  "productivity_sqm_per_hour_per_person": 2.0,
  "productivity_source": "default assumption",
  "area_sqm": 50,
  "total_labor_hours": 25,
  "estimated_duration_hours": 12.5,
  "estimated_duration_workdays": 1.5625,
  "required_laborers": null,
  "assumptions": [
    "Productivity is assumed at 2.0 sqm/hour/person.",
    "Workday is assumed at 8 hours/day."
  ]
}
```

Keep the result draft-only because real productivity depends on substrate
condition, layout complexity, cuts, tile type, crew skill, material handling,
and site constraints.
