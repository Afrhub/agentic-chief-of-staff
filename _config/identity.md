# dCern Identity

Who dCern is and the constraints every agent must respect.

## Product

dCern is an AI Chief of Staff for founders. A fleet of specialist Managed Agents
(one per axis) runs on a schedule, each returning a structured signal. dCern's
deterministic pipeline corroborates via the ≥2-distinct rule and surfaces a
1-3-1 alert only when multiple axes agree.

## Agent Fleet

| Axis | Agent | Phase | Status |
|------|-------|-------|--------|
| money | money.agent.yaml | 1 | Done — scaffold live |
| customers | customers.agent.yaml | 2 | Build next |
| comms | comms.agent.yaml | 2 | Build next |
| meetings | meetings.agent.yaml | 2 | Build next |
| ops | ops.agent.yaml | 2 | Build next |
| coordinator | coordinator.agent.yaml | optional | Anthropic-side delegation |

## Corroboration Rule

A 1-3-1 alert surfaces only when ≥2 distinct axes independently flag `has_signal: true`
in the same fleet run. Enforced in `backend/coordinator.py`. Agents never decide
whether to alert — only whether they have a signal.

## Security Rules

- Agents receive only the context passed in the session — no direct DB or API access.
- API keys and credentials live in env vars on Render, never in code or YAML.
- Agent IDs (`[AXIS]_AGENT_ID`) set on Render. Until set, endpoints return `{"status":"not_configured"}`.
- The `ant` CLI is authenticated to the Anthropic workspace — one-time human action per agent.

## Model Choice

Default: `claude-opus-4-8` for all axis agents.
Cost lever: switch to `claude-haiku-4-5` for high-frequency 24/7 scanning.
Document any model change in the agent YAML comment.
