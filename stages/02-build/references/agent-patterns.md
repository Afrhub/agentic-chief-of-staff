# Agent Patterns

Conventions for all dCern axis agents.

## .agent.yaml structure

Follow `backend/agents/money.agent.yaml` exactly:

```yaml
# dCern [Axis]-axis agent. Create once:
#   ant beta:agents create < backend/agents/[axis].agent.yaml --transform id -r
# Set [AXIS]_AGENT_ID on the dCern service.
name: dCern [Axis] Agent
model: claude-opus-4-8
system: |
  You are dCern's [AXIS]-axis analyst. You receive a snapshot of a founder's
  [axis] context. Decide whether there is a single decision-worthy signal...

  Return ONLY a fenced ```json code block, and nothing else, with this shape:
  {
    "has_signal": true,
    "type": "string",
    "confidence": 0.0-1.0,
    "summary": "one concise sentence a founder can read in 3 seconds",
    "data": { "the": "figures that justify it" }
  }
  If nothing is decision-worthy, return {"has_signal": false}. Do not invent
  numbers — only use what's in the snapshot.
tools:
  - type: agent_toolset_20260401
```

## FastAPI endpoint pattern

Follow the money endpoint in `backend/agents/managed_agents.py`:

```python
@router.post("/founders/{founder_id}/agents/[axis]/run")
async def run_[axis]_agent(founder_id: str, ...):
    agent_id = os.getenv("[AXIS]_AGENT_ID")
    if not agent_id:
        return {"status": "not_configured"}
    # 1. Build context from adapter
    context = build_[axis]_context(founder_id, ...)
    # 2. Run agent
    result = await run_managed_agent(agent_id, context)
    # 3. Parse signal
    finding = parse_agent_signal(result)
    # 4. Ingest
    ingest_finding(founder_id, "[axis]", finding)
    return finding
```

## Signal parsing

The agent returns a fenced ```json block in its text output.
Extract it with the same regex used in the money agent.
Never trust the raw text — always parse the JSON block explicitly.

## Cost note

`claude-opus-4-8` per session. For 24/7 scheduled runs, switch to
`claude-haiku-4-5` (cheaper, fast enough for structured signal extraction).
Document the model in the YAML comment.
