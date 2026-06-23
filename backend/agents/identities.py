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


def fleet_meta() -> list:
    """Roster + each agent's model and live data source (read from its YAML) —
    the shape the dashboard's team view renders."""
    out = []
    for axis, r in ROSTER.items():
        model, source = None, "scorecard"
        try:
            y = yaml.safe_load(open(os.path.join(_HERE, f"{axis}.agent.yaml")))
            model = y.get("model")
            servers = y.get("mcp_servers") or []
            if servers:
                source = servers[0].get("name", source)
        except Exception:
            pass  # missing/unparseable YAML -> identity still renders, source falls back
        out.append({
            "axis": axis, "name": r["name"], "role": r["role"],
            "traits": r["traits"], "watches": r["watches"],
            "model": model, "source": source,
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
    assert meta["customers"]["source"] == "scorecard", meta["customers"]  # no MCP yet
    assert meta["money"]["avatar"] == "/avatars/james.png", meta["money"]
    print("identities self-check ok:", [m["name"] for m in fleet_meta()])
