# Agent Test Checklist

Standard checks for every axis agent added to dCern.

## Safe-by-default (no agent ID set)

- [ ] `POST /founders/{id}/agents/[axis]/run` returns `{"status":"not_configured"}`
- [ ] No exception or 500 error when agent ID env var is absent

## Scaffold run (agent ID set, seed data)

- [ ] `ant beta:agents create` succeeds, returns an agent ID
- [ ] Agent ID set in local env: `export [AXIS]_AGENT_ID=agent_...`
- [ ] `POST /founders/{id}/agents/[axis]/run` returns a valid signal
- [ ] Signal shape matches `shared/signal-shape.md` (has_signal, type, confidence, summary, data)
- [ ] `confidence` is between 0.0 and 1.0
- [ ] `data` contains only fields from the seed snapshot — no invented numbers

## Corroboration (full fleet)

- [ ] `POST /founders/{id}/agents/run` completes without error
- [ ] One-axis-only run: no alert surfaced (lone signal suppressed)
- [ ] Two-axis run (mock second axis): alert surfaced correctly

## Adapter

- [ ] Adapter returns a snapshot with seed data when credentials are absent
- [ ] No API keys appear in logs or response bodies
- [ ] All required snapshot fields present and non-null

## Cleanup

- [ ] Test results written to `output/[axis]-test-results.md`
- [ ] Agent ID removed from local env (or noted as needed for ongoing dev)
