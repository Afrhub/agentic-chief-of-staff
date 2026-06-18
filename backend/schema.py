from sqlalchemy import Column, String, DateTime, JSON, Float, Boolean, Integer, Text, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

Base = declarative_base()


class Founder(Base):
    __tablename__ = "founders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    slack_user_id = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)  # e.g. "+14155551234" (maps inbound WhatsApp)
    stripe_account_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    alerts = relationship("Alert", back_populates="founder")
    decisions = relationship("Decision", back_populates="founder")
    integrations = relationship("IntegrationState", back_populates="founder")
    memories = relationship("SemanticMemory", back_populates="founder")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    founder_id = Column(String, ForeignKey("founders.id"), nullable=False)
    alert_type = Column(String, nullable=False)  # revenue_anomaly, churn_signal, investor_contact, team_conflict, competitor_move
    triggered_at = Column(DateTime, default=datetime.utcnow)

    # Alert content
    title = Column(String, nullable=False)
    what_happened = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=False)
    what_to_do_next = Column(Text, nullable=False)
    next_decision = Column(String, nullable=True)

    # Supporting data
    signals = Column(JSON, nullable=False)  # List of triggering signals with timestamps
    data_freshness = Column(JSON, nullable=False)  # {"stripe": "3 min old", "slack": "real-time", ...}
    confidence_score = Column(Float, default=0.0)  # 0-1, must be >0.8 to surface

    # Historical precedent
    similar_past_decision_id = Column(String, nullable=True)
    precedent_context = Column(Text, nullable=True)

    # State
    status = Column(String, default="active")  # active, decided, delegated, dismissed

    founder = relationship("Founder", back_populates="alerts")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    founder_id = Column(String, ForeignKey("founders.id"), nullable=False)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=True)

    decision_type = Column(String, nullable=False)  # decide, delegate, dismiss
    made_at = Column(DateTime, default=datetime.utcnow)

    # Decision details
    decision_text = Column(Text, nullable=False)  # What they decided
    delegated_to = Column(String, nullable=True)  # Team member name (if delegated)
    rationale = Column(Text, nullable=True)  # Optional notes

    # Outcome tracking (filled later)
    outcome = Column(Text, nullable=True)
    outcome_at = Column(DateTime, nullable=True)
    impact = Column(String, nullable=True)  # positive, neutral, negative

    founder = relationship("Founder", back_populates="decisions")


class SemanticMemory(Base):
    __tablename__ = "semantic_memory"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    founder_id = Column(String, ForeignKey("founders.id"), nullable=False)

    # Content
    content = Column(Text, nullable=False)  # Decision memo, context, outcome
    embedding = Column(Vector(1536), nullable=False)  # OpenAI/Claude embedding
    content_type = Column(String, nullable=False)  # decision, context, pattern, precedent

    # Metadata
    related_decision_id = Column(String, nullable=True)
    tags = Column(JSON, nullable=False)  # ["revenue", "churn", "pricing", ...]
    created_at = Column(DateTime, default=datetime.utcnow)

    founder = relationship("Founder", back_populates="memories")


class IntegrationState(Base):
    __tablename__ = "integration_state"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    founder_id = Column(String, ForeignKey("founders.id"), nullable=False)

    # Integration info
    service = Column(String, nullable=False)  # stripe, slack, email, calendar, salesforce
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)

    # Sync state
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String, default="pending")  # pending, syncing, success, failed
    last_error = Column(Text, nullable=True)

    # Configuration
    config = Column(JSON, nullable=False)  # Service-specific config (channel IDs, etc.)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    founder = relationship("Founder", back_populates="integrations")


class LangGraphCheckpoint(Base):
    __tablename__ = "langgraph_checkpoints"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    founder_id = Column(String, ForeignKey("founders.id"), nullable=False)

    # Workflow state
    thread_id = Column(String, nullable=False)  # LangGraph thread ID
    agent_state = Column(JSON, nullable=False)  # Full agent state snapshot

    checkpoint_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
