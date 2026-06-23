# dCern — Task Routing

Build and wire axis agents one at a time.
Each agent follows the same four-stage pipeline.

## Pipeline

| Task | Go To | Description |
|------|-------|-------------|
| Design a new agent | `stages/01-design/CONTEXT.md` | Scope data sources, signal shape, prompt |
| Build the agent | `stages/02-build/CONTEXT.md` | Write .agent.yaml + managed_agents.py endpoint |
| Wire the adapter | `stages/03-adapter/CONTEXT.md` | Write or update backend/integrations/ adapter |
| Test end-to-end | `stages/04-test/CONTEXT.md` | Run agent, validate signal, check corroboration |

## One-off Tasks

| Task | Location |
|------|----------|
| One-time agent setup | `backend/agents/README.md` — `ant` CLI to create agents + set env vars on Render |
| Promote coordinator | Create coordinator agent via `ant` once all 5 axis agents are live |

## Triggers

| Keyword | Action |
|---------|--------|
| `setup` | Run `setup/questionnaire.md` onboarding |
| `status` | Show pipeline completion for the current axis |
| `build [axis]` | Begin Stage 01 for a named axis (money, customers, comms, meetings, ops) |
