# Stage 04 — Test

Run the axis agent, validate its signal, and confirm corroboration works.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Build summary | `../02-build/output/[axis]-build-summary.md` | Full | Env var name and ant command |
| Adapter diff | `../03-adapter/output/[axis]-adapter-diff.md` | Full | What adapter data to expect |
| Test checklist | `references/test-checklist.md` | Full | Standard validation steps |

## Process

1. Run the axis endpoint with seed data (agent ID not set → confirm `{"status":"not_configured"}`).
2. Create the agent via `ant`: `ant beta:agents create < backend/agents/[axis].agent.yaml --transform id -r`
3. Set `[AXIS]_AGENT_ID` in the local env.
4. Run `POST /founders/{id}/agents/[axis]/run` — confirm a valid signal is returned.
5. Check signal shape against `shared/signal-shape.md`.
6. Run `POST /founders/{id}/agents/run` (full fleet) — confirm corroboration logic handles one axis correctly (lone signal suppressed).
7. Write test results to output/.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Test results | `output/[axis]-test-results.md` | Pass/fail per checklist item, raw signal received |

## Audit

| Check | Pass Condition |
|-------|---------------|
| Safe-by-default confirmed | Returns `{"status":"not_configured"}` without agent ID |
| Signal shape valid | Response matches `shared/signal-shape.md` exactly |
| Lone-signal suppressed | Full fleet run does not surface an alert from one axis alone |
| No credential leaks | No API keys appear in logs or response bodies |
