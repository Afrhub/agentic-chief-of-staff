# Self-Hosted Install — dCern (Phase 2)

Run the entire product on **your own** infrastructure. Your business data —
signals, alerts, decisions, memory, OAuth tokens — lives only in this stack and
never touches the vendor's systems.

## What you get

One Docker Compose stack, fully isolated to your host:

```
┌──────────────────────── your server / VPC ────────────────────────┐
│  web (nginx)  ──proxy──>  backend (FastAPI + scheduler)            │
│      │                          │                                  │
│   browser                    db (PostgreSQL + pgvector)            │
│                                                                    │
│  [optional] ollama  ← fully-local LLM, nothing leaves the host     │
└────────────────────────────────────────────────────────────────────┘
```

## Requirements
- Docker + Docker Compose v2
- ~2 vCPU / 4 GB RAM for the app (Mode A). Add a GPU only for Mode B (local LLM).

## Install

```bash
cd deploy
cp .env.example .env
$EDITOR .env            # set DB password, your LLM keys, integration tokens

make up                 # build + start db, backend, web
make seed               # create a demo founder
make smoke              # end-to-end check (health -> DB -> API -> decision loop)

open http://localhost:8080      # or your configured WEB_PORT
```

`make help` lists every target. Without `make`, the equivalents are:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec -T backend python seed.py
./smoke.sh
```

The database schema is created automatically on first boot.

### Smoke test

`make smoke` verifies the real path: it waits for `/health`, seeds a founder
(proves DB writes), reads alerts back (proves DB reads + nginx routing), and
confirms a single signal is correctly **suppressed** by the ≥2-signal rule
(needs no LLM). If LLM keys are set in `.env`, it also drives the full
**surface → decide → read-back** loop. A green run means the stack is wired
end-to-end.

## LLM mode (data-residency choice)

See [`../docs/llm-inference.md`](../docs/llm-inference.md) for the full decision record.

- **Mode A — cloud (default).** Set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` to
  **your own** accounts. Prompt content is processed by that vendor under your
  account's terms — never by us. Best quality, zero ops.
- **Mode B — fully local.** Set `LLM_MODE=local`, then:
  ```bash
  docker compose -f docker-compose.prod.yml --profile local-llm up -d
  docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.1:70b
  docker compose -f docker-compose.prod.yml exec ollama ollama pull nomic-embed-text
  ```
  Nothing leaves your host. Requires a capable GPU; quality is below frontier.

## What leaves your host

| Mode | Leaves the host |
|---|---|
| A (cloud) | Prompt content → your own Anthropic/OpenAI account only |
| B (local) | Nothing |
| Either | Outbound calls *you* configure: Stripe/Slack/Google APIs to read your signals |

The vendor receives **no founder data** and **no PII** — at most an opt-in,
PII-free license heartbeat (`LICENSE_KEY`).

## Operations
- **Logs:** `docker compose -f docker-compose.prod.yml logs -f backend`
- **Backup:** snapshot the `cos_pgdata` volume.
- **Update:** `git pull && docker compose -f docker-compose.prod.yml up -d --build`
- **Scheduler:** runs inside the single backend process (evaluates every 5 min).
  Do **not** scale `backend` to multiple replicas — it would duplicate the job.

## Notes
- TLS: put this behind your own reverse proxy / load balancer (Caddy, ALB, etc.)
  and terminate HTTPS there. The stack listens HTTP on `WEB_PORT`.
- Single-tenant by design: one stack = one company. All queries are already
  scoped by `founder_id`, so isolation holds.
