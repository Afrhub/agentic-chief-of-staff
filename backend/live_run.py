"""End-to-end live run of the REAL app against a live DB.

What's REAL here: the FastAPI app (via TestClient), every endpoint, the LangGraph
coordinator + its >=2-signal/confidence rules, SQLAlchemy persistence, the
draft -> approve loop, intent detection.
What's STUBBED (no creds in this env): the LLM text output, and pgvector
similarity (SemanticMemory table skipped on SQLite). Slack/Gmail send are no-ops
(no tokens) so drafts land 'approved' rather than 'sent'.

Run:  .venv/bin/python live_run.py
"""
import os
import unittest.mock as mock

os.environ["DATABASE_URL"] = "sqlite:///./live_demo.db"
os.environ.setdefault("ANTHROPIC_API_KEY", "stub")
os.environ.setdefault("OPENAI_API_KEY", "stub")

import database
from schema import Base

# pgvector's Vector column can't be created on SQLite — create every table
# EXCEPT the two vector/JSONB-heavy ones we don't need for this path.
SKIP = {"semantic_memory", "langgraph_checkpoints"}


def sqlite_init():
    tables = [t for n, t in Base.metadata.tables.items() if n not in SKIP]
    Base.metadata.create_all(database.engine, tables=tables)
    print("  DB ready (sqlite):", [t.name for t in tables])


_prompts = []  # capture every prompt so we can assert what reached the LLM


def stub_llm(prompt: str) -> str:
    """Return the right shape based on what the prompt asks for."""
    _prompts.append(prompt)
    if "SUBJECT:" in prompt:  # draft generation
        return ("SUBJECT: Re: pricing + this week's dip\n"
                "BODY: Hi —\n\nQuick update: we saw a short MRR dip from a pricing "
                "test; here's the diagnosis and the recovery plan. Happy to walk "
                "through Thursday.\n\nBest,\n[Founder]")
    if "WHAT_HAPPENED" in prompt:  # alert synthesis (1-3-1)
        return ("WHAT_HAPPENED: MRR fell 11% ($18K->$16K) in 24h with 3 cancellations.\n"
                "WHY_IT_MATTERS: ~$24K ARR at risk; clustered with pricing complaints.\n"
                "OPTIONS:\n1. Pause ads and focus on retention\n"
                "2. Hold spend and run a pricing win-back\n"
                "3. Do nothing for a week and re-measure\n"
                "WHAT_TO_DO_NEXT: 1. Pull the 3 churned accounts.\n2. Pause high-CAC ads.\n"
                "NEXT_DECISION: Pause ads and focus on retention this week?")
    return "Here's my read: revenue dipped on a pricing test — recommend pausing ads while we diagnose."


passed, failed = [], []
def check(name, cond):
    (passed if cond else failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name)


with mock.patch("database.init_db", sqlite_init):
    import main
main.coordinator_agent._call_with_fallback = stub_llm  # stub LLM text only

from fastapi.testclient import TestClient

with TestClient(main.app) as c:
    print("\n==> 1. Health")
    r = c.get("/health"); check("health 200 + scheduler running", r.status_code == 200 and r.json().get("scheduler_running"))

    print("==> 2. Signup -> session token (creates the founder; no manual seed)")
    r = c.post("/auth/signup", json={"email": "founder@test.co", "password": "hunter2hunter"})
    check("signup 200 + token", r.status_code == 200 and bool(r.json().get("token")))
    check("signup rejects short password", c.post("/auth/signup", json={"email": "x@y.co", "password": "short"}).status_code == 400)
    check("signup defaults pack to saas", r.json().get("pack") == "saas")
    check("/packs lists saas + ecommerce", {p["id"] for p in c.get("/packs").json()} >= {"saas", "ecommerce"})
    fid = r.json()["founder_id"]

    print("==> 3. Founder route WITHOUT token -> 401 (the auth gate)")
    check("unauthenticated alerts -> 401", c.get(f"/founders/{fid}/alerts").status_code == 401)

    print("==> 4. Login: wrong password -> 401, right password -> rotated token")
    check("wrong password -> 401", c.post("/auth/login", json={"email": "founder@test.co", "password": "WRONGWRONG"}).status_code == 401)
    r = c.post("/auth/login", json={"email": "founder@test.co", "password": "hunter2hunter"})
    check("login 200 + token", r.status_code == 200 and bool(r.json().get("token")))
    c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})  # authed for the rest

    print("==> 5. Single signal -> suppressed (>=2 distinct rule, real coordinator)")
    r = c.post(f"/founders/{fid}/alerts", json={"signals": [{"type": "revenue_anomaly", "confidence": 0.9, "data": {"mrr": 16000}}]})
    check("single signal suppressed", r.json().get("status") == "suppressed")

    print("==> 6. Two distinct signals -> surfaced (real graph + persistence)")
    r = c.post(f"/founders/{fid}/alerts", json={"signals": [
        {"type": "revenue_anomaly", "confidence": 0.9, "data": {"mrr": 16000}},
        {"type": "churn_signal", "confidence": 0.85, "data": {"count": 3}},
    ]})
    check("alert surfaced", r.json().get("status") == "surfaced")
    check("alert has synthesized next_decision", "Pause ads" in (r.json().get("next_decision") or ""))
    aid = r.json()["alert_id"]

    print("==> 7. GET alerts (authed, real DB read)")
    r = c.get(f"/founders/{fid}/alerts"); check("1 active alert returned", len(r.json()) == 1)
    check("alert carries 3 options (1-3-1)", len(r.json()[0].get("options") or []) == 3)

    print("==> 7b. Defer the alert (waiting on an away person) -> leaves active, auto-resurfaces")
    import datetime as _dt
    past = (_dt.datetime.utcnow() - _dt.timedelta(days=1)).isoformat()
    r = c.post(f"/founders/{fid}/alerts/{aid}/defer", json={"waiting_on": "CFO (on leave)", "until": past})
    check("defer -> status deferred", r.json().get("status") == "deferred")
    check("deferred alert leaves active feed", len(c.get(f"/founders/{fid}/alerts").json()) == 0)
    check("deferred alert shows in deferred view", len(c.get(f"/founders/{fid}/alerts?status=deferred").json()) == 1)
    _db = main.SessionLocal(); main.reactivate_due_deferrals(_db); _db.close()
    check("elapsed deferral auto-resurfaces to active", len(c.get(f"/founders/{fid}/alerts").json()) == 1)

    print("==> 8. Chat with draft intent -> creates a pending draft (real intent + persist)")
    r = c.post(f"/founders/{fid}/chat", json={"message": "draft a reply to the investor about the dip"})
    check("chat spawned a draft", "draft_id" in r.json())

    print("==> 9. GET drafts (real DB read)")
    r = c.get(f"/founders/{fid}/drafts"); drafts = r.json()
    check("1 pending draft", len(drafts) == 1)
    check("draft has a subject/body", bool(drafts and drafts[0].get("body")))

    print("==> 10. Approve the draft (no creds -> 'approved', send is no-op)")
    did = drafts[0]["id"]
    r = c.post(f"/founders/{fid}/drafts/{did}/approve"); check("approve recorded", r.json().get("status") in ("approved", "sent"))
    r = c.get(f"/founders/{fid}/drafts"); check("no pending drafts left", len(r.json()) == 0)

    print("==> 11. Plain chat question (real reply path)")
    r = c.post(f"/founders/{fid}/chat", json={"message": "what's our churn story?"})
    check("chat answered", bool(r.json().get("reply")))

    print("==> 12. Digital Brain (Obsidian) — reads the vault + grounds the chat")
    check("brain reads the obsidian vault", c.get(f"/founders/{fid}/brain").json()["notes"] >= 1)
    check("brain notes injected into chat context", any("FROM YOUR NOTES" in p for p in _prompts))

    print("==> 13. Scorecard — onboarding calibration seeded the targets; readings + on/off track")
    sc = c.get(f"/founders/{fid}/scorecard").json()
    names = {m["name"] for m in sc}
    check("signup auto-calibrated saas targets", {"MRR", "Churn", "Runway", "Pipeline"} <= names)
    mrr = next(m for m in sc if m["name"] == "MRR")
    churn = next(m for m in sc if m["name"] == "Churn")
    check("calibrated MRR target=20000 up", mrr["target"] == 20000 and mrr["direction"] == "up")
    check("calibrated Churn target=5 down", churn["target"] == 5 and churn["direction"] == "down")
    c.post(f"/founders/{fid}/scorecard/metrics/{mrr['id']}/readings", json={"value": 16000})
    c.post(f"/founders/{fid}/scorecard/metrics/{mrr['id']}/readings", json={"value": 18000})
    c.post(f"/founders/{fid}/scorecard/metrics/{churn['id']}/readings", json={"value": 3})
    sc = c.get(f"/founders/{fid}/scorecard").json()
    mrr = next(m for m in sc if m["name"] == "MRR")
    churn = next(m for m in sc if m["name"] == "Churn")
    check("MRR latest=18000, below 20k target -> off track", mrr["latest"] == 18000 and mrr["on_track"] is False)
    check("MRR series carries both readings", len(mrr["series"]) == 2)
    check("Churn 3 <= 5 target (down) -> on track", churn["on_track"] is True)
    check("re-calibrate is idempotent (adds nothing)", c.post(f"/founders/{fid}/scorecard/calibrate").json()["created"] == [])

    print("==> 14. Kanban board — New -> Decided -> Done (verified)")
    b = c.get(f"/founders/{fid}/board").json()
    check("reactivated alert sits in 'new'", any(card["id"] == aid for card in b["new"]))
    c.post(f"/founders/{fid}/alerts/{aid}/decide", json={"decision_text": "Pause ads + retention"})
    b = c.get(f"/founders/{fid}/board").json()
    check("decided alert moves to 'decided'", any(card["id"] == aid for card in b["decided"]))
    c.post(f"/founders/{fid}/alerts/{aid}/verify", json={"impact": "positive", "note": "MRR recovered in 2 weeks"})
    b = c.get(f"/founders/{fid}/board").json()
    check("verified alert moves to 'done'", any(card["id"] == aid for card in b["done"]))
    check("done card carries impact", next(card for card in b["done"] if card["id"] == aid)["impact"] == "positive")

    print("==> 15. Axis-agent fleet + deployment sync — safe no-ops / validation until configured")
    check("single axis agent gated when unconfigured", c.post(f"/founders/{fid}/agents/money/run").json().get("status") == "not_configured")
    check("agent fleet gated when unconfigured", c.post(f"/founders/{fid}/agents/run").json().get("status") == "not_configured")
    check("unknown axis -> 404", c.post(f"/founders/{fid}/agents/bogus/run").status_code == 404)
    check("deployment sync gated when unconfigured", c.post(f"/founders/{fid}/agents/deployments/sync").json().get("status") == "not_configured")

    print("==> 15b. Agent fleet identities (/agents/fleet)")
    fl = c.get("/agents/fleet").json()
    check("fleet lists 5 named agents", len(fl["agents"]) == 5 and all(a["name"] for a in fl["agents"]))
    check("money agent is James, sourced from stripe",
          any(a["axis"] == "money" and a["name"] == "James" and a["source"] == "stripe" for a in fl["agents"]))
    check("coordinator is dCern (the Chief of Staff)", fl["coordinator"]["name"] == "dCern")

    print("==> 16. Corroboration gate — breadth beats dilution (top-2 + breadth bonus)")
    # 3 distinct signals, two strong + one moderate. Old AVG=(0.85+0.85+0.5)/3=0.73 -> suppressed.
    # New: top-2 = 0.85, 3 axes -> threshold 0.75 -> SURFACES.
    r = c.post(f"/founders/{fid}/alerts", json={"signals": [
        {"type": "revenue_anomaly", "confidence": 0.85, "data": {}},
        {"type": "churn_signal", "confidence": 0.85, "data": {}},
        {"type": "team_conflict", "confidence": 0.5, "data": {}},
    ]})
    check("breadth + strong top-2 -> surfaced (no dilution)", r.json().get("status") == "surfaced")
    # 2 distinct but both moderate -> top-2 = 0.625 < 0.8 -> still suppressed.
    r = c.post(f"/founders/{fid}/alerts", json={"signals": [
        {"type": "revenue_anomaly", "confidence": 0.6, "data": {}},
        {"type": "churn_signal", "confidence": 0.65, "data": {}},
    ]})
    check("two moderate signals -> still suppressed", r.json().get("status") == "suppressed")

    print("==> 17. Security hardening — headers, input bounds, rate limiting")
    h = c.get("/health").headers
    check("security headers set (nosniff + frame DENY + HSTS)",
          h.get("x-content-type-options") == "nosniff" and h.get("x-frame-options") == "DENY"
          and "max-age" in (h.get("strict-transport-security") or ""))
    check("oversized password rejected at the edge (422)",
          c.post("/auth/signup", json={"email": "big@y.co", "password": "x" * 500}).status_code == 422)
    codes = [c.post("/auth/login", json={"email": "nope@y.co", "password": "whatever8"}).status_code for _ in range(15)]
    check("auth brute-force is rate limited (429 seen)", 429 in codes)

    print("==> 18. Security-review fixes — webhook signature + SSRF guard")
    os.environ["SLACK_SIGNING_SECRET"] = "test-secret"  # activate the signature check
    check("forged /slack/actions rejected (401)",
          c.post("/slack/actions", data="payload=%7B%7D").status_code == 401)
    blocked = 0
    for bad in ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/", "http://10.0.0.5/", "file:///etc/passwd"]:
        try:
            main._safe_external_url(bad)
        except ValueError:
            blocked += 1
    check("SSRF guard blocks metadata/loopback/private/non-http", blocked == 4)
    check("SSRF guard allows a public address",
          main._safe_external_url("http://93.184.216.34/x") == "http://93.184.216.34/x")
    # webhook signature must fail CLOSED in production when the secret is absent
    del os.environ["SLACK_SIGNING_SECRET"]
    os.environ["DCERN_ENV"] = "production"
    check("prod + no signing secret -> /slack/actions fails closed (401)",
          c.post("/slack/actions", data="payload=%7B%7D").status_code == 401)
    del os.environ["DCERN_ENV"]
    # per-account login throttle — IP-independent, so XFF spoofing can't bypass it
    main._LOGIN_FAILS["victim@throttle.test"] = [9e18] * 10  # 10 recent failures
    check("per-email login throttle locks an account after 10 fails", main._login_locked("victim@throttle.test"))

print(f"\n{'ALL ' + str(len(passed)) + ' CHECKS PASSED' if not failed else str(len(failed)) + ' FAILED: ' + str(failed)}")
raise SystemExit(1 if failed else 0)
