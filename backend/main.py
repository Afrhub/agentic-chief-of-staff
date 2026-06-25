from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import logging
import os
import hmac
import hashlib
import time
import threading
import json
import base64
import socket
import ipaddress
import httpx
from urllib.parse import parse_qsl
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import init_db, get_db, SessionLocal
from schema import Founder, Alert, Decision, IntegrationState, Draft, Metric, MetricReading
from auth import hash_password, verify_password, new_token
from packs import get_pack, list_packs
from coordinator import CoordinatorAgent, CoordinatorState, AlertSignal
from integrations.slack_adapter import SlackAdapter
from integrations.stripe_adapter import StripeAdapter
from integrations.email_adapter import EmailAdapter
from integrations.calendar_adapter import CalendarAdapter
from integrations.granola_adapter import GranolaAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="dCern")


async def _require_session(request: Request, call_next):
    """Gate every /founders/{id}/* route: the bearer token must match that
    founder's session_token. One chokepoint so a new route can't forget to auth.
    Demo mode is frontend-only (canned data, never calls these), so it's unaffected."""
    path = request.url.path
    if request.method != "OPTIONS" and path.startswith("/founders/"):
        parts = path.split("/")
        founder_id = parts[2] if len(parts) > 2 else ""
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        db = SessionLocal()
        try:
            f = db.query(Founder).filter(Founder.id == founder_id).first()
            ok = bool(f and f.session_token and token and hmac.compare_digest(f.session_token, token))
        finally:
            db.close()
        if not ok:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


# --- Rate limiting (in-process sliding window) ---------------------------------
# ponytail: per-process counters — fine for single-instance Render. Multi-instance
# needs shared state (e.g. Redis); per-worker counters don't sync. Auth paths get a
# tight bucket (brute-force guard), everything else a generous one.
_RL_LOCK = threading.Lock()
_RL_HITS: dict = {}


def _rl_rule(path: str):
    """(limit, window_seconds, bucket) per path class."""
    if path.startswith("/auth/"):
        return 12, 300, "auth"                          # brute-force guard
    if path.startswith("/slack/") or path.startswith("/whatsapp/"):
        return 90, 60, "hook"                           # inbound webhooks
    if "/agents/" in path:
        return 20, 60, "agents"                         # EXPENSIVE — managed-agent inference $$
    return 240, 60, "gen"


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")  # Render/proxies set this
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


async def _rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    limit, window, bucket = _rl_rule(path)
    key = f"{_client_ip(request)}:{bucket}"
    now = time.time()
    with _RL_LOCK:
        hits = [t for t in _RL_HITS.get(key, []) if t > now - window]
        if len(hits) >= limit:
            _RL_HITS[key] = hits
            return JSONResponse(
                {"detail": "Too many requests — slow down."},
                status_code=429, headers={"Retry-After": str(int(hits[0] + window - now) + 1)},
            )
        hits.append(now)
        _RL_HITS[key] = hits
    return await call_next(request)


_SEC_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",  # JSON API
}


async def _security_headers(request: Request, call_next):
    resp = await call_next(request)
    for k, v in _SEC_HEADERS.items():
        resp.headers.setdefault(k, v)
    for leak in ("server", "x-powered-by"):
        if leak in resp.headers:
            del resp.headers[leak]
    return resp


# Middleware order: last-added runs first (outermost). Outer→inner we want:
# security-headers → CORS → rate-limit → session gate → route. So 401/429 responses
# still carry CORS + security headers, and rate-limiting throttles even unauth'd hits.
_ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "DCERN_ALLOWED_ORIGINS",
    "https://dcern.netlify.app,https://ai-c-o-s.netlify.app,http://localhost:3000,http://localhost:4173",
).split(",") if o.strip()]

app.add_middleware(BaseHTTPMiddleware, dispatch=_require_session)   # inner
app.add_middleware(BaseHTTPMiddleware, dispatch=_rate_limit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,          # explicit allowlist (was "*")
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=_security_headers)  # outermost

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


class DeferRequest(BaseModel):
    waiting_on: Optional[str] = None  # the person/info you're blocked on
    until: Optional[str] = None       # ISO date — auto-resurfaces when it passes
    reason: Optional[str] = None


class MetricCreate(BaseModel):
    name: str
    owner: Optional[str] = None
    target: Optional[float] = None
    unit: Optional[str] = None
    direction: str = "up"             # up = higher is better, down = lower


class ReadingCreate(BaseModel):
    value: float
    period: Optional[str] = None


class VerifyRequest(BaseModel):
    impact: str                       # positive | neutral | negative
    note: Optional[str] = None


class AlertCreateRequest(BaseModel):
    signals: List[dict]


class ChatRequest(BaseModel):
    message: str = Field(max_length=8000)
    history: Optional[List[dict]] = None  # [{role, content}], optional


class ConnectRequest(BaseModel):
    access_token: str = Field(max_length=2000)
    config: Optional[dict] = None


class DraftRequest(BaseModel):
    instruction: str = Field(max_length=8000)
    channel: str = Field(default="email", max_length=20)   # email | slack
    recipient: Optional[str] = Field(default=None, max_length=320)


class FounderRequest(BaseModel):
    email: Optional[str] = None
    slack_user_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    pack: Optional[str] = None


class AuthRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)  # min enforced in /auth/signup; max guards PBKDF2 DoS
    pack: Optional[str] = Field(default=None, max_length=40)  # vertical pack id chosen at signup


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
    # Industry framing: load the founder's vertical pack so the coordinator
    # synthesizes the alert in that industry's terms (SaaS vs e-commerce vs …).
    founder = db.query(Founder).filter(Founder.id == founder_id).first()
    coordinator_agent.active_pack = get_pack(getattr(founder, "pack", None) if founder else None)
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
        "options": [],
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
        options=final_state.get("options") or [],
        signals=_jsonable([s.dict() for s in signals]),
        data_freshness=_get_freshness_indicators(founder_id, db),
        confidence_score=final_state["confidence_score"],
        precedent_context=final_state.get("similar_past_decision"),
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    if founder:  # fetched above for the pack lookup
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


def _safe_external_url(url: str) -> str:
    """SSRF guard for user-supplied URLs fetched server-side. Rejects non-HTTP(S)
    and hosts that resolve to private / loopback / link-local / reserved IPs (incl.
    cloud metadata 169.254.169.254). Raises ValueError if unsafe.
    ponytail: resolve-then-check leaves a small DNS-rebinding window — fine as a
    first layer; a vetted egress proxy would close it."""
    from urllib.parse import urlparse
    p = urlparse(url or "")
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("url must be http(s) with a host")
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(p.hostname, None)}
    except Exception:
        raise ValueError("host does not resolve")
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"host resolves to a blocked address ({ip})")
    return url


def _collect_granola_signals(founder_id: str, state: IntegrationState, db: Session) -> List[AlertSignal]:
    """Collect decision/action/risk signals from recent Granola meeting notes."""
    signals: List[AlertSignal] = []
    base_url = (state.config or {}).get("base_url") or "https://public-api.granola.ai/v1"
    try:
        base_url = _safe_external_url(base_url)
    except ValueError as e:
        logger.error(f"granola base_url blocked (SSRF guard): {e}")
        return []
    adapter = GranolaAdapter(state.access_token, base_url)
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


def reactivate_due_deferrals(db: Session) -> int:
    """Flip deferred alerts whose defer window has elapsed back to active so they
    re-surface (e.g. the away person is back). Runs each scheduler tick."""
    now = datetime.utcnow()
    due = db.query(Alert).filter(
        Alert.status == "deferred",
        Alert.deferred_until.isnot(None),
        Alert.deferred_until <= now,
    ).all()
    for a in due:
        a.status = "active"
        a.deferred_until = None
    if due:
        db.commit()
        logger.info(f"Reactivated {len(due)} deferred alert(s) whose window elapsed")
    return len(due)


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
        reactivate_due_deferrals(db)  # bring back any deferrals whose window elapsed
        for founder in db.query(Founder).all():
            collected: List[AlertSignal] = []
            states = db.query(IntegrationState).filter(
                IntegrationState.founder_id == founder.id
            ).all()

            for state in states:
                cfg = state.config or {}
                # MCP-sourced signal: any connected integration whose config is
                # kind="mcp" is pulled via the MCP adapter (config not adapter code).
                if cfg.get("kind") == "mcp":
                    try:
                        from integrations.mcp_adapter import collect as mcp_collect
                        collected.extend(mcp_collect(
                            _safe_external_url(cfg["mcp_server"]), state.access_token, cfg["tool"],
                            cfg.get("maps_to", "external_signal"),
                            cfg.get("confidence", 0.8), cfg.get("args"),
                        ))
                        state.last_sync_status = "success"
                        state.last_error = None
                    except Exception as e:
                        state.last_sync_status = "failed"
                        state.last_error = str(e)
                        logger.error(f"mcp collection failed for {founder.id}: {e}")
                    state.last_sync_at = datetime.utcnow()
                    continue

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


@app.post("/auth/signup")
def signup(body: AuthRequest, db: Session = Depends(get_db)):
    """Create an account → returns {founder_id, token}. Public by design."""
    email = (body.email or "").strip().lower()
    if "@" not in email or len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Valid email and password (min 8 chars) required")
    if db.query(Founder).filter(Founder.email == email).first():
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    token = new_token()
    pack_id = get_pack(body.pack).get("id")  # validated → real pack id or default
    f = Founder(
        email=email, password_hash=hash_password(body.password),
        session_token=token, pack=pack_id,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    _calibrate(f.id, pack_id, db)  # onboarding: seed the scorecard targets from the pack
    return {"founder_id": f.id, "token": token, "pack": pack_id}


@app.post("/auth/login")
def login(body: AuthRequest, db: Session = Depends(get_db)):
    """Verify credentials → rotate + return a fresh session token."""
    email = (body.email or "").strip().lower()
    f = db.query(Founder).filter(Founder.email == email).first()
    if not f or not f.password_hash or not verify_password(body.password, f.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = new_token()
    f.session_token = token  # rotate on each login (invalidates the prior token)
    db.commit()
    return {"founder_id": f.id, "token": token}


@app.get("/packs")
def get_packs():
    """Available vertical packs (industry framings) — drives the onboarding picker."""
    return list_packs()


@app.get("/agents/fleet")
def agents_fleet():
    """The dCern agent fleet: human identities + each axis agent's model and live
    data source. Product metadata (no founder data) — drives the dashboard's team
    view. The personas here are also prepended to the agents at creation time."""
    from agents.identities import fleet_meta, COORDINATOR
    return {"coordinator": COORDINATOR, "agents": fleet_meta()}


@app.get("/health")
def health():
    return {"status": "ok", "scheduler_running": scheduler.running}


@app.post("/founders/{founder_id}")
def upsert_founder(founder_id: str, body: FounderRequest, db: Session = Depends(get_db)):
    """Update your own founder profile (email / slack / whatsapp). Auth-gated by
    the session middleware; account creation now happens via /auth/signup."""
    f = db.query(Founder).filter(Founder.id == founder_id).first()
    if not f:
        f = Founder(id=founder_id, email=body.email or f"{founder_id}@demo.test")
        db.add(f)
    elif body.email:
        f.email = body.email
    if body.slack_user_id is not None:
        f.slack_user_id = body.slack_user_id
    if body.whatsapp_number is not None:
        f.whatsapp_number = body.whatsapp_number
    if body.pack is not None:
        f.pack = get_pack(body.pack).get("id")  # validated
    db.commit()
    return {"id": founder_id, "status": "ok"}


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
            "options": a.options or [],
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


@app.post("/founders/{founder_id}/alerts/{alert_id}/defer")
def defer_alert(founder_id: str, alert_id: str, body: DeferRequest, db: Session = Depends(get_db)):
    """Park an alert until missing info arrives (e.g. a person who's away). It
    leaves the active feed and auto-resurfaces once `until` passes; with no
    `until` it stays parked until a new signal re-raises it."""
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.founder_id == founder_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    until = None
    if body.until:
        try:
            until = datetime.fromisoformat(body.until.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            until = None  # unparseable date → park indefinitely rather than fail

    waiting_on = body.waiting_on or "more info"
    note = f"Deferred — waiting on {waiting_on}" + (f" until {until.date()}" if until else "")
    decision = Decision(
        founder_id=alert.founder_id,
        alert_id=alert_id,
        decision_type="defer",
        decision_text=note,
        rationale=body.reason,
    )
    db.add(decision)
    alert.status = "deferred"
    alert.deferred_until = until
    db.commit()
    db.refresh(decision)
    return {"decision_id": decision.id, "status": "deferred", "until": until.isoformat() if until else None}


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


# ---------------------------------------------------------------------------
# Precision Scorecard — metrics with an owner + target, measured over time.
# (Martell: Targets & Actuals + Assign Ownership + Weekly Measurement.)
# ---------------------------------------------------------------------------


def _on_track(latest, target, direction) -> Optional[bool]:
    if latest is None or target is None:
        return None
    return latest <= target if direction == "down" else latest >= target


@app.get("/founders/{founder_id}/scorecard")
def get_scorecard(founder_id: str, db: Session = Depends(get_db)):
    """Each metric with its target, latest actual, on/off-track, and a recent
    series for a sparkline."""
    out = []
    for m in db.query(Metric).filter(Metric.founder_id == founder_id).order_by(Metric.created_at).all():
        readings = db.query(MetricReading).filter(
            MetricReading.metric_id == m.id
        ).order_by(MetricReading.recorded_at).all()
        series = [r.value for r in readings]
        latest = series[-1] if series else None
        out.append({
            "id": m.id, "name": m.name, "owner": m.owner, "target": m.target,
            "unit": m.unit, "direction": m.direction, "latest": latest,
            "on_track": _on_track(latest, m.target, m.direction), "series": series[-12:],
        })
    return out


@app.post("/founders/{founder_id}/scorecard/metrics")
def create_metric(founder_id: str, body: MetricCreate, db: Session = Depends(get_db)):
    m = Metric(
        founder_id=founder_id, name=body.name, owner=body.owner,
        target=body.target, unit=body.unit, direction=body.direction or "up",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"metric_id": m.id, "name": m.name}


def _calibrate(founder_id: str, pack_id: str, db: Session) -> list:
    """Onboarding calibration: seed the founder's scorecard with the pack's default
    metrics + targets (idempotent by name) — the per-axis 'business parameters' the
    agents judge against. A connected data source can baseline these from history later."""
    existing = {m.name for m in db.query(Metric).filter(Metric.founder_id == founder_id).all()}
    created = []
    for spec in get_pack(pack_id).get("metrics", []):
        if not spec.get("name") or spec["name"] in existing:
            continue
        db.add(Metric(
            founder_id=founder_id, name=spec["name"], owner=spec.get("owner"),
            target=spec.get("target"), unit=spec.get("unit"),
            direction=spec.get("direction", "up"),
        ))
        created.append(spec["name"])
    if created:
        db.commit()
    return created


@app.post("/founders/{founder_id}/scorecard/calibrate")
def calibrate_scorecard(founder_id: str, reset: bool = False, db: Session = Depends(get_db)):
    """Re-run onboarding calibration: set each axis's targets from the founder's
    pack. Idempotent — only adds metrics not already present. With reset=true
    (industry re-pick), first drops the founder's *untouched* default metrics (no
    readings logged) so the new pack's targets replace them; metrics the founder
    has actually used (have readings) are kept."""
    f = db.query(Founder).filter(Founder.id == founder_id).first()
    pack_id = (f.pack if f else None) or get_pack(None).get("id")
    if reset:
        for m in db.query(Metric).filter(Metric.founder_id == founder_id).all():
            used = db.query(MetricReading).filter(MetricReading.metric_id == m.id).first()
            if not used:
                db.delete(m)
        db.commit()
    created = _calibrate(founder_id, pack_id, db)
    return {"pack": pack_id, "created": created}


@app.post("/founders/{founder_id}/scorecard/metrics/{metric_id}/readings")
def add_reading(founder_id: str, metric_id: str, body: ReadingCreate, db: Session = Depends(get_db)):
    m = db.query(Metric).filter(Metric.id == metric_id, Metric.founder_id == founder_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Metric not found")
    r = MetricReading(metric_id=metric_id, founder_id=founder_id, value=body.value, period=body.period)
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"reading_id": r.id, "value": r.value}


@app.delete("/founders/{founder_id}/scorecard/metrics/{metric_id}")
def delete_metric(founder_id: str, metric_id: str, db: Session = Depends(get_db)):
    m = db.query(Metric).filter(Metric.id == metric_id, Metric.founder_id == founder_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Metric not found")
    db.query(MetricReading).filter(MetricReading.metric_id == metric_id).delete()
    db.delete(m)
    db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Kanban board — the decision lifecycle as columns.
# New -> Decision made / Delegated / Deferred / Dismissed -> Done (verified).
# "Done" = a decided/delegated alert whose outcome has been verified (impact set).
# ---------------------------------------------------------------------------


@app.get("/founders/{founder_id}/board")
def get_board(founder_id: str, db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter(
        Alert.founder_id == founder_id
    ).order_by(Alert.triggered_at.desc()).limit(200).all()

    # Latest decision per alert (for the resolution note + verified impact).
    latest = {}
    for d in db.query(Decision).filter(
        Decision.founder_id == founder_id
    ).order_by(Decision.made_at.desc()).all():
        if d.alert_id and d.alert_id not in latest:
            latest[d.alert_id] = d

    cols = {"new": [], "decided": [], "delegated": [], "deferred": [], "dismissed": [], "done": []}
    for a in alerts:
        d = latest.get(a.id)
        card = {
            "id": a.id,
            "type": a.alert_type,
            "title": (a.title or "").replace("Decision: ", ""),
            "next_decision": a.next_decision,
            "confidence": a.confidence_score,
            "triggered_at": a.triggered_at.isoformat(),
            "note": d.decision_text if d else None,
            "impact": d.impact if d else None,
        }
        if a.status == "active":
            cols["new"].append(card)
        elif a.status == "deferred":
            cols["deferred"].append(card)
        elif a.status == "dismissed":
            cols["dismissed"].append(card)
        elif a.status in ("decided", "delegated"):
            cols["done" if (d and d.impact) else a.status].append(card)
    return cols


@app.post("/founders/{founder_id}/alerts/{alert_id}/verify")
def verify_alert(founder_id: str, alert_id: str, body: VerifyRequest, db: Session = Depends(get_db)):
    """Post-decision check: record whether the call was right (the 'Done' move)."""
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.founder_id == founder_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    d = db.query(Decision).filter(
        Decision.alert_id == alert_id, Decision.founder_id == founder_id
    ).order_by(Decision.made_at.desc()).first()
    if not d:
        raise HTTPException(status_code=400, detail="Decide or delegate this alert before verifying its outcome")
    d.impact = body.impact
    d.outcome = body.note
    d.outcome_at = datetime.utcnow()
    db.commit()
    return {"status": "verified", "impact": d.impact}


# ---------------------------------------------------------------------------
# Phase 1 — per-axis Managed Agent (Money). Safe by default: no-ops until the
# agent + environment IDs are configured. See backend/agents/README.md.
# ---------------------------------------------------------------------------


_AXIS_AGENTS = {
    "money": "MONEY_AGENT_ID",
    "customers": "CUSTOMERS_AGENT_ID",
    "comms": "COMMS_AGENT_ID",
    "meetings": "MEETINGS_AGENT_ID",
    "ops": "OPS_AGENT_ID",
}


def _axis_context(founder_id: str, axis: str, db: Session) -> str:
    """Snapshot of the founder's state for an axis agent to analyze (scorecard +
    recent decisions). Phase 3 gives each agent its own live MCP data source."""
    lines = [f"Axis: {axis}. Decide if there is a decision-worthy {axis} signal right now.", "Scorecard:"]
    for m in db.query(Metric).filter(Metric.founder_id == founder_id).all():
        last = db.query(MetricReading).filter(
            MetricReading.metric_id == m.id
        ).order_by(MetricReading.recorded_at.desc()).first()
        lines.append(f"- {m.name}: {last.value if last else 'n/a'} (target {m.target}{m.unit or ''}, better {m.direction})")
    recent = db.query(Alert).filter(
        Alert.founder_id == founder_id
    ).order_by(Alert.triggered_at.desc()).limit(5).all()
    if recent:
        lines.append("Recent decisions: " + "; ".join((a.title or "")[:80] for a in recent))
    return "\n".join(lines)


def _run_axis(founder_id: str, axis: str, db: Session):
    """Run one axis agent → its finding dict, or None if that axis isn't configured."""
    agent_id = os.getenv(_AXIS_AGENTS.get(axis, ""))
    if not (agent_id and os.getenv("DCERN_ENV_ID") and os.getenv("ANTHROPIC_API_KEY")):
        return None
    from agents.managed_agents import run_axis_agent
    vault = os.getenv("DCERN_VAULT_ID")  # credentials for the agent's MCP tools
    return run_axis_agent(
        agent_id, os.environ["DCERN_ENV_ID"], _axis_context(founder_id, axis, db),
        vault_ids=[vault] if vault else None,
    )


@app.post("/founders/{founder_id}/agents/{axis}/run")
def run_axis_endpoint(founder_id: str, axis: str, db: Session = Depends(get_db)):
    """Run a single axis agent and ingest its finding. A lone signal is correctly
    suppressed — surfacing needs ≥2 axes; use POST /agents/run for the fleet."""
    if axis not in _AXIS_AGENTS:
        raise HTTPException(status_code=404, detail=f"Unknown axis '{axis}'")
    try:
        finding = _run_axis(founder_id, axis, db)
    except Exception as e:
        logger.error(f"{axis} agent run failed: {e}")
        raise HTTPException(status_code=502, detail=f"{axis} agent run failed")
    if finding is None:
        return {"status": "not_configured",
                "detail": f"Set {_AXIS_AGENTS[axis]}, DCERN_ENV_ID and ANTHROPIC_API_KEY — see backend/agents/README.md"}
    result = {"axis": axis, "finding": finding}
    if finding.get("has_signal"):
        alert = process_signals(founder_id, [AlertSignal(
            type=finding.get("type", axis), confidence=float(finding.get("confidence", 0.8)),
            timestamp=datetime.utcnow(), data=finding.get("data", {}))], db)
        result["alert_status"] = "surfaced" if alert else "suppressed (one signal — corroboration needs ≥2 axes)"
    return result


@app.post("/founders/{founder_id}/agents/run")
def run_agent_fleet(founder_id: str, db: Session = Depends(get_db)):
    """Run every configured axis agent, then corroborate their findings via the
    ≥2-distinct rule — the fleet path that produces surfaced alerts."""
    configured = [ax for ax in _AXIS_AGENTS if os.getenv(_AXIS_AGENTS[ax])]
    if not (configured and os.getenv("DCERN_ENV_ID") and os.getenv("ANTHROPIC_API_KEY")):
        return {"status": "not_configured",
                "detail": "No axis agents configured — see backend/agents/README.md"}

    findings, signals, errors = [], [], {}
    for axis in configured:
        try:
            f = _run_axis(founder_id, axis, db)
        except Exception as e:
            errors[axis] = str(e)[:300]
            logger.error(f"{axis} agent run failed: {e}")
            continue
        if f is None:
            continue
        findings.append({"axis": axis, **f})
        if f.get("has_signal"):
            signals.append(AlertSignal(
                type=f.get("type", axis), confidence=float(f.get("confidence", 0.8)),
                timestamp=datetime.utcnow(), data=f.get("data", {})))

    if not findings:
        # Configured, but every run errored — surface WHY (don't mislabel as unconfigured).
        return {"status": "no_findings", "configured": configured, "errors": errors,
                "detail": "Axis agents are configured but none returned a finding — see "
                          "'errors' (commonly low Anthropic balance or rate limits)."}

    alert = process_signals(founder_id, signals, db) if signals else None
    return {
        "findings": findings, "signals": len(signals), "errors": errors,
        "alert_status": "surfaced" if alert else "suppressed",
        "alert_id": alert.id if alert else None,
    }


@app.post("/founders/{founder_id}/agents/deployments/sync")
def sync_deployment(founder_id: str, db: Session = Depends(get_db)):
    """Ingest the latest scheduled-deployment run's finding (the 24/7 path: an
    Anthropic cron fires the coordinator, this pulls its result into dCern).
    No-ops until DCERN_DEPLOYMENT_ID is set — see backend/agents/PROD.md."""
    dep = os.getenv("DCERN_DEPLOYMENT_ID")
    if not (dep and os.getenv("ANTHROPIC_API_KEY")):
        return {"status": "not_configured",
                "detail": "Set DCERN_DEPLOYMENT_ID and ANTHROPIC_API_KEY — see backend/agents/PROD.md"}
    try:
        from agents.managed_agents import latest_deployment_finding
        finding = latest_deployment_finding(dep)
    except Exception as e:
        logger.error(f"deployment sync failed: {e}")
        raise HTTPException(status_code=502, detail="Deployment sync failed")
    result = {"finding": finding}
    if finding.get("has_signal"):
        alert = process_signals(founder_id, [AlertSignal(
            type=finding.get("type", "revenue_anomaly"), confidence=float(finding.get("confidence", 0.8)),
            timestamp=datetime.utcnow(), data=finding.get("data", {}))], db)
        result["alert_status"] = "surfaced" if alert else "suppressed"
    return result


@app.get("/founders/{founder_id}/integrations")
def list_integrations(founder_id: str, db: Session = Depends(get_db)):
    """List connected integrations + sync status (for the Connect UI)."""
    rows = db.query(IntegrationState).filter(
        IntegrationState.founder_id == founder_id
    ).all()
    return [
        {
            "service": r.service,
            "status": r.last_sync_status,
            "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None,
            "error": r.last_error,
        }
        for r in rows
    ]


@app.post("/founders/{founder_id}/integrations/{service}")
def connect_integration(founder_id: str, service: str, body: ConnectRequest, db: Session = Depends(get_db)):
    """Connect (or update) an integration by storing its API key. Upsert by (founder, service)."""
    founder = db.query(Founder).filter(Founder.id == founder_id).first()
    if not founder:
        raise HTTPException(status_code=404, detail="Founder not found")

    row = db.query(IntegrationState).filter(
        IntegrationState.founder_id == founder_id,
        IntegrationState.service == service,
    ).first()
    if row:
        row.access_token = body.access_token
        row.config = body.config or row.config or {}
    else:
        row = IntegrationState(
            founder_id=founder_id, service=service,
            access_token=body.access_token, config=body.config or {},
        )
        db.add(row)
    db.commit()
    return {"service": service, "status": "connected"}


def _vault_path_for(founder_id: str, db: Session) -> str:
    """Resolve the founder's Obsidian vault: their connected path, else an env
    override (self-hosted), else the bundled sample vault (so the hosted demo
    still has a Digital Brain to read)."""
    row = db.query(IntegrationState).filter(
        IntegrationState.founder_id == founder_id,
        IntegrationState.service == "obsidian",
    ).first()
    if row and (row.config or {}).get("vault_path"):
        return row.config["vault_path"]
    return os.getenv("OBSIDIAN_VAULT_PATH") or os.path.join(os.path.dirname(__file__), "sample_vault")


def _recall_brain(founder_id: str, query: str, db: Session, k: int = 3) -> list:
    """Top-k Obsidian notes relevant to `query` (the Digital Brain), as snippets."""
    path = _vault_path_for(founder_id, db)
    if not path or not os.path.isdir(path):
        return []
    try:
        from integrations.obsidian_adapter import read_vault, rank_notes
        notes = rank_notes(read_vault(path), query, k=k)
        return [f"{n['title']}: {n['text'][:220].strip()}" for n in notes]
    except Exception as e:
        logger.warning(f"brain recall failed: {e}")
        return []


@app.get("/founders/{founder_id}/brain")
def get_brain(founder_id: str, db: Session = Depends(get_db)):
    """Digital Brain status: which vault, how many notes, sample titles."""
    from integrations.obsidian_adapter import read_vault
    path = _vault_path_for(founder_id, db)
    notes = read_vault(path) if path and os.path.isdir(path) else []
    return {"vault_path": path, "notes": len(notes), "titles": [n["title"] for n in notes[:20]]}


def _chief_of_staff_reply(founder_id: str, message: str, db: Session) -> str:
    """The chief-of-staff brain. Lazy v1: stuff recent alerts + decisions as
    context and answer (read-only, recommend-don't-execute). Shared by the web
    /chat endpoint and the Slack bot so there's one brain.
    ponytail: no tool-calling/draft-send yet — add when the agent must act."""
    alerts = db.query(Alert).filter(
        Alert.founder_id == founder_id, Alert.status == "active"
    ).order_by(Alert.triggered_at.desc()).limit(10).all()
    decisions = db.query(Decision).filter(
        Decision.founder_id == founder_id
    ).order_by(Decision.made_at.desc()).limit(10).all()

    context = "ACTIVE ALERTS:\n" + ("\n".join(
        f"- [{a.alert_type}] {a.title}: {a.what_happened}" for a in alerts
    ) or "(none)")
    context += "\n\nRECENT DECISIONS:\n" + ("\n".join(
        f"- {d.decision_type}: {d.decision_text}" for d in decisions
    ) or "(none)")

    # Digital Brain: ground the answer in the founder's own Obsidian notes.
    notes = _recall_brain(founder_id, message, db)
    if notes:
        context += "\n\nFROM YOUR NOTES (Obsidian):\n" + "\n".join(f"- {n}" for n in notes)

    prompt = (
        "You are the founder's AI Chief of Staff. Answer concisely and like a "
        "thought partner. Recommend; never claim to have sent or executed "
        "anything — drafts require the founder's approval.\n\n"
        f"{context}\n\nFounder: {message}\nChief of Staff:"
    )
    coordinator_agent.memory_db = db
    return coordinator_agent._call_with_fallback(prompt)


_DRAFT_INTENT = ("draft", "write a", "write an", "reply to", "compose", "send a message", "send an email")


def _wants_draft(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in _DRAFT_INTENT)  # ponytail: keyword intent; LLM-classify later


@app.post("/founders/{founder_id}/chat")
def chat(founder_id: str, body: ChatRequest, db: Session = Depends(get_db)):
    """Conversational chief of staff (web). If the founder asks for a draft, the
    chat generates one (pending approval in Drafts) instead of just replying."""
    founder = db.query(Founder).filter(Founder.id == founder_id).first()
    if not founder:
        raise HTTPException(status_code=404, detail="Founder not found")
    try:
        if _wants_draft(body.message):
            channel = "slack" if "slack" in body.message.lower() else "email"
            draft = _persist_draft(founder_id, body.message, channel, None, db)
            return {
                "reply": f"✍️ I drafted a {channel} message — review and approve it in **Drafts**.",
                "draft_id": draft.id,
            }
        return {"reply": _chief_of_staff_reply(founder_id, body.message, db)}
    except Exception as e:
        logger.error(f"chat failed: {e}")
        raise HTTPException(status_code=503, detail="assistant unavailable")


def _generate_draft(founder_id: str, instruction: str, channel: str, db: Session) -> dict:
    """Ask the LLM to write a draft message. Returns {subject, body}."""
    prompt = (
        f"You are the founder's chief of staff. Draft a {channel} message for the "
        f"request below. Concise, professional, ready to send. Return EXACTLY:\n"
        f"SUBJECT: <one line; 'N/A' for slack>\nBODY: <message>\n\n"
        f"Request: {instruction}"
    )
    coordinator_agent.memory_db = db
    raw = coordinator_agent._call_with_fallback(prompt)

    subject, body, section = "", "", None
    for line in raw.splitlines():
        if line.startswith("SUBJECT:"):
            section = "s"; subject = line[8:].strip()
        elif line.startswith("BODY:"):
            section = "b"; body = line[5:].strip()
        elif section == "b":
            body += "\n" + line
    return {"subject": subject, "body": body.strip() or raw.strip()}


def _draft_dict(d: Draft) -> dict:
    return {
        "id": d.id, "channel": d.channel, "recipient": d.recipient,
        "subject": d.subject, "body": d.body, "status": d.status,
        "instruction": d.instruction, "created_at": d.created_at.isoformat(),
    }


def _persist_draft(founder_id: str, instruction: str, channel: str, recipient, db: Session) -> Draft:
    """Generate + save a pending draft. Shared by the /drafts endpoint and chat."""
    gen = _generate_draft(founder_id, instruction, channel, db)
    draft = Draft(
        founder_id=founder_id, channel=channel, recipient=recipient,
        subject=gen["subject"], body=gen["body"], instruction=instruction,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@app.post("/founders/{founder_id}/drafts")
def create_draft(founder_id: str, body: DraftRequest, db: Session = Depends(get_db)):
    """Generate a draft (email/slack) for approval. Nothing is sent here."""
    founder = db.query(Founder).filter(Founder.id == founder_id).first()
    if not founder:
        raise HTTPException(status_code=404, detail="Founder not found")
    try:
        return _draft_dict(_persist_draft(founder_id, body.instruction, body.channel, body.recipient, db))
    except Exception as e:
        logger.error(f"draft generation failed: {e}")
        raise HTTPException(status_code=503, detail="assistant unavailable")


@app.get("/founders/{founder_id}/drafts")
def list_drafts(founder_id: str, status: str = "pending", db: Session = Depends(get_db)):
    rows = db.query(Draft).filter(
        Draft.founder_id == founder_id, Draft.status == status
    ).order_by(Draft.created_at.desc()).limit(50).all()
    return [_draft_dict(d) for d in rows]


@app.post("/founders/{founder_id}/drafts/{draft_id}/approve")
def approve_draft(founder_id: str, draft_id: str, db: Session = Depends(get_db)):
    """Approve a draft. Slack drafts with a recipient are actually sent; email
    drafts are marked approved (SMTP/Gmail send is the next rung)."""
    draft = db.query(Draft).filter(
        Draft.id == draft_id, Draft.founder_id == founder_id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.approved_at = datetime.utcnow()
    sent = False
    if draft.channel == "slack" and draft.recipient and os.getenv("SLACK_BOT_TOKEN"):
        sent = SlackAdapter(os.getenv("SLACK_BOT_TOKEN")).post_message(draft.recipient, draft.body)
    elif draft.channel == "email" and draft.recipient:
        email_state = db.query(IntegrationState).filter(
            IntegrationState.founder_id == founder_id, IntegrationState.service == "email"
        ).first()
        if email_state:
            adapter = EmailAdapter(
                email_address=(email_state.config or {}).get("email"),
                imap_token=email_state.access_token,
                refresh_token=email_state.refresh_token,
            )
            sent = adapter.send_via_gmail(draft.recipient, draft.subject or "(no subject)", draft.body)
    draft.status = "sent" if sent else "approved"  # approved = ready (no recipient/integration)
    db.commit()
    return {"id": draft.id, "status": draft.status}


@app.post("/founders/{founder_id}/drafts/{draft_id}/discard")
def discard_draft(founder_id: str, draft_id: str, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(
        Draft.id == draft_id, Draft.founder_id == founder_id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "discarded"
    db.commit()
    return {"id": draft.id, "status": "discarded"}


def _verify_slack(raw: bytes, ts: str, sig: str) -> bool:
    """Verify Slack's request signature (trust boundary — don't skip in prod)."""
    secret = os.getenv("SLACK_SIGNING_SECRET")
    if not secret:
        logger.warning("SLACK_SIGNING_SECRET unset — skipping signature check (set it in prod)")
        return True  # ponytail: dev fallback only; required once the bot is public
    try:
        if abs(time.time() - int(ts)) > 300:
            return False
    except (TypeError, ValueError):
        return False
    base = b"v0:" + ts.encode() + b":" + raw
    mine = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mine, sig or "")


def _slack_reply_worker(founder_id: str, channel: str, message: str):
    """Run the chief-of-staff brain and post the reply back to Slack (background
    so we ack Slack within its 3s window and avoid retries)."""
    db = SessionLocal()
    try:
        reply = _chief_of_staff_reply(founder_id, message, db)
        SlackAdapter(os.getenv("SLACK_BOT_TOKEN")).post_message(channel, reply)
    except Exception as e:
        logger.error(f"Slack reply worker failed: {e}")
    finally:
        db.close()


@app.post("/slack/events")
async def slack_events(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Slack Events API: a founder DMs the bot → reply with the chief of staff.
    Reachable with no browser open — the CoS lives in Slack."""
    raw = await request.body()
    payload = json.loads(raw or b"{}")

    # Slack endpoint setup handshake
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if not _verify_slack(
        raw,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=403, detail="bad signature")

    event = payload.get("event", {})
    # Real human message only — ignore the bot's own posts and edits/joins.
    if event.get("type") == "message" and not event.get("bot_id") and not event.get("subtype"):
        user = event.get("user")
        text = (event.get("text") or "").strip()
        channel = event.get("channel")
        founder = db.query(Founder).filter(Founder.slack_user_id == user).first()
        if founder and text and channel:
            background.add_task(_slack_reply_worker, founder.id, channel, text)

    return {"ok": True}  # ack fast; reply happens in the background


def _verify_twilio(url: str, params: dict, signature: str) -> bool:
    """Verify Twilio's X-Twilio-Signature (trust boundary). Algorithm: base64(
    HMAC-SHA1(auth_token, url + concatenated sorted key+value pairs))."""
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not token:
        logger.warning("TWILIO_AUTH_TOKEN unset — skipping WhatsApp signature check (set it in prod)")
        return True  # ponytail: dev fallback only; required once the number is live
    base = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    mac = base64.b64encode(hmac.new(token.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(mac, signature or "")


def _twilio_send_whatsapp(to: str, body: str):
    """Send a WhatsApp message via Twilio REST (httpx, no SDK)."""
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    sender = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g. "whatsapp:+14155238886"
    if not (sid and token and sender):
        logger.error("Twilio env (SID/TOKEN/FROM) incomplete — cannot send WhatsApp reply")
        return
    httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, token),
        data={"From": sender, "To": to, "Body": body[:1500]},
        timeout=20,
    )


def _whatsapp_reply_worker(founder_id: str, to: str, message: str):
    """Background: run the chief-of-staff brain and WhatsApp the reply back."""
    db = SessionLocal()
    try:
        reply = _chief_of_staff_reply(founder_id, message, db)
        _twilio_send_whatsapp(to, reply)
    except Exception as e:
        logger.error(f"WhatsApp reply worker failed: {e}")
    finally:
        db.close()


@app.post("/whatsapp/events")
async def whatsapp_events(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Twilio WhatsApp inbound webhook: a founder messages the number → chief of
    staff replies. Reachable with no browser open. Acks fast (empty TwiML),
    replies in the background to avoid Twilio's webhook timeout."""
    raw = await request.body()
    form = dict(parse_qsl(raw.decode()))  # stdlib parse — no python-multipart dep
    if not _verify_twilio(str(request.url), form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(status_code=403, detail="bad signature")

    sender = form.get("From", "")           # "whatsapp:+14155551234"
    text = (form.get("Body") or "").strip()
    number = sender.replace("whatsapp:", "")
    founder = db.query(Founder).filter(Founder.whatsapp_number == number).first()
    if founder and text:
        background.add_task(_whatsapp_reply_worker, founder.id, sender, text)

    # Empty TwiML ack — the real reply is sent async via the REST API.
    return Response(content="<Response></Response>", media_type="application/xml")


@app.post("/slack/actions")
async def slack_action(request: Request, db: Session = Depends(get_db)):
    """Handle Slack button actions (Decide/Delegate/Dismiss). Slack's request
    signature is the trust boundary — this route is NOT session-gated, so we must
    verify it; otherwise anyone could mutate any alert's status by id. Slack sends
    interactive payloads form-encoded as `payload=<json>`."""
    raw = await request.body()
    if not _verify_slack(raw, request.headers.get("X-Slack-Request-Timestamp", ""),
                         request.headers.get("X-Slack-Signature", "")):
        return JSONResponse({"ok": False, "error": "bad_signature"}, status_code=401)
    try:
        from urllib.parse import parse_qs
        payload = json.loads(parse_qs(raw.decode()).get("payload", ["{}"])[0])
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
    # Respect the platform's $PORT (Render/Cloud Run/Heroku); default 8000 locally.
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
