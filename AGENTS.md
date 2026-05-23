# Abscissa CI Agent Instructions

## 1. Project Mission

Abscissa CI means Abscissa Construction Intelligence / Coordinate Intelligence.
The project exists to turn messy construction inputs into practical,
build-ready working outputs for contractors.

The first version is service-first and human-reviewed. It should help prepare
drafts such as estimates, BOQs, schedules, assumptions, RFIs, change orders,
proposals, and review notes from real project inputs.

Do not treat this project as a full SaaS platform yet. Build small,
monetizable workflows that can be used in contractor service delivery before
adding platform complexity.

## 2. Brand Meaning

In coordinate geometry, the abscissa is the input axis.

For this product, the construction inputs are drawings, scope notes, specs,
measurements, assumptions, photos, and site decisions. Abscissa CI is the input
axis for construction intelligence: where every build begins.

Future product decisions should preserve this meaning:

- Inputs come first.
- Every output must be traceable to inputs, assumptions, or human decisions.
- The system should help contractors move from unclear project information to
  contractor-ready documents.

## 3. Product Principles

- Keep the system practical for real contractors.
- Prioritize accuracy, traceability, and explicit assumptions over impressive
  AI wording.
- Always distinguish extracted facts from AI-generated assumptions.
- Never present an estimate, schedule, BOQ, RFI, change order, or proposal as
  final without human review.
- Prefer small service workflows that can generate revenue over a broad
  construction super-app.
- Avoid SaaS infrastructure until the workflow has been validated through real
  service delivery.
- Store project decisions, assumptions, and review status clearly.
- Make generated documents contractor-friendly, not academic.
- Use simple language in construction outputs.
- Keep the codebase easy for future agents to extend.

## 4. MVP Scope

The MVP should focus on narrow, useful workflows for small contractors and
renovation teams. Good first workflows include:

- Small renovation estimate drafts.
- BOQ and scope extraction from notes, drawings, specs, or photos.
- Estimate-to-schedule conversion.
- Change order / variation order preparation.
- Missing-scope and assumption checks.
- Client-ready proposal drafting.

Each workflow should produce a draft that a human can review, correct, and send
or reuse. The MVP should make service delivery faster before it tries to become
self-serve software.

## 5. Agent/Skill Architecture Guidelines

Build modularly around reusable construction workflow skills. A skill should
own a specific job, such as scope extraction, BOQ drafting, assumption checking,
schedule drafting, or proposal writing.

Prefer this structure over one large agent:

- Input processing layer: normalize uploaded or pasted project inputs.
- Project state layer: store known facts, assumptions, decisions, review notes,
  source references, and output versions.
- Skill layer: run focused construction workflows against project state.
- Review layer: make unresolved assumptions, risks, and confidence issues clear
  for human review.
- Output layer: generate contractor-friendly documents and structured data.

Future agents should:

- Keep skills narrow and reusable.
- Make assumptions inspectable.
- Preserve source references when extracting facts.
- Mark review status on generated outputs.
- Design for human-in-the-loop correction.
- Avoid hidden state that future agents cannot inspect or update.

## 6. Construction Domain Rules

- Separate extracted facts from assumptions.
- Show unknowns and missing information clearly.
- Do not invent measurements, rates, quantities, product specs, or labor
  durations without labeling them as assumptions.
- When a quantity depends on a drawing, measurement, or site condition, keep the
  source visible.
- When a rate or productivity assumption is used, record the basis if known.
- Flag scope gaps, exclusions, dependencies, and client decisions.
- Use contractor-friendly terms and plain language.
- Treat AI outputs as drafts until reviewed by a qualified human.
- Do not imply professional certification, engineering approval, code
  compliance, or legal finality unless the system has explicit reviewed input
  from the responsible professional.

## 7. Engineering Standards

- Keep the codebase simple and modular.
- Prefer boring, inspectable data structures over opaque prompt-only behavior.
- Use typed interfaces or schemas for project inputs, extracted facts,
  assumptions, outputs, and review status when the implementation begins.
- Keep workflow code separate from presentation and delivery surfaces.
- Make important transformations testable without a live UI.
- Keep prompts, templates, and construction rules versioned.
- Add dependencies only when they reduce real complexity.
- Preserve a clear path from source input to generated output.
- Do not hide construction logic inside large untested prompt strings.

## 8. What Not To Build Yet

Do not build these until the service workflow is validated:

- Full SaaS account, billing, team, or tenant infrastructure.
- Marketplace features.
- Complex dashboard analytics.
- End-to-end autonomous construction estimating without review.
- Broad all-in-one construction management features.
- Heavy CRM, ERP, accounting, or procurement integrations.
- Custom drawing/CAD viewers unless a validated workflow requires them.
- Premature agent orchestration frameworks that make simple workflows harder to
  understand.

## 9. Testing and Verification

Testing should prove that outputs are traceable, reviewable, and useful.

For future implementation work:

- Test parsers and extractors with realistic contractor inputs.
- Verify that extracted facts keep source references.
- Verify that assumptions are labeled separately from facts.
- Verify that generated outputs include review status.
- Test edge cases with missing drawings, incomplete notes, conflicting specs,
  unclear quantities, and client-side decisions.
- Use fixture projects for renovation estimates, BOQ extraction, schedule
  drafting, change orders, and proposal generation.
- Prefer deterministic tests around structured intermediate data before testing
  final prose.

No output should be considered ready for contractor use unless the review state
and unresolved assumptions are visible.

## 10. How Agents Should Report Work

When reporting work, be direct and specific:

- State what changed.
- List files created or modified.
- Mention tests or verification performed.
- Call out assumptions, risks, or missing inputs.
- State whether any generated construction output is draft-only or reviewed.
- Tell the user what to do next if there is a useful next step.

Do not oversell progress. If a workflow is only a draft, say it is a draft. If
human review is still required, say what needs review.
