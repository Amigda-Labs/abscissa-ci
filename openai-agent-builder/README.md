# OpenAI Agent Builder Assets

This folder contains Agent Builder-ready skill bundles for Abscissa CI.

## Skills

- `skills/rectangle-tile-installation-planner`: Computes rectangular floor area,
  counts required tiles, gathers labor/timeline inputs, drafts an installation
  schedule, lists materials/tools, and returns a contractor-friendly plan.

## Agent Instructions

- `agent-instructions/floorplan-construction-document-agent.md`: General Agent
  Builder instructions for a construction-document agent that receives a floor
  plan image, converts it to structured JSON, selects the correct skill, and
  drafts BOQ/manpower schedule outputs.

## Use Notes

- These assets are draft workflow instructions, not final contractor documents.
- Keep generated outputs human-reviewed.
- Preserve the distinction between extracted floor-plan facts and assumptions.
- Do not use this folder for broad SaaS behavior or account/workspace logic.
