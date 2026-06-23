# dCern Workspace Setup

Answer all questions in one pass. After this, the workspace is configured for
every agent build. Skip any question with a return — defaults apply.

---

1. **Anthropic workspace** — which workspace are your Managed Agents created in?
   (Shown in Claude Console under your `ant` profile.)

2. **Render service name** — the dCern backend service where env vars are set.

3. **Next axis to build** — which agent to tackle after money?
   Options: customers, comms, meetings, ops
   Default: customers

4. **Fleet cadence** — how often should the full fleet run once live?
   Example: every 4 hours, twice daily, once daily
   Default: twice daily

5. **Model preference** — opus for quality vs haiku for cost?
   Default: claude-opus-4-8 (switch to claude-haiku-4-5 for 24/7)

6. **Coordinator agent** — Anthropic-side multi-agent roster, or keep dCern's
   deterministic corroboration pipeline only?
   Default: deterministic pipeline only (coordinator is optional)

---

After answering, record in `_config/identity.md` and point to
`stages/01-design/CONTEXT.md` to begin building the next axis agent.
