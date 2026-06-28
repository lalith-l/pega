"""
Audit logging service — append-only, never UPDATE or DELETE rows.
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models import AuditLog
from datetime import datetime


async def log_event(
    db: AsyncSession,
    case_id: str,
    event_type: str,
    triggered_by: str,
    event_payload: dict,
    node_id: str = None,
) -> AuditLog:
    """
    Append a new audit event. Sequence number is auto-calculated per case.
    """
    # Get next sequence number for this case
    result = await db.execute(
        select(func.count()).where(AuditLog.case_id == case_id)
    )
    count = result.scalar() or 0
    next_seq = count + 1

    entry = AuditLog(
        case_id=case_id,
        sequence_number=next_seq,
        event_type=event_type,
        triggered_by=triggered_by,
        node_id=node_id,
        event_payload=event_payload,
        event_timestamp=datetime.utcnow(),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_audit_trail(db: AsyncSession, case_id: str) -> list[dict]:
    """Return full audit trail ordered by sequence number."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.sequence_number.asc())
    )
    logs = result.scalars().all()
    return [
        {
            "log_id": l.log_id,
            "sequence_number": l.sequence_number,
            "event_type": l.event_type,
            "triggered_by": l.triggered_by,
            "node_id": l.node_id,
            "event_payload": l.event_payload,
            "event_timestamp": l.event_timestamp.isoformat() if l.event_timestamp else None,
        }
        for l in logs
    ]
