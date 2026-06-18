from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import init_db, get_db, SessionLocal
from schema import Founder, Alert, Decision, IntegrationState
from coordinator import CoordinatorAgent, CoordinatorState, AlertSignal
from integrations.slack_adapter import SlackAdapter
from integrations.stripe_adapter import StripeAdapter
from integrations.email_adapter import EmailAdapter
from integrations.calendar_adapter import CalendarAdapter
from integrations.granola_adapter import GranolaAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="dCernment")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# Single coordinator instance; memory_db is injected per call (request/job scope).
coordinator_agent = CoordinatorAgent()

scheduler = BackgroundScheduler()


# ---------------------------------------------------------------------------
# Request models (so JSON bodies from the dashboard map correctly)
# ---------------------------------------------------------------------------


class DecideRequest(BaseModel):
    decision_text: str


class DelegateRequest(BaseModel):
    delegated_to: str


class DismissRequest(BaseModel):
    reason: Optional[str] = None


class AlertCreateRequest(BaseModel):
    signals: List[dict]


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
def start_scheduler():
    """Start the background scheduler that evaluates founders every 5 minutes."""
    if not scheduler.running:
        scheduler.add_job(
            evaluate_all_founders,
            IntervalTrigger(minutes=5),
            id="evaluate_founders",
            name="Collect signals across integrations and surface alerts",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        logger.info("✓ Integration evaluation scheduler started (every 5 min)")


@app.on_event("shutdown")
def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("✓ Scheduler shutdown")


# ---------------------------------------------------------------------------
# Core pipeline — shared by the scheduler AND the manual /alerts endpoint
# ---------------------------------------------------------------------------


def _jsonable(obj):
    """Recursively convert datetimes (and nested ones) to ISO strings so the
    value can be stored in a JSON column without a serialization error."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def process_signals(founder_id: str, signals: List[AlertSignal], db: Session) -> Optional[Alert]:
    """Run the coordinator over a set of signals and, if it clears the
    confidence/corroboration bar, persist an alert and push it to Slack.

    Returns the created Alert, or None if the coordinator suppressed it.
    Shared by the polling job and the manual POST /alerts endpoint so there is
    exactly one path that turns signals into alerts.
    """
    if not signals:
        return None

    coordinator_agent.memory_db = db
    graph = coordinator_agent.build_graph()

    state: CoordinatorState = {
        "founder_id": founder_id,
        "signals": signals,
        "identified_decision": None,
        "confidence_score": 0.0,
        "what_happened": "",
        "why_it_matters": "",
        "what_to_do_next": "",
        "next_decision": "",
        "similar_past_decision": None,
        "should_surface_alert": False,
    }

    final_state = graph.invoke(state)

    if not final_state["should_surface_alert"]:
        return None

    alert = Alert(
        founder_id=founder_id,
        alert_type=signals[0].type,
        title=f"Decision: {final_state['next_decision']}",
        what_happened=final_state["what_happened"],
        why_it_matters=final_state["why_it_matters"],
        what_to_do_next=final_state["what_to_do_next"],
        next_decision=final_state["next_decision"],
        signals=_jsonable([s.dict() for s in signals]),
        data_freshness=_get_freshness_indicators(founder_id, db),
        confidence_score=final_state["confidence_score"],
        precedent_context=final_state.get("similar_past_decision"),
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    founder = db.query(Founder).filter(Founder.id == founder_id).first()
    if founder:
        _post_to_slack(founder, alert)

    return alert


# ---------------------------------------------------------------------------
# Signal collection per integration (each isolated for graceful degradation)
# ---------------------------------------------------------------------------


def _collect_stripe_signals(founder_id: str, state: IntegrationState, db: Session) -> List[AlertSignal]:
    """Collect revenue-anomaly signals; compares MRR to the last-seen baseline."""
    signals: List[AlertSignal] = []
    baseline = (state.config or {}).get("last_mrr")
    adapter = StripeAdapter(state.access_token)
    metrics = adapter.get_revenue_metrics(baseline_mrr=baseline)

    if "error" in metrics:
        state.last_sync_status = "failed"
        state.last_error = metrics["error"]
    else:
        if metrics["mrr_change_pct"] < -5 or metrics["churn_count"] > 0:
            signals.append(AlertSignal(
                type="revenue_anomaly",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                data=metrics,
            ))
        # Persist new MRR baseline for the next evaluation.
        new_config = dict(state.config or {})
        new_config["last_mrr"] = metrics["mrr"]
        state.config = new_config
        state.last_sync_status = "success"
        state.last_error = None

    state.last_sync_at = datetime.utcnow()
    return signals


def _collect_email_signals(founder_id: str, state: IntegrationState, db: Session) -> List[AlertSignal]:
    """Collect churn + VIP-contact signals from the founder's inbox."""
    signals: List[AlertSignal] = []
    adapter = EmailAdapter(
        email_address=(state.config or {}).get("email"),
        imap_token=state.access_token,
    )

    for vip in adapter.scan_inbox_for_vips():
        signals.append(AlertSignal(
            type="investor_contact",
            confidence=0.9,
            timestamp=vip.get("timestamp", datetime.utcnow()),
            data=vip,
        ))
    for churn in adapter.scan_inbox_for_churn_signals():
        signals.append(AlertSignal(
            type="churn_signal",
            confidence=0.85,
            timestamp=churn.get("timestamp", datetime.utcnow()),
            data=churn,
        ))

    state.last_sync_at = datetime.utcnow()
    state.last_sync_status = "success"
    state.last_error = None
    return signals


def _collect_slack_signals(founder_id: str, state: IntegrationState, db: Session) -> List[AlertSignal]:
    """Collect team-conflict / escalation signals from Slack channels."""
    signals: List[AlertSignal] = []
    adapter = SlackAdapter(state.access_token)
    channels = (state.config or {}).get("channels")

    for esc in adapter.scan_channels_for_escalations(channels=channels):
        signals.append(AlertSignal(
            type="team_conflict",
            confidence=0.8 if esc.get("severity") == "high" else 0.7,
            timestamp=esc.get("timestamp", datetime.utcnow()),
            data=esc,
        ))

    state.last_sync_at = datetime.utcnow()
    state.last_sync_status = "success"
    state.last_error = None
    return signals


def _collect_granola_signals(founder_id: str, state: IntegrationState, db: Session) -> List[AlertSignal]:
    """Collect decision/action/risk signals from recent Granola meeting notes."""
    signals: List[AlertSignal] = []
    adapter = GranolaAdapter(
        state.access_token,
        (state.config or {}).get("base_url") or "https://public-api.granola.ai/v1",
    )
    for note in adapter.scan_recent_notes():
        signals.append(AlertSignal(
            type=note["kind"],
            confidence=0.8,
            timestamp=note["timestamp"],
            data=note,
        ))
    state.last_sync_at = datetime.utcnow()
    state.last_sync_status = "success"
    state.last_error = None
    return signals


_COLLECTORS = {
    "stripe": _collect_stripe_signals,
    "email": _collect_email_signals,
    "slack": _collect_slack_signals,
    "granola": _collect_granola_signals,
}


def evaluate_all_founders():
    """Scheduler entrypoint: for each founder, gather signals from every
    connected integration, then run them through the coordinator together.

    Gathering signals across sources before evaluating is what lets the
    coordinator enforce the doctrine's ">=2 corroborating signals" rule
    (revenue drop alone is held; revenue drop + churn surfaces). Each
    integration is collected in isolation so one failing source never blocks
    the others (doctrine: graceful degradation).
    """
    db = SessionLocal()
    try:
        for founder in db.query(Founder).all():
            collected: List[AlertSignal] = []
            states = db.query(IntegrationState).filter(
                IntegrationState.founder_id == founder.id
            ).all()

            for state in states:
                collector = _COLLECTORS.get(state.service)
                if not collector:
                    continue
                try:
                    collected.extend(collector(founder.id, state, db))
                except Exception as e:
                    state.last_sync_status = "failed"
                    state.last_error = str(e)
                    state.last_sync_at = datetime.utcnow()
                    logger.error(f"{state.service} collection failed for {founder.id}: {e}")

            db.commit()  # persist sync state + baselines regardless of alert outcome

            if collected:
                try:
                    alert = process_signals(founder.id, collected, db)
                    if alert:
                        logger.info(f"Alert surfaced for {founder.id}: {alert.id}")
                except Exception as e:
                    logger.error(f"process_signals failed for {founder.id}: {e}")
    except Exception as e:
        logger.error(f"evaluate_all_founders failed: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "scheduler_running": scheduler.running}


@app.post("/founders/{founder_id}/alerts")
def create_alert(founder_id: str, body: AlertCreateRequest, db: Session = Depends(get_db)):
    """Manually create an alert from incoming signals (e.g. webhooks/tests)."""
    founder = db.query(Founder).filter(Founder.id == founder_id).first()
    if not founder:
        raise HTTPException(status_code=404, detail="Founder not found")

    signals = [
        AlertSignal(
            type=s["type"],
            confidence=s.get("confidence", 0.8),
            timestamp=datetime.utcnow(),
            data=s.get("data", {}),
        )
        for s in body.signals
    ]

    try:
        alert = process_signals(founder_id, signals, db)
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not alert:
        return {"status": "suppressed", "reason": "insufficient_corroboration_or_confidence"}

    return {
        "alert_id": alert.id,
        "status": "surfaced",
        "title": alert.title,
        "next_decision": alert.next_decision,
    }


@app.get("/founders/{founder_id}/alerts")
def get_alerts(founder_id: str, status: str = "active", db: Session = Depends(get_db)):
    """Fetch alerts for a founder."""
    alerts = db.query(Alert).filter(
        Alert.founder_id == founder_id,
        Alert.status == status,
    ).order_by(Alert.triggered_at.desc()).limit(50).all()

    return [
        {
            "id": a.id,
            "type": a.alert_type,
            "title": a.title,
            "what_happened": a.what_happened,
            "why_it_matters": a.why_it_matters,
            "what_to_do_next": a.what_to_do_next,
            "next_decision": a.next_decision,
            "precedent_context": a.precedent_context,
            "data_freshness": a.data_freshness,
            "confidence": a.confidence_score,
            "triggered_at": a.triggered_at.isoformat(),
        }
        for a in alerts
    ]


@app.post("/founders/{founder_id}/alerts/{alert_id}/decide")
def mark_decision(founder_id: str, alert_id: str, body: DecideRequest, db: Session = Depends(get_db)):
    """Mark an alert as decided."""
    # Scope by founder_id so one founder cannot act on another's alert (tenant isolation).
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.founder_id == founder_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    decision = Decision(
        founder_id=alert.founder_id,
        alert_id=alert_id,
        decision_type="decide",
        decision_text=body.decision_text,
    )
    db.add(decision)
    alert.status = "decided"
    db.commit()
    db.refresh(decision)
    return {"decision_id": decision.id, "status": "recorded"}


@app.post("/founders/{founder_id}/alerts/{alert_id}/delegate")
def delegate_decision(founder_id: str, alert_id: str, body: DelegateRequest, db: Session = Depends(get_db)):
    """Mark an alert as delegated."""
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.founder_id == founder_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    decision = Decision(
        founder_id=alert.founder_id,
        alert_id=alert_id,
        decision_type="delegate",
        decision_text=f"Delegated to {body.delegated_to}",
        delegated_to=body.delegated_to,
    )
    db.add(decision)
    alert.status = "delegated"
    db.commit()
    db.refresh(decision)
    return {"decision_id": decision.id, "status": "delegated"}


@app.post("/founders/{founder_id}/alerts/{alert_id}/dismiss")
def dismiss_alert(founder_id: str, alert_id: str, body: DismissRequest, db: Session = Depends(get_db)):
    """Mark an alert as dismissed."""
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.founder_id == founder_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    decision = Decision(
        founder_id=alert.founder_id,
        alert_id=alert_id,
        decision_type="dismiss",
        decision_text=f"Dismissed: {body.reason or 'false alarm'}",
    )
    db.add(decision)
    alert.status = "dismissed"
    db.commit()
    db.refresh(decision)
    return {"decision_id": decision.id, "status": "dismissed"}


@app.get("/founders/{founder_id}/decisions")
def get_decision_history(founder_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Fetch decision history for a founder."""
    decisions = db.query(Decision).filter(
        Decision.founder_id == founder_id
    ).order_by(Decision.made_at.desc()).limit(limit).all()

    return [
        {
            "id": d.id,
            "type": d.decision_type,
            "decision_text": d.decision_text,
            "made_at": d.made_at.isoformat(),
            "outcome": d.outcome,
            "impact": d.impact,
        }
        for d in decisions
    ]


@app.post("/slack/actions")
def slack_action(payload: dict, db: Session = Depends(get_db)):
    """Handle Slack button actions (Decide/Delegate/Dismiss from a Slack alert)."""
    try:
        action = payload.get("actions", [{}])[0]
        action_type = action.get("action_id", "").split("_")[0]
        alert_id = action.get("value", "").split("_")[-1]

        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return {"ok": False, "error": "alert_not_found"}

        if action_type == "decide":
            decision = Decision(
                founder_id=alert.founder_id, alert_id=alert_id,
                decision_type="decide", decision_text="Decided from Slack",
            )
            alert.status = "decided"
        elif action_type == "delegate":
            decision = Decision(
                founder_id=alert.founder_id, alert_id=alert_id,
                decision_type="delegate", decision_text="Delegated from Slack",
            )
            alert.status = "delegated"
        elif action_type == "dismiss":
            decision = Decision(
                founder_id=alert.founder_id, alert_id=alert_id,
                decision_type="dismiss", decision_text="Dismissed from Slack",
            )
            alert.status = "dismissed"
        else:
            return {"ok": False, "error": "unknown_action"}

        db.add(decision)
        db.commit()
        return {"ok": True}

    except Exception as e:
        logger.error(f"Slack action error: {e}")
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_freshness_indicators(founder_id: str, db: Session) -> dict:
    """Compute real data freshness per integration from integration_state."""
    freshness = {}
    integrations = db.query(IntegrationState).filter(
        IntegrationState.founder_id == founder_id
    ).all()

    for integration in integrations:
        if integration.last_sync_at:
            age_minutes = int((datetime.utcnow() - integration.last_sync_at).total_seconds() / 60)
            if integration.last_sync_status == "failed":
                freshness[integration.service] = f"{age_minutes} min old ❌ (sync failed)"
            elif age_minutes == 0:
                freshness[integration.service] = "real-time ✓"
            elif age_minutes <= 5:
                freshness[integration.service] = f"{age_minutes} min old ✓"
            elif age_minutes <= 30:
                freshness[integration.service] = f"{age_minutes} min old ⚠️"
            else:
                freshness[integration.service] = f"{age_minutes} min old ❌ (stale)"
        else:
            freshness[integration.service] = "never synced ❌"

    return freshness


def _post_to_slack(founder: Founder, alert: Alert) -> bool:
    """Post an alert to the founder's Slack DM/channel, if configured."""
    if not founder.slack_user_id:
        return False
    try:
        slack = SlackAdapter(os.getenv("SLACK_BOT_TOKEN"))
        return slack.post_alert(
            channel=founder.slack_user_id,
            alert_payload={
                "id": alert.id,
                "title": alert.title,
                "what_happened": alert.what_happened,
                "why_it_matters": alert.why_it_matters,
                "what_to_do_next": alert.what_to_do_next,
            },
        )
    except Exception as e:
        logger.error(f"Failed to post to Slack: {e}")
        return False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
