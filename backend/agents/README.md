# dCern agent fleet

A specialist **Managed Agent per business axis** (money, customers, comms,
meetings, ops). dCern triggers them, collects their findings, and corroborates
via the **≥2-distinct rule** into a surfaced 1-3-1 alert. dCern stays the control
plane + system of record; the agents are the intelligence layer.

- **Phase 1:** Money agent end-to-end (done).
- **Phase 2 (here):** all five axis agents + dCern fleet orchestration.
- **Phase 3:** per-agent live data via MCP/vaults, `self_hosted` environment for
  data residency, and a scheduled deployment for 24/7 (replaces the in-app cron).

## One-time setup (`ant` CLI, authenticated to your Anthropic workspace)
```sh
ENV_ID=$(ant beta:environments create < backend/agents/environment.yaml --transform id -r)
for axis in money customers comms meetings ops; do
  ID=$(ant beta:agents create < backend/agents/$axis.agent.yaml --transform id -r)
  echo "${axis^^}_AGENT_ID=$ID"      # e.g. MONEY_AGENT_ID=agent_...
done
```
Set on the dCern service (Render): `DCERN_ENV_ID`, `MONEY_AGENT_ID`,
`CUSTOMERS_AGENT_ID`, `COMMS_AGENT_ID`, `MEETINGS_AGENT_ID`, `OPS_AGENT_ID`
(and the existing `ANTHROPIC_API_KEY`). The agents appear in your **Claude
Console** under the workspace tied to your `ant` profile. Until the IDs are set,
the endpoints return `{"status":"not_configured"}` — safe to deploy.

## Run
```sh
# one axis (a lone signal is correctly suppressed)
curl -sX POST https://<dcern-api>/founders/<FID>/agents/money/run -H "Authorization: Bearer <TOKEN>"
# the whole fleet -> corroborates -> surfaces an alert when >=2 axes agree
curl -sX POST https://<dcern-api>/founders/<FID>/agents/run        -H "Authorization: Bearer <TOKEN>"
```

## Corroboration: dCern vs the coordinator
`POST /agents/run` orchestrates the fleet and corroborates in dCern's
deterministic pipeline (keeps the ≥2 rule + 1-3-1 synthesis in code). This is the
recommended path. `coordinator.agent.yaml` is the alternative — Anthropic runs the
delegation server-side via a `multiagent` roster; fill in the five agent IDs and
create it only if you want that.

## Notes
- **Cost:** each run = real inference (a session per axis). For 24/7, use
  `claude-haiku-4-5` on the axis agents, lengthen cadence, and trigger via a
  scheduled deployment, not per-request.
- **Security (prod):** move credentials into **vaults** (MCP OAuth + secrets,
  injected at egress) and switch the environment to `self_hosted`.
