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


def stub_llm(prompt: str) -> str:
    """Return the right shape based on what the prompt asks for."""
    if "SUBJECT:" in prompt:  # draft generation
        return ("SUBJECT: Re: pricing + this week's dip\n"
                "BODY: Hi —\n\nQuick update: we saw a short MRR dip from a pricing "
                "test; here's the diagnosis and the recovery plan. Happy to walk "
                "through Thursday.\n\nBest,\n[Founder]")
    if "WHAT_HAPPENED" in prompt:  # alert synthesis
        return ("WHAT_HAPPENED: MRR fell 11% ($18K->$16K) in 24h with 3 cancellations.\n"
                "WHY_IT_MATTERS: ~$24K ARR at risk; clustered with pricing complaints.\n"
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
from schema import Founder

# Seed a founder directly in the live DB.
db = main.SessionLocal()
if not db.query(Founder).filter(Founder.id == "demo").first():
    db.add(Founder(id="demo", email="demo@founder.test"))
    db.commit()
db.close()
print("\n==> 1. Seeded founder 'demo' (real DB write)")

with TestClient(main.app) as c:
    print("==> 2. Health")
    r = c.get("/health"); check("health 200 + scheduler running", r.status_code == 200 and r.json().get("scheduler_running"))

    print("==> 3. Single signal -> suppressed (>=2 distinct rule, real coordinator)")
    r = c.post("/founders/demo/alerts", json={"signals": [{"type": "revenue_anomaly", "confidence": 0.9, "data": {"mrr": 16000}}]})
    check("single signal suppressed", r.json().get("status") == "suppressed")

    print("==> 4. Two distinct signals -> surfaced (real graph + persistence)")
    r = c.post("/founders/demo/alerts", json={"signals": [
        {"type": "revenue_anomaly", "confidence": 0.9, "data": {"mrr": 16000}},
        {"type": "churn_signal", "confidence": 0.85, "data": {"count": 3}},
    ]})
    check("alert surfaced", r.json().get("status") == "surfaced")
    check("alert has synthesized next_decision", "Pause ads" in (r.json().get("next_decision") or ""))

    print("==> 5. GET alerts (real DB read)")
    r = c.get("/founders/demo/alerts"); check("1 active alert returned", len(r.json()) == 1)

    print("==> 6. Chat with draft intent -> creates a pending draft (real intent + persist)")
    r = c.post("/founders/demo/chat", json={"message": "draft a reply to the investor about the dip"})
    check("chat spawned a draft", "draft_id" in r.json())

    print("==> 7. GET drafts (real DB read)")
    r = c.get("/founders/demo/drafts"); drafts = r.json()
    check("1 pending draft", len(drafts) == 1)
    check("draft has a subject/body", bool(drafts and drafts[0].get("body")))

    print("==> 8. Approve the draft (no creds -> 'approved', send is no-op)")
    did = drafts[0]["id"]
    r = c.post(f"/founders/demo/drafts/{did}/approve"); check("approve recorded", r.json().get("status") in ("approved", "sent"))
    r = c.get("/founders/demo/drafts"); check("no pending drafts left", len(r.json()) == 0)

    print("==> 9. Plain chat question (real reply path)")
    r = c.post("/founders/demo/chat", json={"message": "what's our churn story?"})
    check("chat answered", bool(r.json().get("reply")))

print(f"\n{'ALL ' + str(len(passed)) + ' CHECKS PASSED' if not failed else str(len(failed)) + ' FAILED: ' + str(failed)}")
raise SystemExit(1 if failed else 0)
