"""The dCern agent fleet — human identities for the per-axis Managed Agents.

ONE source of truth. It drives BOTH:
  - the agent persona, prepended to each agent's system prompt at creation
    (see create_agents.py), and
  - the /agents/fleet metadata the dashboard renders.

A persona adds VOICE and PRIORITISATION; it never changes the doctrine. Each
agent still returns structured JSON only and never decides whether to alert —
the coordinator's corroboration gate does that (see coordinator.analyze_signals).
"""
import os

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))

ROSTER = {
    "money": {
        "name": "James",
        "role": "Finance Director",
        "traits": ["numbers-first", "calm under pressure", "conservative", "no vanity metrics"],
        "watches": "MRR, churn-driven revenue loss, failed-payment spikes, runway",
        "persona": ("You are James, the founder's Finance Director — numbers-first, calm, "
                    "conservative, and allergic to vanity metrics. You quantify every claim."),
    },
    "customers": {
        "name": "Sofia",
        "role": "Head of Customer Success",
        "traits": ["empathetic", "data-driven", "retention-obsessed", "hears churn early"],
        "watches": "cancellations, pre-churn behaviour, health-score and NPS drops",
        "persona": ("You are Sofia, the founder's Head of Customer Success — empathetic but "
                    "data-driven and retention-obsessed. You hear quiet churn before it hits MRR."),
    },
    "comms": {
        "name": "Marcus",
        "role": "Chief of Staff (gatekeeper)",
        "traits": ["discerning", "protects your attention", "politically astute", "fast triage"],
        "watches": "investor/VIP inbound, time-sensitive external asks, team friction",
        "persona": ("You are Marcus, the founder's gatekeeping Chief of Staff — discerning and "
                    "protective of their attention. You can tell a VIP signal from noise."),
    },
    "meetings": {
        "name": "Priya",
        "role": "Executive Assistant",
        "traits": ["meticulous", "never drops a commitment", "deadline-aware", "reads subtext"],
        "watches": "commitments made, deadlines, risks and competitor mentions in meetings",
        "persona": ("You are Priya, the founder's Executive Assistant — meticulous, you never drop "
                    "a commitment, and you read the subtext of a meeting, not just the words."),
    },
    "ops": {
        "name": "David",
        "role": "Head of Operations",
        "traits": ["reliability-first", "process-minded", "watches quiet failures", "unflappable"],
        "watches": "uptime/incidents, hiring and people-runway, process breakdowns",
        "persona": ("You are David, the founder's Head of Operations — reliability-first and "
                    "process-minded. You catch the things that break quietly."),
    },
}

# The Chief of Staff that synthesises the team. Not an axis scanner — it only
# interrupts the founder when >=2 of the team independently corroborate.
COORDINATOR = {
    "name": "dCern",
    "role": "Chief of Staff",
    "traits": ["synthesises the team", "ruthless about noise", "1-3-1 framing", "decides nothing alone"],
    "watches": "the whole fleet — surfaces only corroborated, decision-worthy alerts",
}


def persona_for(axis: str) -> str:
    """The voice line prepended to an axis agent's system prompt at creation."""
    r = ROSTER.get(axis)
    return r["persona"] if r else ""


def aggregator_server():
    """Operator-configured MCP aggregator (Composio / Zapier / Pipedream / any hosted
    MCP) that fans out to thousands of tools through one endpoint. Returns {name, url}
    when DCERN_AGGREGATOR_MCP_URL is set to an https URL, else None. It's operator-set
    (env), not founder input — but we still require https. Single source of truth used
    by create_agents.py (injection) and fleet_meta (display)."""
    url = os.getenv("DCERN_AGGREGATOR_MCP_URL", "").strip()
    if not url.startswith("https://"):
        return None  # unset or non-https -> disabled (no plaintext aggregator endpoints)
    name = os.getenv("DCERN_AGGREGATOR_NAME", "aggregator").strip() or "aggregator"
    return {"name": name, "url": url}


def fleet_meta() -> list:
    """Roster + each agent's model and live data source (read from its YAML) —
    the shape the dashboard's team view renders."""
    out = []
    agg = aggregator_server()
    for axis, r in ROSTER.items():
        model, connectors = None, []
        try:
            y = yaml.safe_load(open(os.path.join(_HERE, f"{axis}.agent.yaml")))
            model = y.get("model")
            connectors = [s.get("name") for s in (y.get("mcp_servers") or []) if s.get("name")]
        except Exception:
            pass  # missing/unparseable YAML -> identity still renders, connectors empty
        if agg and agg["name"] not in connectors:
            connectors = connectors + [agg["name"]]  # operator-wide MCP aggregator
        out.append({
            "axis": axis, "name": r["name"], "role": r["role"],
            "traits": r["traits"], "watches": r["watches"],
            "model": model,
            "source": connectors[0] if connectors else "scorecard",  # primary (Team-card label)
            "connectors": connectors,            # every MCP server this agent declares
            "tools": ["agent toolset (bash · files)"] + [f"{c} (MCP)" for c in connectors],
            "cadence": "Hourly",                 # design cadence; on-demand until 24/7 deployment is on
            # Avatar lives in the frontend's static assets; path derives from the
            # name. Missing file -> the UI falls back to the initial (see Fleet.tsx).
            "avatar": f"/avatars/{r['name'].lower()}.png",
        })
    return out


if __name__ == "__main__":
    # ponytail self-check: roster covers exactly the five axes, personas resolve,
    # and the UI meta merges in each agent's model + source from its YAML.
    assert set(ROSTER) == {"money", "customers", "comms", "meetings", "ops"}, set(ROSTER)
    assert all(r["name"] and r["role"] and r["traits"] and r["persona"] for r in ROSTER.values())
    assert persona_for("money").startswith("You are James")
    assert persona_for("bogus") == ""
    meta = {m["axis"]: m for m in fleet_meta()}
    assert meta["money"]["source"] == "stripe", meta["money"]
    assert meta["meetings"]["source"] == "granola", meta["meetings"]
    assert meta["customers"]["source"] == "intercom", meta["customers"]
    assert meta["comms"]["source"] == "slack", meta["comms"]
    assert meta["ops"]["source"] == "datadog", meta["ops"]
    assert meta["money"]["avatar"] == "/avatars/james.png", meta["money"]
    # aggregator slot: off by default, https-only, reflected in connectors when on
    assert aggregator_server() is None
    os.environ["DCERN_AGGREGATOR_MCP_URL"] = "http://insecure/mcp"
    assert aggregator_server() is None, "non-https must be refused"
    os.environ["DCERN_AGGREGATOR_MCP_URL"] = "https://connect.composio.dev/mcp"
    assert aggregator_server()["name"] == "aggregator"
    assert "aggregator" in fleet_meta()[0]["connectors"]
    del os.environ["DCERN_AGGREGATOR_MCP_URL"]
    assert aggregator_server() is None and "aggregator" not in fleet_meta()[0]["connectors"]
    print("identities self-check ok:", [m["name"] for m in fleet_meta()])
