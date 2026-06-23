# Stage 01 — Design

Scope the axis agent: what data it reads, what signal it returns, how to prompt it.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Conversation | (axis name from user) | Full | Which agent we're building |
| Identity | `../../_config/identity.md` | Agent fleet section | Existing agents + corroboration rule |
| Signal shape | `../../shared/signal-shape.md` | Full | What the JSON output must look like |

## Process

1. Confirm which axis to build (customers, comms, meetings, or ops).
2. List the data sources this axis needs — which `backend/integrations/` adapters are relevant.
3. Draft the agent's system prompt: role, input format, decision criteria, output schema.
4. Define the signal this agent returns — must match `shared/signal-shape.md`.
5. Identify what the adapter must supply: which fields, at what granularity.
6. Write the design doc to output/.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Design doc | `output/[axis]-design.md` | System prompt draft, data sources, signal shape, adapter requirements |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|------------|---------------|---------------|
| Step 3 | System prompt draft | Approve or refine before implementation begins |

## Audit

| Check | Pass Condition |
|-------|---------------|
| Signal shape valid | Output schema matches `shared/signal-shape.md` exactly |
| Data sources named | Each required adapter listed with specific fields needed |
| Prompt is verifiable | Decision criteria are concrete and testable, not vague |
