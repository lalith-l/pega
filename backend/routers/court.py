from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from db import get_db
from models import CourtSession, Case
from worker import run_court_session
from audit import log_event
from neo4j_service import neo4j_service
from sse_manager import sse_manager

router = APIRouter(prefix="/court", tags=["Architecture Court"])


class ConveneRequest(BaseModel):
    business_objective: str
    case_id: Optional[str] = None  # If provided, attach court session to existing case


class ResolveConflictRequest(BaseModel):
    session_id: str
    node_id: str
    resolution_action: str  # "ACCEPT" | "MODIFY" | "REMOVE"
    modification_instruction: Optional[str] = None


class CompileRequest(BaseModel):
    session_id: str


# ── POST /court/convene ──────────────────────────────────────────────────────
@router.post("/convene")
async def convene_court(
    req: ConveneRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start an Architecture Court session. Returns session_id immediately."""
    session_id = str(uuid.uuid4())

    # Create or get Case
    if req.case_id:
        result = await db.execute(select(Case).where(Case.case_id == req.case_id))
        case = result.scalar_one_or_none()
        if not case:
            raise HTTPException(404, f"Case {req.case_id} not found")
        case_id = req.case_id
    else:
        case = Case(
            title=req.business_objective[:60],
            business_objective=req.business_objective,
            status="DRAFT",
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)
        case_id = case.case_id

    # Create CourtSession
    session = CourtSession(
        session_id=session_id,
        business_objective=req.business_objective,
        session_status="CONVENING",
    )
    db.add(session)

    # Link to Case
    await db.execute(
        update(Case)
        .where(Case.case_id == case_id)
        .values(court_session_id=session_id)
    )
    await db.commit()

    # Audit log
    await log_event(db, case_id, "COURT_STARTED", "USER",
                    {"session_id": session_id, "objective": req.business_objective})

    # Launch background worker
    background_tasks.add_task(run_court_session, session_id, case_id, req.business_objective)

    return {
        "session_id": session_id,
        "case_id": case_id,
        "status": "CONVENING",
        "message": "Architecture Court is convening. Poll /court/{session_id}/status for updates.",
    }


# ── GET /court/{session_id}/status ──────────────────────────────────────────
@router.get("/{session_id}/status")
async def get_court_status(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CourtSession).where(CourtSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "session_id": session_id,
        "session_status": session.session_status,
        "architect_done": session.architect_done,
        "security_done": session.security_done,
        "efficiency_done": session.efficiency_done,
        "compliance_done": session.compliance_done,
        "error_message": session.error_message,
    }


# ── GET /court/{session_id}/record ───────────────────────────────────────────
@router.get("/{session_id}/record")
async def get_court_record(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CourtSession).where(CourtSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "session_id": session_id,
        "session_status": session.session_status,
        "court_record": session.court_record,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


# ── POST /court/resolve ──────────────────────────────────────────────────────
@router.post("/resolve")
async def resolve_conflict(req: ResolveConflictRequest, db: AsyncSession = Depends(get_db)):
    """Human resolves a disputed node."""
    result = await db.execute(
        select(CourtSession).where(CourtSession.session_id == req.session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    court_record = session.court_record
    if not court_record:
        raise HTTPException(400, "Court record not ready")

    # Find and update the node
    node_found = False
    for node in court_record.get("proposed_nodes", []):
        if node["node_id"] == req.node_id:
            node["final_status"] = "RESOLVED"
            node["resolution"] = {
                "resolved_by": "HUMAN",
                "resolution_action": req.resolution_action,
                "modification_instruction": req.modification_instruction,
                "timestamp": datetime.utcnow().isoformat(),
            }
            node_found = True
            break

    if not node_found:
        raise HTTPException(404, f"Node {req.node_id} not found")

    # Check if all nodes are now settled (CONSENSUS or RESOLVED, not DISPUTED)
    all_settled = all(
        n["final_status"] in ("CONSENSUS", "RESOLVED", "WARNED")
        for n in court_record["proposed_nodes"]
    )
    if all_settled:
        # All disputes are cleared — advance court to COMPLETED so compile can proceed
        court_record["session_status"] = "COMPLETED"

    await db.execute(
        update(CourtSession)
        .where(CourtSession.session_id == req.session_id)
        .values(court_record=court_record, session_status=court_record["session_status"])
    )
    await db.commit()

    return {"status": "resolved", "node_id": req.node_id, "all_resolved": all_settled}


# ── POST /court/compile ──────────────────────────────────────────────────────
@router.post("/compile")
async def compile_workflow_body(req: CompileRequest, db: AsyncSession = Depends(get_db)):
    """Compile approved Court Record into a JSON State Machine for execution."""
    return await _do_compile(req.session_id, db)


# ── POST /court/{session_id}/compile ─────────────────────────────────────────
@router.post("/{session_id}/compile")
async def compile_workflow_path(session_id: str, db: AsyncSession = Depends(get_db)):
    """Compile by path param (convenience route)."""
    return await _do_compile(session_id, db)


async def _do_compile(session_id: str, db: AsyncSession):
    result = await db.execute(
        select(CourtSession).where(CourtSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    court_record = session.court_record
    if not court_record:
        raise HTTPException(400, "Court record not ready")

    # Filter out REMOVE'd nodes only — RESOLVED and CONSENSUS both compile
    active_nodes = [
        n for n in court_record.get("proposed_nodes", [])
        if n.get("resolution", {}).get("resolution_action") != "REMOVE"
        and n.get("final_status") in ("CONSENSUS", "RESOLVED", "WARNED")
    ]

    # Block compile if any unresolved DISPUTED nodes remain
    remaining_disputed = [n for n in court_record.get("proposed_nodes", [])
                          if n["final_status"] == "DISPUTED"]
    if remaining_disputed:
        raise HTTPException(400, f"Cannot compile: {len(remaining_disputed)} unresolved disputes remain")

    # Find the Case linked to this session
    case_result = await db.execute(
        select(Case).where(Case.court_session_id == session_id)
    )
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "No case found for this session")

    # Build compiled workflow (JSON State Machine)
    from compiler import compile_workflow, CompilationError
    try:
        compiled = compile_workflow(
            case_id=case.case_id, 
            objective=court_record["business_objective"], 
            raw_nodes=active_nodes
        )
    except CompilationError as e:
        raise HTTPException(400, f"Compilation failed: {e}")

    # Save compiled workflow
    await db.execute(
        update(Case)
        .where(Case.case_id == case.case_id)
        .values(compiled_workflow=compiled, status="COMPILED")
    )
    await db.execute(
        update(CourtSession)
        .where(CourtSession.session_id == session_id)
        .values(session_status="COMPILED", resolved_at=datetime.utcnow())
    )
    await db.commit()

    # Write to Neo4j
    try:
        await neo4j_service.create_case_graph(
            case.case_id, compiled["nodes"], court_record["business_objective"]
        )

        # Write also agent verdicts to Neo4j
        agent_names = ["ARCHITECT", "SECURITY", "EFFICIENCY", "COMPLIANCE"]
        for agent_name in agent_names:
            verdicts = []
            for node in active_nodes:
                av = node.get("agent_verdicts", {}).get(agent_name)
                if av:
                    verdicts.append({"node_id": node["node_id"], **av})
            if verdicts:
                await neo4j_service.write_agent_verdicts(case.case_id, agent_name, verdicts)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(503, "Graph database is waking up. Please click Compile again in 10 seconds.")

    await log_event(db, case.case_id, "COMPILED", "USER",
                    {"compiled_nodes": len(active_nodes), "session_id": session_id})

    await sse_manager.publish(case.case_id, "WORKFLOW_COMPILED", {
        "case_id": case.case_id,
        "total_nodes": len(active_nodes),
    })

    return {
        "status": "compiled",
        "case_id": case.case_id,
        "compiled_nodes": len(active_nodes),
        "compiled_workflow": compiled,
    }
