# Python Adapter Contract

Every adapter in `backend/integrations/` must implement this interface.
Reference: existing adapters (stripe_adapter.py, slack_adapter.py, etc.).

## Interface

```python
class [Name]Adapter:
    def __init__(self, config: dict):
        """Initialise with env-var-sourced config (no hardcoded secrets)."""

    def get_snapshot(self, founder_id: str) -> dict:
        """
        Return a structured snapshot for this axis.
        Must work with seed/sample data when credentials are absent.
        """
```

## Snapshot shapes by axis

```python
# money
{"mrr": 0.0, "churn_rate": 0.0, "failed_payments": 0, "runway_months": 0.0}

# customers
{"active_users": 0, "churned_this_month": 0, "nps": 0.0, "support_tickets_open": 0}

# comms
{"unread_count": 0, "threads_awaiting_reply": 0, "oldest_unanswered_days": 0}

# meetings
{"meetings_this_week": 0, "focus_hours_available": 0.0, "overdue_commitments": []}

# ops
{"open_roles": 0, "days_since_last_hire": 0, "critical_deadlines": []}
```

## Rules

- Never raise an exception — return an empty/zero snapshot on failure and log the error.
- Read all credentials from env vars. Fall back to seed data if credentials are absent.
- Snapshots are plain dicts — no custom classes that the agent prompt would need to decode.
- Keep field names consistent across runs — the agent's prompt is written against these names.
