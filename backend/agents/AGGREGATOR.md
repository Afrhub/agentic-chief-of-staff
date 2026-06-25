# MCP aggregator — reach thousands of tools through one slot

Each axis agent already declares its own MCP source (Stripe for money, etc.). The
**aggregator slot** adds *one more* MCP server to **every** agent — a hosted aggregator
(Composio / Zapier / Pipedream / any hosted MCP) that fans out to thousands of apps —
so you don't hand-wire each tool. It's optional and vendor-neutral.

## How it works
- One env var, set by the **operator** (not founders): `DCERN_AGGREGATOR_MCP_URL` (https).
  Optional `DCERN_AGGREGATOR_NAME` (default `aggregator`).
- `create_agents.py` injects it into every agent's `mcp_servers` + a `mcp_toolset`.
- The aggregator's credential rides in the **vault** (`DCERN_VAULT_ID`), like every
  other connector — never on the agent, never in dCern's DB.
- Unset → nothing changes (fully backward compatible). The Team view shows the
  aggregator under each agent's connectors when it's on.

## Activate (any one vendor)
1. Pick a vendor and get your hosted MCP URL:

   | Vendor | Endpoint | Auth | Reach |
   |--------|----------|------|-------|
   | **Composio** | `https://connect.composio.dev/mcp` (or user-scoped `https://backend.composio.dev/v3/mcp/<server_id>?user_id=…`) | `x-api-key` (in vault) | 500+ apps, managed per-app OAuth |
   | **Zapier** | per-server `https://mcp.zapier.com/…` (from mcp.zapier.com → Connect) | the **URL itself is the secret** (rotatable) | 9,000 apps / 30,000 actions |
   | **Pipedream** | `https://mcp.pipedream.com/{user}/{app}` | managed OAuth per user/app | 10,000+ tools |

2. Add that vendor's connector/credential to your **vault** (`DCERN_VAULT_ID`) so the
   managed agent authenticates at egress. (For Zapier the secret is the URL itself —
   keep it only in the env var, treat it like a password, rotate via "Rotate token".)
3. Set on Render: `DCERN_AGGREGATOR_MCP_URL=<https url>` (+ optional `DCERN_AGGREGATOR_NAME`).
4. Re-run `create_agents.py` and update the `*_AGENT_ID`s — the agents now have the aggregator.

## Notes
- **https only** — a non-https value is ignored (no plaintext aggregator endpoints).
- The URL is **operator-set**, so it isn't a founder-controlled SSRF vector; it's never
  logged (it can embed a secret).
- Sources: [Composio](https://docs.composio.dev/docs/mcp-quickstart) · [Zapier MCP](https://zapier.com/mcp) · [Pipedream](https://pipedream.com/docs/connect/mcp/developers).
