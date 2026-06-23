# dCern — working context

Read at the start of every session in this folder.

## What this is

dCern is an AI Chief of Staff for founders. A fleet of specialist Managed Agents
(one per business axis: money, customers, comms, meetings, ops) runs on a schedule,
each returning a structured signal. dCern's deterministic pipeline corroborates via
the ≥2-distinct rule and surfaces a 1-3-1 alert only when multiple axes agree.

## Stack

- **Backend:** Python/FastAPI (`backend/`). Managed Agents via Anthropic API (`ant` CLI).
- **Frontend:** React (`frontend/`).
- **DB:** SQLite (dev/demo: `backend/live_demo.db`). Postgres in prod.
- **Deploy:** Docker + Render. Config in `deploy/`.
- **Integration adapters:** `backend/integrations/` — calendar, email, Slack, Stripe, Granola, Obsidian, MCP.

## Agent fleet (`backend/agents/`)

| File | Axis | Status |
|------|------|--------|
| `money.agent.yaml` | Revenue / billing | Phase 1 done, scaffold live |
| `customers.agent.yaml` | Customers / churn | Phase 2 |
| `comms.agent.yaml` | Comms / inbox | Phase 2 |
| `meetings.agent.yaml` | Meetings / calendar | Phase 2 |
| `ops.agent.yaml` | Ops / hiring | Phase 2 |
| `coordinator.agent.yaml` | Fleet coordinator | Optional (Anthropic-side delegation) |

One-time setup: `ant beta:agents create < backend/agents/<axis>.agent.yaml`
Set `<AXIS>_AGENT_ID` env vars on Render. Until set, endpoints return `{"status":"not_configured"}`.

## Key routes

- `POST /founders/{id}/agents/{axis}/run` — trigger one axis agent
- `POST /founders/{id}/agents/run` — trigger the full fleet → corroborate → alert

## Workspace (ICM)

```
app/
  CLAUDE.md               Layer 0 — you are here
  CONTEXT.md              Layer 1 — task routing table
  stages/
    01-design/            Scope the agent and its data sources
    02-build/             Write .agent.yaml + managed_agents.py endpoint
    03-adapter/           Write or update the Python integration adapter
    04-test/              Run the agent, validate signal, check corroboration
  _config/                Layer 3 — stable identity + constraints
  shared/                 Layer 3 — cross-stage resources
  setup/                  Onboarding questionnaire
  backend/                FastAPI application code
  frontend/               React frontend
  deploy/                 Docker / Render config
```

Triggers: `setup` → run onboarding. `status` → show pipeline completion.
`build [axis]` → begin Stage 01 design for a named axis agent.

## Corroboration rule

A signal surfaces only when ≥2 distinct axes independently flag it.
This is enforced in `backend/coordinator.py`, not in any agent.
Agents return structured JSON only — they do not decide whether to alert.
