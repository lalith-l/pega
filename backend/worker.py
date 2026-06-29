import asyncio
import json
from datetime import datetime
from sqlalchemy import update, select
from db import AsyncSessionLocal
from models import CourtSession
from agents.architect import architect_agent
from agents.security import security_agent
from agents.efficiency import efficiency_agent
from agents.compliance import compliance_agent
from audit import log_event
from sse_manager import sse_manager

async def _update_session(session_id: str, updates: dict):
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(CourtSession)
            .where(CourtSession.session_id == session_id)
            .values(**updates)
        )
        await db.commit()

def _run_conflict_resolver(revised_nodes: list[dict], objections: list[dict]) -> list[dict]:
    """Round 3: Algorithmic conflict resolution."""
    # Group objections by node_id
    obj_by_node = {}
    for obj in objections:
        nid = obj["node_id"]
        if nid not in obj_by_node:
            obj_by_node[nid] = []
        obj_by_node[nid].append(obj)

    for node in revised_nodes:
        nid = node["node_id"]
        node_objections = obj_by_node.get(nid, [])
        
        node["agent_verdicts"] = {"ARCHITECT": {"verdict": "APPROVE", "reasoning": "Revised proposal"}}
        
        # If there are objections, assume Architect either fixed them or didn't.
        # We will check the Architect's generated `agent_verdicts` if it included them, 
        # but to strictly follow the "Python algorithm" constraint without LLM:
        # We will assume if an objection was raised, it remains a DISPUTE unless the Architect
        # explicitly marked it as resolved in the node data.
        # Actually, simpler: if the Architect included the objection in its `agent_verdicts` 
        # and marked `resolved: true`, we clear it. Else it is DISPUTED.
        
        has_block = False
        has_warn = False
        
        for obj in node_objections:
            agent = obj["agent"]
            # Did architect claim to resolve it?
            architect_claims_resolved = False
            if "agent_verdicts" in node and agent in node["agent_verdicts"]:
                architect_claims_resolved = node["agent_verdicts"][agent].get("resolved", False)
                
            if not architect_claims_resolved:
                # Add to node verdicts as a dispute
                node["agent_verdicts"][agent] = {
                    "verdict": "DISPUTE",
                    "reasoning": obj["reasoning"],
                    "dispute_type": obj.get("dispute_type"),
                    "severity": obj.get("severity", "WARN")
                }
                if obj.get("severity") == "BLOCK":
                    has_block = True
                else:
                    has_warn = True

        if has_block:
            node["final_status"] = "DISPUTED"
        elif has_warn:
            node["final_status"] = "WARNED"
        else:
            node["final_status"] = "CONSENSUS"
            
    return revised_nodes

async def run_court_session(session_id: str, case_id: str, business_objective: str):
    """3-Round Architecture Court Pipeline."""
    print(f"\n🏛️  Court session {session_id} starting...")

    court_record = {
        "session_id": session_id,
        "business_objective": business_objective,
        "proposed_nodes": [],
        "session_status": "DEBATING",
        "created_at": datetime.utcnow().isoformat(),
        "resolved_at": None,
    }

    try:
        # ── ROUND 1: Independent Proposals ──────────────────────────────────
        print("[Court] Round 1: Architect proposing initial graph...")
        await _update_session(session_id, {"session_status": "DEBATING", "court_record": court_record})
        await sse_manager.publish(case_id, "AGENT_STARTED", {"agent": "ARCHITECT", "session_id": session_id})
        
        # Write Root CausalNode
        from neo4j_service import neo4j_service
        root_causal_id = await neo4j_service.write_causal_node(
            case_id, "GLOBAL", "Schema Context Injection",
            {"schema_version": "v2.1", "is_root": True}
        )
        
        # Fetch session
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CourtSession).where(CourtSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            # Store in session
            causal_node_ids = session.causal_node_ids or {} if session else {}
            
        if root_causal_id:
            causal_node_ids["GLOBAL"] = root_causal_id
            
        initial_nodes = await architect_agent.run_round1(business_objective)
        
        # Write Parameter Declaration CausalNodes for each API_CALL
        from firewall.schema_registry import get_production_schema
        for node in initial_nodes:
            if node.get("node_type") == "API_CALL":
                nid = node.get("node_id")
                target = node.get("target_endpoint", "")
                
                prod_schema = get_production_schema(target)
                expected_v24 = []
                if prod_schema and "schema" in prod_schema and "parameters" in prod_schema["schema"]:
                    expected_v24 = [p["name"] for p in prod_schema["schema"]["parameters"]]
                
                declared_v21 = list(node.get("declared_parameters", {}).keys())
                
                cid = await neo4j_service.write_causal_node(
                    case_id, nid, "Parameter Declaration",
                    {"declared_params_v21": str(declared_v21), "expected_params_v24": str(expected_v24)},
                    link_from_internal_id=root_causal_id
                )
                if cid:
                    causal_node_ids[nid] = cid
                
        # Update court record and causal_node_ids in DB
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CourtSession).where(CourtSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                session.causal_node_ids = causal_node_ids
                session.court_record = court_record
                session.architect_done = True
                await db.commit()
            
        await _update_session(session_id, {"session_status": "DEBATING"})

        # ── ROUND 2: Cross-Examination ──────────────────────────────────────
        print("[Court] Round 2a: Challengers cross-examining proposal...")
        await sse_manager.publish(case_id, "AGENT_STARTED", {"agent": "SECURITY"})
        await sse_manager.publish(case_id, "AGENT_STARTED", {"agent": "EFFICIENCY"})
        await sse_manager.publish(case_id, "AGENT_STARTED", {"agent": "COMPLIANCE"})

        # Run challengers sequentially (staggered to avoid OpenRouter 429 on free tier)
        all_objections = []
        
        try:
            sec_objs = await security_agent.run_round2(business_objective, initial_nodes)
            all_objections.extend(sec_objs)
        except Exception as e:
            print(f"[Court] ⚠️ Security agent failed: {e}")
        
        await asyncio.sleep(3)
        
        try:
            eff_objs = await efficiency_agent.run_round2(business_objective, initial_nodes)
            all_objections.extend(eff_objs)
        except Exception as e:
            print(f"[Court] ⚠️ Efficiency agent failed: {e}")
        
        await asyncio.sleep(3)
        
        try:
            comp_objs = await compliance_agent.run_round2(business_objective, initial_nodes)
            all_objections.extend(comp_objs)
        except Exception as e:
            print(f"[Court] ⚠️ Compliance agent failed: {e}")

        await _update_session(session_id, {
            "security_done": True, 
            "efficiency_done": True, 
            "compliance_done": True
        })

        print(f"[Court] Round 2b: Architect revising proposal against {len(all_objections)} objections...")
        revised_nodes = await architect_agent.run_round2(business_objective, initial_nodes, all_objections)
        
        # Defensive: if architect returned empty or fewer nodes, fall back to initial_nodes
        if not revised_nodes or len(revised_nodes) < len(initial_nodes):
            print(f"[Court] ⚠️  Architect round2 returned {len(revised_nodes) if revised_nodes else 0} nodes (expected {len(initial_nodes)}) — falling back to initial_nodes")
            revised_nodes = initial_nodes

        # ── ROUND 3: Conflict Resolution ──────────────────────────────────────
        print("[Court] Round 3: Algorithmic Conflict Resolution...")
        final_nodes = _run_conflict_resolver(revised_nodes, all_objections)
        
        court_record["proposed_nodes"] = final_nodes
        
        disputed_count = sum(1 for n in final_nodes if n["final_status"] == "DISPUTED")
        
        # Correct status logic: only go to COMPLETED when all nodes are clean
        final_status = "AWAITING_HUMAN" if disputed_count > 0 else "COMPLETED"
        court_record["session_status"] = final_status

        await _update_session(session_id, {
            "session_status": final_status,
            "court_record": court_record,
        })

        # Audit
        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "COURT_COMPLETED", "SYSTEM", {
                "session_id": session_id,
                "total_nodes": len(final_nodes),
                "disputed_nodes": disputed_count,
            })

        await sse_manager.publish(case_id, "COURT_COMPLETE", {
            "session_id": session_id,
            "total_nodes": len(final_nodes),
            "disputed_count": disputed_count,
            "status": "AWAITING_HUMAN",
        })
        print(f"✅ Court session {session_id} complete.")

    except Exception as e:
        print(f"[Court] ❌ Fatal error: {e}")
        await _update_session(session_id, {"session_status": "FAILED", "error_message": str(e)})
        await sse_manager.publish(case_id, "COURT_ERROR", {"error": str(e)})
