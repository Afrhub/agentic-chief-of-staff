# dCern agent fleet — Phase 1 (Money axis)

Proves one business-axis agent runs as an Anthropic **Managed Agent** and feeds
its finding back into dCern. Phases 2–3 add the other axes + a coordinator that
corroborates them, then move to a `self_hosted` environment for data residency.

## One-time setup
Requires the `ant` CLI (`brew install anthropics/tap/ant`) authenticated to your
Anthropic org, or use the REST API directly.

```sh
# 1. Create the environment + agent (returns IDs)
ENV_ID=$(ant beta:environments create < backend/agents/environment.yaml --transform id -r)
AGENT_ID=$(ant beta:agents create   < backend/agents/money.agent.yaml   --transform id -r)

# 2. Set these on the dCern backend service (Render dashboard / .env):
#    MONEY_AGENT_ID=$AGENT_ID
#    DCERN_ENV_ID=$ENV_ID
#    ANTHROPIC_API_KEY=...   (already set)
```

Until those three env vars are set, `POST /founders/{id}/agents/money/run` returns
`{"status":"not_configured"}` — it never calls Anthropic, so it's safe to deploy.

## Run it
```sh
# log in to get a token, then:
curl -s -X POST https://<dcern-api>/founders/<FID>/agents/money/run \
  -H "Authorization: Bearer <TOKEN>"
```
Returns the agent's structured finding, e.g.
`{"finding":{"has_signal":true,"type":"revenue_anomaly","confidence":0.9,...},"alert_status":"suppressed (one signal — corroboration is Phase 2)"}`.

A lone money signal is correctly **suppressed** by the ≥2-distinct rule — surfacing
needs a second axis, which is Phase 2 (add customers/comms/meetings/ops agents +
the coordinator's `multiagent` roster).

## Notes
- **Cost:** an agent session per run is real inference. For 24/7 use, switch the
  agent model to `claude-haiku-4-5`, lengthen the cadence, and trigger via a
  scheduled deployment rather than per-request.
- **Security (prod):** move credentials into **vaults** (MCP OAuth + secrets,
  injected at egress) instead of stored keys; switch the environment to
  `self_hosted` so data stays on the founder's box.
- dCern stays the control plane + system of record: the agent produces the
  finding, dCern persists it as an alert and renders it on the board.
