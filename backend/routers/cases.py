from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
import uuid

from db import get_db
from models import Case
from execution_engine import execute_case
from audit import log_event, get_audit_trail
from sse_manager import sse_manager
from state_machine import validate_transition, InvalidTransitionError
from neo4j_service import neo4j_service

router = APIRouter(prefix="/cases", tags=["Cases"])

class RollbackRequest(BaseModel):
    target_node_id: str

class ADGOverrideRequest(BaseModel):
    node_id: str
    selected_branch: str
    reasoning: str


# ── GET /cases ───────────────────────────────────────────────────────────────
@router.get("")
async def list_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).order_by(Case.created_at.desc()))
    cases = result.scalars().all()
    return [
        {
            "case_id": c.case_id,
            "title": c.title,
            "status": c.status,
            "court_session_id": c.court_session_id,
            "trc_attempt_number": c.trc_attempt_number,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]


# ── GET /cases/{case_id} ─────────────────────────────────────────────────────
@router.get("/{case_id}")
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    return {
        "case_id": case.case_id,
        "title": case.title,
        "business_objective": case.business_objective,
        "status": case.status,
        "court_session_id": case.court_session_id,
        "compiled_workflow": case.compiled_workflow,
        "checkpoint": case.checkpoint,
        "trc_attempt_number": case.trc_attempt_number,
        "amendments": case.amendments or [],
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


# ── GET /cases/{case_id}/audit ───────────────────────────────────────────────
@router.get("/{case_id}/audit")
async def get_case_audit(case_id: str, db: AsyncSession = Depends(get_db)):
    trail = await get_audit_trail(db, case_id)
    return {"case_id": case_id, "audit_trail": trail}


# ── POST /cases/{case_id}/execute ────────────────────────────────────────────
@router.post("/{case_id}/execute")
async def execute(
    case_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status not in ("COMPILED", "RESUMING"):
        raise HTTPException(400, f"Cannot execute: Case is in '{case.status}' state")

    background_tasks.add_task(execute_case, case_id)
    return {"status": "started", "case_id": case_id, "message": "Execution started"}


# ── POST /cases/{case_id}/trc/approve ────────────────────────────────────────
@router.post("/{case_id}/trc/approve")
async def approve_trc_patch(case_id: str, db: AsyncSession = Depends(get_db)):
    """Human approves TRC patch — applies patch and resumes execution."""
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    checkpoint = case.checkpoint or {}
    trc_result = checkpoint.get("trc_result")
    if not trc_result:
        raise HTTPException(400, "No TRC patch awaiting approval")

    patch = trc_result.get("patch", {})
    new_nodes = patch.get("new_nodes", [])
    import copy
    compiled = copy.deepcopy(case.compiled_workflow) if case.compiled_workflow else {"nodes": []}

    # Apply patch
    failed_id = trc_result["autopsy"]["failure_node_id"]
    nodes = compiled.get("nodes", [])
    patch_type = patch.get("patch_type", "")
    
    if patch_type in ("REPLACE_NODE", "MODIFY_PARAMETERS") and new_nodes:
        # Replace the failed node in place, preserving its ID so dependencies and guards still work
        new_node = new_nodes[0]
        new_node["node_id"] = failed_id
        for i, n in enumerate(nodes):
            if n["node_id"] == failed_id:
                nodes[i] = new_node
                break
    else:
        # Insert mode
        existing_ids = {n["node_id"] for n in nodes}
        existing_labels = {n.get("label") for n in nodes}
        for node in new_nodes:
            if node["node_id"] not in existing_ids:
                # Prevent inserting duplicate ADD_VALIDATION_STEP nodes
                if patch_type == "ADD_VALIDATION_STEP" and node.get("label") in existing_labels:
                    continue
                insert_idx = next(
                    (i for i, n in enumerate(nodes) if n["node_id"] == failed_id),
                    len(nodes)
                )
                nodes.insert(insert_idx, node)

    # Clear the failing node's firewall block by adjusting checkpoint
    completed_nodes = checkpoint.get("completed_nodes", [])
    
    # If MODIFY_PARAMETERS or REPLACE_NODE, we must re-run the FIREWALL_GATE that guards this node
    if patch_type in ("REPLACE_NODE", "MODIFY_PARAMETERS"):
        firewall_node = next((n for n in nodes if n.get("node_type") == "FIREWALL_GATE" and n.get("guards") == failed_id), None)
        if firewall_node and firewall_node["node_id"] in completed_nodes:
            completed_nodes.remove(firewall_node["node_id"])
            checkpoint["current_node_id"] = firewall_node["node_id"]
            print(f"✅ [PATCH] Execution will resume from FIREWALL_GATE node: {firewall_node['node_id']} (guards {failed_id})")

    checkpoint["completed_nodes"] = completed_nodes
    checkpoint.pop("failure_node_id", None)
    checkpoint.pop("violation_report", None)
    checkpoint.pop("trc_result", None)

    # ── VERIFICATION PRINT ──────────────────────────────────────────────
    if patch_type == "MODIFY_PARAMETERS":
        erp_node = next((n for n in nodes if n["node_id"] == failed_id), {})
        print(f"✅ [VERIFICATION] ERP Payment Posting declared_parameters in SQLite: {erp_node.get('declared_parameters')}")
    # ────────────────────────────────────────────────────────────────────

    # Record amendment
    amendments = case.amendments or []
    amendments.append({
        "amendment_number": len(amendments) + 1,
        "patch_id": patch.get("patch_id"),
        "patch_type": patch.get("patch_type"),
        "rationale": patch.get("patch_rationale"),
        "approved_at": __import__("datetime").datetime.utcnow().isoformat(),
    })

    await db.execute(
        update(Case).where(Case.case_id == case_id).values(
            compiled_workflow=compiled,
            checkpoint=checkpoint,
            status="RESUMING",
            amendments=amendments,
            trc_attempt_number=0,
        )
    )
    await db.commit()

    await log_event(db, case_id, "AMENDMENT_LOGGED", "USER",
                    {"patch_id": patch.get("patch_id"), "amendment": amendments[-1]})

    await neo4j_service.create_amendment(
        case_id=case_id,
        patch_id=patch.get("patch_id"),
        patch_type=patch.get("patch_type"),
        rationale=patch.get("patch_rationale"),
        amendment_number=len(amendments)
    )

    await sse_manager.publish(case_id, "PATCH_APPROVED", {
        "case_id": case_id,
        "amendment_number": len(amendments),
        "message": "Patch approved. Resuming execution...",
    })

    return {
        "status": "patch_approved",
        "case_id": case_id,
        "amendment_number": len(amendments),
        "message": "Patch applied. Call /cases/{case_id}/execute to resume.",
    }


# ── POST /cases/{case_id}/trc/abandon ────────────────────────────────────────
@router.post("/{case_id}/trc/abandon")
async def abandon_case(case_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    await db.execute(
        update(Case).where(Case.case_id == case_id).values(status="CLOSED_FAILURE")
    )
    await db.commit()
    await log_event(db, case_id, "CASE_CLOSED", "USER", {"result": "FAILURE", "reason": "Human abandoned"})
    await sse_manager.publish(case_id, "CASE_ABANDONED", {"case_id": case_id})

    return {"status": "closed", "case_id": case_id, "result": "CLOSED_FAILURE"}


# ── POST /cases/{case_id}/rollback ───────────────────────────────────────────
@router.post("/{case_id}/rollback")
async def rollback_case(case_id: str, req: RollbackRequest, db: AsyncSession = Depends(get_db)):
    """Human-initiated rollback to a specific execution checkpoint (node_id)."""
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
        
    checkpoint = case.checkpoint or {}
    completed_nodes = checkpoint.get("completed_nodes", [])
    
    if req.target_node_id not in completed_nodes:
        raise HTTPException(400, f"Cannot rollback: Node {req.target_node_id} is not in completed history")

    # In a full implementation, we'd truncate the completed_nodes list up to the target_node_id based on topology order
    # For now, we simulate resetting it by just keeping it in the list (so it doesn't re-run) but removing others might be complex without the topological map
    # We will just delegate to Neo4j to delete downstream executions
    await neo4j_service.rollback_to_node(case_id, req.target_node_id)
    
    await db.execute(
        update(Case).where(Case.case_id == case_id).values(status="RESUMING", current_node_id=req.target_node_id)
    )
    await db.commit()
    await log_event(db, case_id, "CASE_ROLLBACK", "USER", {"target_node_id": req.target_node_id})
    await sse_manager.publish(case_id, "CASE_ROLLBACK", {"case_id": case_id, "target_node_id": req.target_node_id})
    return {"status": "rollback_complete", "case_id": case_id, "target_node_id": req.target_node_id}


# ── POST /cases/{case_id}/adg/override ───────────────────────────────────────
@router.post("/{case_id}/adg/override")
async def override_adg(case_id: str, req: ADGOverrideRequest, db: AsyncSession = Depends(get_db)):
    """Human overrides the ADG decision within the 60s window."""
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
        
    if case.status != "AWAITING_ADG_OVERRIDE":
        raise HTTPException(400, "Case is not awaiting ADG override")

    await neo4j_service.write_adg_decision(
        case_id, 
        req.node_id, 
        req.selected_branch, 
        100.0, 
        f"Human Override: {req.reasoning}", 
        True
    )
    
    # Resume execution
    await db.execute(
        update(Case).where(Case.case_id == case_id).values(status="EXECUTING")
    )
    await db.commit()
    await log_event(db, case_id, "ADG_OVERRIDE", "USER", {"node_id": req.node_id, "branch": req.selected_branch})
    await sse_manager.publish(case_id, "ADG_OVERRIDDEN", {"case_id": case_id, "node_id": req.node_id})
    
    return {"status": "overridden", "case_id": case_id}



# ── GET /cases/{case_id}/stream ──────────────────────────────────────────────
@router.get("/{case_id}/stream")
async def stream_events(case_id: str):
    """SSE stream for real-time Case events."""
    from fastapi.responses import StreamingResponse
    from sse_manager import sse_manager

    async def event_generator():
        async for event in sse_manager.subscribe(case_id):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
