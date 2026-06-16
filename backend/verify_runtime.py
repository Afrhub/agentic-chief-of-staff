"""Runtime verification harness — exercises the real logic without a live DB/LLM.

Run: python verify_runtime.py
Stubs init_db (no Postgres) and the LLM call (no API), then asserts the
behaviours the doctrine depends on.
"""
import os
import unittest.mock as mock
from datetime import datetime, timedelta

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://stub/stub")

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        failures.append(name)


# Stub init_db so importing main doesn't require a live Postgres.
with mock.patch("database.init_db", lambda: None):
    import main
    import coordinator
    from coordinator import AlertSignal

# 1. App + all expected routes registered.
paths = {r.path for r in main.app.routes}
for p in [
    "/health",
    "/founders/{founder_id}/alerts",
    "/founders/{founder_id}/alerts/{alert_id}/decide",
    "/founders/{founder_id}/alerts/{alert_id}/delegate",
    "/founders/{founder_id}/alerts/{alert_id}/dismiss",
    "/founders/{founder_id}/decisions",
    "/slack/actions",
]:
    check(f"route registered: {p}", p in paths)

# 2. _jsonable flattens nested datetimes (the JSON-column crash we fixed).
sample = {"timestamp": datetime.utcnow(), "nested": {"t": datetime.utcnow()}, "list": [datetime.utcnow()]}
out = main._jsonable(sample)
import json as _json
try:
    _json.dumps(out)  # must not raise
    check("_jsonable makes nested datetimes JSON-serializable", True)
except TypeError:
    check("_jsonable makes nested datetimes JSON-serializable", False)

# 3. Coordinator: a single signal must be suppressed (no LLM call, anti-noise rule).
agent = coordinator.CoordinatorAgent()
state_single = {
    "founder_id": "f1", "signals": [AlertSignal(type="revenue_anomaly", confidence=0.9, timestamp=datetime.utcnow(), data={})],
    "identified_decision": None, "confidence_score": 0.0, "what_happened": "", "why_it_matters": "",
    "what_to_do_next": "", "next_decision": "", "similar_past_decision": None, "should_surface_alert": False,
}
r1 = agent.analyze_signals(dict(state_single))
check("single signal suppressed (>=2 distinct rule)", r1["should_surface_alert"] is False)

# 4. Two same-type signals must still be suppressed (needs >=2 DISTINCT types).
state_sametype = dict(state_single)
state_sametype["signals"] = [
    AlertSignal(type="revenue_anomaly", confidence=0.9, timestamp=datetime.utcnow(), data={}),
    AlertSignal(type="revenue_anomaly", confidence=0.9, timestamp=datetime.utcnow(), data={}),
]
r2 = agent.analyze_signals(dict(state_sametype))
check("two same-type signals suppressed (need distinct sources)", r2["should_surface_alert"] is False)

# 5. Two DISTINCT signals surface — with the LLM stubbed out.
with mock.patch.object(
    coordinator.CoordinatorAgent, "_call_with_fallback",
    return_value="WHAT_HAPPENED: MRR dropped 8%\nWHY_IT_MATTERS: revenue risk\nWHAT_TO_DO_NEXT: 1. review\nNEXT_DECISION: pause ads?",
):
    state_two = dict(state_single)
    state_two["signals"] = [
        AlertSignal(type="revenue_anomaly", confidence=0.9, timestamp=datetime.utcnow(), data={}),
        AlertSignal(type="churn_signal", confidence=0.85, timestamp=datetime.utcnow(), data={}),
    ]
    r3 = agent.analyze_signals(dict(state_two))
    check("two distinct signals surface alert", r3["should_surface_alert"] is True)
    check("alert content parsed: what_happened", "MRR dropped" in r3["what_happened"])
    check("alert content parsed: next_decision", "pause ads" in r3["next_decision"])

# 6. Circular fallback: claude fails -> gpt fails -> haiku succeeds.
class _Resp:
    content = "WHAT_HAPPENED: x\nWHY_IT_MATTERS: y\nWHAT_TO_DO_NEXT: z\nNEXT_DECISION: d"

agent2 = coordinator.CoordinatorAgent()
m1 = mock.Mock(); m1.invoke.side_effect = Exception("primary down")
m2 = mock.Mock(); m2.invoke.side_effect = Exception("fallback down")
m3 = mock.Mock(); m3.invoke.return_value = _Resp()
agent2.models = [("primary", m1), ("fallback", m2), ("last_resort", m3)]
with mock.patch.object(coordinator.time, "sleep", lambda *_: None):  # no real backoff sleep
    txt = agent2._call_with_fallback("prompt")
check("circular fallback reaches 3rd model when first two fail", "WHAT_HAPPENED" in txt)

# 7. Embedding fallback returns exactly 1536 dims (matches Vector column).
agent3 = coordinator.CoordinatorAgent()
agent3.embeddings = mock.Mock(); agent3.embeddings.embed_query.side_effect = Exception("no api")
emb = agent3._embed_decision_context("some text")
check("embedding fallback is 1536-dim", len(emb) == 1536)

# 8. build_graph compiles and supports sync .invoke.
g = agent.build_graph()
check("graph compiles with sync invoke", hasattr(g, "invoke"))

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURE(S): {failures}"))
raise SystemExit(1 if failures else 0)
