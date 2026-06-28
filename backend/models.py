"""
SQLAlchemy models for MORPHEUS — SQLite local dev.
All tables use UUID strings as primary keys.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, Boolean, JSON, Float
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.utcnow()


# ──────────────────────────────────────────────
# Court Session (Architecture Court)
# ──────────────────────────────────────────────
class CourtSession(Base):
    __tablename__ = "court_sessions"

    session_id = Column(String, primary_key=True, default=_uuid)
    business_objective = Column(Text, nullable=False)

    # Full Court Record JSON (updated as agents complete)
    court_record = Column(JSON, nullable=True)

    # Progress tracking
    architect_done = Column(Boolean, default=False)
    security_done = Column(Boolean, default=False)
    efficiency_done = Column(Boolean, default=False)
    compliance_done = Column(Boolean, default=False)

    # "CONVENING" | "DEBATING" | "AWAITING_HUMAN" | "RESOLVED" | "COMPILED"
    session_status = Column(String, default="CONVENING")

    created_at = Column(DateTime, default=_now)
    resolved_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


# ──────────────────────────────────────────────
# Case (Living Case Object)
# ──────────────────────────────────────────────
class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    business_objective = Column(Text, nullable=False)

    # FSM state
    # DRAFT | COMPILED | EXECUTING | PAUSED | AWAITING_HUMAN
    # RESUMING | FAILED | SUSPENDED | CLOSED_SUCCESS | CLOSED_FAILURE
    status = Column(String, default="DRAFT")

    # Links
    court_session_id = Column(String, nullable=True)

    # Compiled workflow JSON (the JSON State Machine)
    compiled_workflow = Column(JSON, nullable=True)

    # Execution checkpoint (for pause/resume/rollback)
    checkpoint = Column(JSON, nullable=True)

    # Current execution pointer (node_id currently executing)
    current_node_id = Column(String, nullable=True)

    # TRC state
    trc_attempt_number = Column(Integer, default=0)
    rejected_patches = Column(JSON, default=list)  # list of {patch_id, rationale, nodes}

    # SLA
    sla_deadline = Column(DateTime, nullable=True)

    # Amendment history
    amendments = Column(JSON, default=list)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ──────────────────────────────────────────────
# Audit Log (append-only, never UPDATE/DELETE)
# ──────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)  # auto-increment per case

    event_type = Column(String, nullable=False)
    # SYSTEM | ARCHITECT | SECURITY | EFFICIENCY | COMPLIANCE | USER | FIREWALL | TRC | ADG
    triggered_by = Column(String, nullable=False)
    node_id = Column(String, nullable=True)

    # Full context JSON
    event_payload = Column(JSON, nullable=True)

    event_timestamp = Column(DateTime, default=_now)


# ──────────────────────────────────────────────
# SLA Rules
# ──────────────────────────────────────────────
class SLARule(Base):
    __tablename__ = "sla_rules"

    rule_id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, nullable=False, index=True)

    # e.g. "PAUSED_TOO_LONG" | "OVERDUE" | "ESCALATION_THRESHOLD"
    rule_type = Column(String, nullable=False)
    threshold_minutes = Column(Integer, nullable=False)
    escalation_contact = Column(String, nullable=True)

    triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime, nullable=True)


# ──────────────────────────────────────────────
# Schema Registry (Firewall API schemas)
# ──────────────────────────────────────────────
class SchemaRegistryEntry(Base):
    __tablename__ = "schema_registry"

    entry_id = Column(String, primary_key=True, default=_uuid)
    endpoint_pattern = Column(String, nullable=False, unique=True)  # e.g. "stripe.com/v1/charges"
    service_name = Column(String, nullable=False)  # "stripe" | "erp_mock" | "sendgrid"
    schema_version = Column(String, nullable=False)
    parameter_schema = Column(JSON, nullable=False)  # JSON Schema for validation
    registered_at = Column(DateTime, default=_now)
