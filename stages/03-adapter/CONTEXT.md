# Stage 03 — Adapter

Write or update the Python integration adapter that supplies data to this agent.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Design doc | `../01-design/output/[axis]-design.md` | Adapter requirements section | Which fields the agent needs |
| Build summary | `../02-build/output/[axis]-build-summary.md` | Full | Confirms which adapter(s) to update |
| Existing adapters | `../../backend/integrations/` | Relevant adapter file | Starting point or reference |
| Adapter contract | `references/adapter-contract.md` | Full | What every adapter must implement |

## Process

1. Read the design doc's adapter requirements: which provider, which fields, what granularity.
2. Check `backend/integrations/` — does a suitable adapter already exist?
   - If yes: extend it with the new fields this agent needs.
   - If no: write a new adapter following the contract in `references/adapter-contract.md`.
3. Update `managed_agents.py` to call the adapter when building context for this agent.
4. Seed data: if the adapter has no live data yet, add sample data so the agent runs in dev.
5. Write a diff summary to output/.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Diff summary | `output/[axis]-adapter-diff.md` | What changed in backend/integrations/, any new env vars |

## Audit

| Check | Pass Condition |
|-------|---------------|
| Contract implemented | Adapter implements all required methods from `references/adapter-contract.md` |
| Seed data present | Agent can run without live credentials (dev/demo mode) |
| No secrets in code | API keys read from env vars only |
| Fields match design | Adapter output provides every field the design doc requires |
