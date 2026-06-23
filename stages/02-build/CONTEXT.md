# Stage 02 — Build

Write the .agent.yaml definition and the FastAPI endpoint that triggers it.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Design doc | `../01-design/output/[axis]-design.md` | Full | System prompt, signal shape, data requirements |
| Money agent reference | `../../backend/agents/money.agent.yaml` | Full | Canonical pattern for axis agents |
| Managed agents module | `../../backend/agents/managed_agents.py` | Full | Where the new endpoint goes |
| Agent patterns | `references/agent-patterns.md` | Full | dCern agent conventions |

## Process

1. Write `backend/agents/[axis].agent.yaml` from the approved system prompt in the design doc.
2. Add `POST /founders/{id}/agents/[axis]/run` to `backend/agents/managed_agents.py`:
   - Build context from the founder's data via the relevant adapter(s).
   - Call `run_managed_agent([AXIS]_AGENT_ID, context)`.
   - Parse the JSON signal from the response.
   - Ingest the finding via `ingest_finding()`.
   - Return `{"status": "not_configured"}` if the agent ID env var is not set.
3. Write the build summary to output/.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Agent YAML | Written directly to `../../backend/agents/[axis].agent.yaml` | YAML |
| Build summary | `output/[axis]-build-summary.md` | What was added, env var name needed, ant command |

## Audit

| Check | Pass Condition |
|-------|---------------|
| Safe-by-default | Endpoint returns `{"status":"not_configured"}` if agent ID env var is unset |
| Signal parsing | `run_managed_agent()` result parsed with the same logic as money agent |
| YAML model | Uses `claude-opus-4-8` (or documents if changing — see cost note in README) |
| No secrets in YAML | .agent.yaml contains no API keys or tokens |
