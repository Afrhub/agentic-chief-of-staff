# Spec: MCP aggregator slot

## Objective
Let dCern's agents reach thousands of additional tools through a single, **operator-
configured** MCP aggregator (Composio / Zapier / Pipedream / any hosted MCP server) —
without hand-wiring each tool's MCP server and without changing dCern's architecture.

## Requirements
1. **Vendor-neutral, env-configured by the operator:**
   - `DCERN_AGGREGATOR_MCP_URL` — the hosted aggregator MCP endpoint (must be `https://`).
   - `DCERN_AGGREGATOR_NAME` — optional connector/display name (default `aggregator`).
2. **When set**, every axis agent gains the aggregator as an additional `mcp_server` +
   `mcp_toolset` at creation (`create_agents.py`), alongside its existing per-axis MCP.
3. **When unset**, behaviour is unchanged — fully backward compatible, no aggregator.
4. The aggregator credential rides in the existing **vault** (`DCERN_VAULT_ID`) — never
   on the agent, never in dCern's DB (same pattern as Stripe/Granola).
5. `GET /agents/fleet` reflects the aggregator in each agent's `connectors`/`tools` when
   configured, so the Team view shows it.
6. **Security:**
   - URL must be `https://` (reject otherwise — no plaintext aggregator endpoints).
   - It is operator-set (env), NOT founder input → not a founder SSRF vector.
   - The URL is **not logged** (it can embed a secret, e.g. Zapier's URL-as-key).
7. **Single source of truth** for the aggregator config (one helper), used by both agent
   creation and the fleet metadata — no drift.
8. **Documented setup** for Composio, Zapier, and Pipedream with their real endpoints.

## Definition of done
- `aggregator_server()` returns `{name, url}` when the env is set to an https URL, else `None`.
- `create_agents.py` injects it into every agent when set.
- `fleet_meta()` includes it (connectors + tools) when set.
- Backward compatible (unset → unchanged); `live_run.py` stays green.
- Setup doc with verified vendor URLs.
- Self-check covers: set→present, https-only, unset→absent.
