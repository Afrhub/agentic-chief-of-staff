"""Phase 1 — run one business-axis agent as an Anthropic Managed Agent and parse
its finding.

Uses raw HTTP (httpx) against the Managed Agents REST API rather than the
`anthropic` beta SDK, because dCern pins an older `anthropic` (via
langchain-anthropic) and upgrading it would risk the deploy. Only invoked when an
axis endpoint is called with the agent/env IDs configured, so it never runs in
the normal request path.

One-time setup is in backend/agents/README.md (create the agent + environment via
the `ant` CLI, then set MONEY_AGENT_ID / DCERN_ENV_ID / ANTHROPIC_API_KEY).
"""
import json
import logging
import os
import re
import time

import httpx

logger = logging.getLogger(__name__)

_API = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/") + "/v1"
_BETA = "managed-agents-2026-04-01"


def _headers() -> dict:
    return {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "anthropic-beta": _BETA,
        "content-type": "application/json",
    }


def run_axis_agent(agent_id: str, environment_id: str, context: str, timeout_s: int = 120) -> dict:
    """Create a session for `agent_id` in `environment_id`, send the axis context,
    wait for the agent to go idle, and return its parsed JSON finding."""
    with httpx.Client(timeout=30) as c:
        s = c.post(f"{_API}/sessions", headers=_headers(),
                   json={"agent": agent_id, "environment_id": environment_id})
        s.raise_for_status()
        sid = s.json()["id"]
        c.post(
            f"{_API}/sessions/{sid}/events", headers=_headers(),
            json={"events": [{"type": "user.message", "content": [{"type": "text", "text": context}]}]},
        ).raise_for_status()

        deadline = time.monotonic() + timeout_s
        texts, idle = [], False
        while time.monotonic() < deadline and not idle:
            time.sleep(3)
            ev = c.get(f"{_API}/sessions/{sid}/events", headers=_headers())
            ev.raise_for_status()
            texts = []  # re-read the full (growing) event list each poll
            for e in ev.json().get("data", []):
                if e.get("type") == "agent.message":
                    texts += [b.get("text", "") for b in e.get("content", []) if b.get("type") == "text"]
                elif e.get("type") in ("session.status_idle", "session.status_terminated"):
                    idle = True
    return _parse_finding("\n".join(texts))


def _json_objects(text: str) -> list:
    """All balanced top-level {...} substrings, in order."""
    objs, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(text[start:i + 1])
    return objs


def _parse_finding(text: str) -> dict:
    """Extract the agent's JSON finding (a fenced ```json block, or the last
    balanced object). Falls back to has_signal=False so callers never crash."""
    text = (text or "").strip()
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates += _json_objects(text)
    candidates.append(text)
    for c in reversed(candidates):
        try:
            d = json.loads(c)
            if isinstance(d, dict) and "has_signal" in d:
                return d
        except Exception:
            continue
    return {"has_signal": False, "raw": text[:500]}


if __name__ == "__main__":
    # ponytail self-check: the finding parser (the only logic runnable without a
    # live Managed Agents session).
    assert _parse_finding('```json\n{"has_signal": true, "type": "revenue_anomaly", "confidence": 0.9}\n```')["has_signal"] is True
    assert _parse_finding('{"has_signal": false}')["has_signal"] is False
    nested = _parse_finding('Here is my analysis.\n{"has_signal": true, "data": {"mrr": 16000}}')
    assert nested["has_signal"] is True and nested["data"]["mrr"] == 16000
    assert _parse_finding("no json at all")["has_signal"] is False
    print("managed_agents parser self-check ok")
