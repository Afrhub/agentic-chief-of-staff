# dCern — Security Posture

Audit scope: every endpoint in `backend/main.py`, the data flows to/from each connected
tool (Stripe / Intercom / Slack / Granola / Datadog via MCP + the server-side adapters),
each managed agent, the auth/session layer, CORS, and secret handling. Mapped to OWASP
Top 10 (2021). Last reviewed 2026-06-23.

## What's already sound

| Area | Finding |
|------|---------|
| **A01 Access control / IDOR** | The session gate (`_require_session`) extracts `founder_id` from the path **and** verifies the bearer token equals *that founder's* `session_token` via constant-time `hmac.compare_digest`. One founder's token cannot read another's `/founders/{id}/*`. One chokepoint — a new route can't forget to auth. |
| **A07 Auth** | Passwords hashed with PBKDF2-HMAC-SHA256 (240k iters, `auth.py`). Login returns a generic *"Invalid email or password"* — no account enumeration. Opaque session tokens (`secrets.token_urlsafe`), rotated on each login. |
| **A03 Injection** | All DB access is via SQLAlchemy ORM (parameterised) — no string-built SQL. |
| **Agent / tool egress** | Agents return **structured JSON only** and never decide to alert (the deterministic coordinator gate does). MCP OAuth credentials live in an Anthropic **vault**, injected at session egress — **never stored in dCern's DB or logs**. Agents declare a fixed allow-list of MCP server URLs in YAML (not user-supplied → no agent-driven SSRF). |

## Fixed in this pass

| # | OWASP | Issue | Fix |
|---|-------|-------|-----|
| 1 | A07 / API | No brute-force / DoS protection | **Rate limiting** middleware (in-process sliding window): `/auth/*` = 12 req / 5 min, everything else = 240 req / min → `429` + `Retry-After`. Keyed by client IP (`X-Forwarded-For` aware). |
| 2 | A05 | `CORS allow_origins=["*"]` with credentials (reflected any origin) | Explicit **allow-list** via `DCERN_ALLOWED_ORIGINS` (defaults to the Netlify origins + localhost); methods/headers narrowed to what's used. |
| 3 | A05 | No security headers | **Security-headers** middleware: HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, restrictive CSP on the JSON API; strips `Server` / `X-Powered-By`. Frontend gets the same safe set via `frontend/public/_headers`. |
| 4 | A03 | Unbounded request bodies | `Field(max_length=…)` on user-supplied strings (email 254, password 200 — also guards PBKDF2 DoS, chat/draft 8000, access_token 2000). Oversized input → `422` at the edge. |

Verified: `backend/live_run.py` 48/48 (incl. headers present, oversized input rejected, auth `429` under brute force).

## Recommended next (not yet done)

| Priority | OWASP | Item | Why / how |
|----------|-------|------|-----------|
| **P1** | A02 | **Encrypt `IntegrationState` secrets at rest** | The server-side adapter tokens (Stripe REST key, Slack token, etc.) are stored plaintext. Encrypt with Fernet under a `DCERN_SECRET_KEY` env (never in code); decrypt only at use. (Agent MCP creds are already vault-side and unaffected.) |
| **P1** | A05 | **Content-Security-Policy on the frontend** | Needs `INLINE_RUNTIME_CHUNK=false` in the Netlify build + `script-src 'self'`, then a deploy-preview to confirm no white-screen. Held back here precisely to avoid breaking the live site unverified. |
| P2 | A07 | **Account lockout** | Rate limiting throttles brute force; add per-account lockout after N failures for defence in depth. |
| P2 | A06 | **Dependency scanning in CI** | `pip-audit` (backend) + `npm audit --audit-level=high` (frontend) on each push. |
| P2 | A09 | **Audit logging** | Structured log of auth events + decisions (no tokens/PII) to a tamper-evident sink. |
| P3 | A10 | **Review adapter URL inputs** | If any integration config lets a founder set a fetched URL server-side, add an allow-list / block private IP ranges (SSRF). MCP server URLs are already fixed. |

## Notes
- Rate-limit counters are **per-process** — correct for single-instance Render; a multi-instance
  deploy needs shared state (Redis), or counters won't sync across workers.
- Findings here are tracked in-repo (single-tenant, founder-scoped app). For a public program,
  move sensitive reproduction detail to a restricted tracker.
