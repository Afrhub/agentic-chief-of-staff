# Agent Signal Shape

Every axis agent returns exactly this JSON shape (fenced ```json block, nothing else).

## Shape

```json
{
  "has_signal": true,
  "type": "string",
  "confidence": 0.0,
  "summary": "one concise sentence a founder can read in 3 seconds",
  "data": {}
}
```

Or when nothing is decision-worthy:

```json
{ "has_signal": false }
```

## Rules

- `has_signal` is always present and boolean.
- When `true`: `type`, `confidence`, `summary`, and `data` are all required.
- `confidence` is a float 0.0–1.0.
- `summary` is one sentence, readable in 3 seconds.
- `data` contains only figures from the input — no invented numbers.
- No keys outside this schema. No prose outside the JSON block.

## Type values by axis

| Axis | Example types |
|------|---------------|
| money | `revenue_anomaly`, `churn_revenue_loss`, `runway_risk`, `payment_failure_spike` |
| customers | `churn_spike`, `nps_drop`, `activation_stall`, `support_volume_surge` |
| comms | `inbox_overload`, `unanswered_thread_risk`, `stakeholder_silence` |
| meetings | `calendar_overload`, `no_focus_time`, `missed_commitment` |
| ops | `hiring_stall`, `team_capacity_risk`, `deadline_miss` |

## Corroboration

`backend/coordinator.py` surfaces a 1-3-1 alert only when ≥2 distinct axes
return `has_signal: true` for the same founder in the same run.
Agents do not decide whether to alert — they only decide whether they have a signal.
