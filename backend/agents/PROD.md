# dCern fleet — production runbook (Phase 3)

Takes the agent fleet from "dCern passes a snapshot" to **live data via MCP +
vaults, a self-hosted (data-residency) environment, and a 24/7 scheduled
deployment**. These are Anthropic-side + infra steps you run; the dCern code that
hooks into them already ships (gated, safe).

## 1. Credentials → vaults (not stored keys)
Create a vault per founder and add each connector's MCP OAuth credential. The
secret never enters the container — it's injected at egress.
```sh
VAULT_ID=$(ant beta:vaults create --name "founder-<id>" --transform id -r)
# add an MCP OAuth credential (e.g. Granola) — shape in the managed-agents vault docs
ant beta:vaults:credentials create --vault-id "$VAULT_ID" < granola-credential.json
```
Set `DCERN_VAULT_ID=$VAULT_ID` on the dCern service — `_run_axis` attaches it to
every session so the agents' MCP tools authenticate.

## 2. Live data → MCP on each agent
Declare the connector's MCP server + an `mcp_toolset` on the agent (done for
`meetings` → Granola in `meetings.agent.yaml`). Pattern for the others:
```yaml
mcp_servers:
  - { type: url, name: stripe, url: https://<stripe-mcp-url> }   # money
tools:
  - type: agent_toolset_20260401
  - { type: mcp_toolset, mcp_server_name: stripe }
```
Re-apply the agent (`ant beta:agents update --agent-id <id> --version N < money.agent.yaml`).
The agent now pulls live instead of relying on dCern's snapshot.

## 3. Data residency → self-hosted environment
```sh
ENV_ID=$(ant beta:environments create < backend/agents/environment.self-hosted.yaml --transform id -r)
# generate an environment key in the Console, then run a worker on the founder's box:
ANTHROPIC_ENVIRONMENT_KEY=sk-ant-oat01-... ant beta:worker poll --environment-id "$ENV_ID" --workdir /workspace
```
Point `DCERN_ENV_ID` at this env. Tool execution + data now run on their infra;
only the agent loop is Anthropic-side.

## 4. 24/7 → scheduled deployment (replaces the in-app cron)
Fill `deployment.yaml` (coordinator agent ID + env ID), then create it:
```sh
curl -fsSL https://api.anthropic.com/v1/deployments \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" -H "content-type: application/json" \
  --data-binary @<(yq -o=json backend/agents/deployment.yaml)
```
Set `DCERN_DEPLOYMENT_ID` to the returned `depl_...`. The cron now fires the
coordinator hourly; dCern's APScheduler fleet-tick can be retired.

## 5. Results back into dCern
`POST /founders/{id}/agents/deployments/sync` pulls the newest deployment run's
finding and ingests it as an alert. Trigger it on a light dCern cron (every few
min) **or** register a webhook in the Console pointing at dCern.
> Webhook signature verification needs the current `anthropic` SDK
> (`client.beta.webhooks.unwrap`); dCern pins an older one, so the **poll-sync
> endpoint is the shipped path**. Wire the webhook when you upgrade the SDK.

## Security & cost recap
- **Security:** credentials live in vaults (Phase 3) — close the plaintext-key
  gap by migrating Stripe/Slack/Gmail the same way. `self_hosted` keeps data on
  the founder's infra.
- **Cost:** a coordinator + 5 sub-agents per fire is real inference. Use
  `claude-haiku-4-5` on axis agents, an hourly (not 5-min) cadence, and let the
  ≥2-corroboration gate keep noise (and spend) down.
