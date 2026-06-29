"""
Case Execution Engine.
Reads compiled workflow, executes nodes in order (respecting deps),
validates through Hallucination Firewall, emits SSE events.
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

import asyncio
import json
from datetime import datetime
import httpx
from sqlalchemy import select, update
from db import AsyncSessionLocal
from models import Case, CourtSession
from audit import log_event
from sse_manager import sse_manager
from firewall.validator import validate_intent, FirewallViolation
from neo4j_service import neo4j_service

async def _get_case(db, case_id: str) -> Case:
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    return result.scalar_one_or_none()

async def _update_case(case_id: str, updates: dict):
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Case).where(Case.case_id == case_id).values(**updates)
        )
        await db.commit()


def _get_executable_nodes(nodes: list[dict], completed: set) -> list[dict]:
    """Return nodes whose all dependencies are in completed set."""
    executable = []
    for node in nodes:
        if node["node_id"] in completed:
            continue
        deps = set(node.get("dependencies", []))
        if deps.issubset(completed):
            executable.append(node)
    return executable


def _build_intent_declaration(firewall_node: dict, target_node: dict, case_id: str) -> dict:
    """Build an Intent Declaration from the API_CALL node for the Firewall."""
    return {
        "node_id": firewall_node["node_id"],
        "target_node_id": target_node["node_id"],
        "action_type": "HTTP_POST",
        "target_endpoint": target_node.get("target_endpoint", ""),
        "http_method": "POST",
        "declared_parameters": target_node.get("declared_parameters", {}),
        "policy_context": {
            "case_id": case_id,
            "node_policy_locks": [],
        },
    }

async def _execute_adg(case_id: str, node: dict) -> dict:
    """Adaptive Decisioning Gate: Uses LLM to decide path based on Case history."""
    from agents.base import BaseAgent
    adg_agent = BaseAgent()
    adg_agent.name = "ADG"
    adg_agent.system_prompt = """You are the Adaptive Decisioning Gate (ADG).
    Analyze the execution history and decide the next best path.
    Output ONLY JSON in the format:
    {
      "selected_branch": "branch_name",
      "confidence": 95.0,
      "reasoning": "Explain why this branch was selected"
    }"""
    
    # Fetch history from Neo4j
    try:
        history = await neo4j_service.get_full_audit_trail(case_id)
    except Exception as e:
        print(f"[ADG] Failed to fetch history: {e}")
        history = []
        
    user_msg = f"Node to decide: {node.get('label')}\nExecution History:\n{json.dumps(history, indent=2)}\n\nDecide path now."
    try:
        raw = await adg_agent.call_llm(user_msg)
        decision = adg_agent.extract_json(raw)
    except Exception as e:
        print(f"[ADG] LLM failed: {e}")
        decision = {}
        
    if isinstance(decision, list):
        decision = decision[0] if decision else {}
    if not isinstance(decision, dict):
        decision = {}

    decision.setdefault("selected_branch", "PROCEED")
    decision.setdefault("confidence", 80.0)
    decision.setdefault("reasoning", "Fallback to standard path due to LLM error.")
        
    await neo4j_service.write_adg_decision(case_id, node["node_id"], decision.get("selected_branch", "next_node_id"), decision.get("confidence", 90.0), decision.get("reasoning", ""), False)
    
    from sse_manager import sse_manager
    await sse_manager.publish(case_id, "ADG_DECISION", {
        "node_id": node["node_id"],
        "label": node.get("label"),
        "decision": decision,
        "message": "ADG decision made. 60-second override window active."
    })
    
    # Update case status to AWAITING_ADG_OVERRIDE
    await _update_case(case_id, {"status": "AWAITING_ADG_OVERRIDE"})
    
    # Pause for 60 seconds (or until human overrides)
    print(f"[ADG] Waiting 60 seconds for potential human override on node {node['node_id']}...")
    for _ in range(60):
        # Check if case status was changed by human override
        async with AsyncSessionLocal() as db:
            c = await _get_case(db, case_id)
            if c and c.status == "EXECUTING":
                print("[ADG] Human overridden/approved. Proceeding immediately.")
                # We need to fetch the potentially updated decision from Neo4j (mocked for now, assuming frontend just updates the node output or we just resume)
                # For simplicity, if human overrides, we just return the decision as is (the override endpoint can modify node_outputs directly)
                break
        await asyncio.sleep(1)
        
    # Ensure status is EXECUTING before returning
    await _update_case(case_id, {"status": "EXECUTING"})
    
    return decision

async def execute_case(case_id: str):
    """Main execution loop running as BackgroundTask."""
    print(f"\n⚡ Execution starting for Case {case_id}...")

    async with AsyncSessionLocal() as db:
        case = await _get_case(db, case_id)
        if not case:
            print(f"[Exec] Case {case_id} not found")
            return

        compiled = case.compiled_workflow
        if not compiled:
            print(f"[Exec] No compiled workflow for {case_id}")
            return

        nodes = compiled.get("nodes", [])
        checkpoint = case.checkpoint or {"completed_nodes": [], "node_outputs": {}}
        completed = set(checkpoint.get("completed_nodes", []))
        node_outputs = checkpoint.get("node_outputs", {})

    await _update_case(case_id, {"status": "EXECUTING"})
    await sse_manager.publish(case_id, "EXECUTION_STARTED", {"case_id": case_id})

    async with AsyncSessionLocal() as db:
        await log_event(db, case_id, "EXECUTION_STARTED", "SYSTEM",
                        {"case_id": case_id, "total_nodes": len(nodes)})

    while True:
        executable = _get_executable_nodes(nodes, completed)
        if not executable:
            # Check if all nodes done
            all_done = all(n["node_id"] in completed for n in nodes)
            if all_done:
                break
            else:
                # Stuck — dependency cycle or all remaining blocked
                print(f"[Exec] No executable nodes but not done. Possibly stuck.")
                break

        for node in executable:
            node_id = node["node_id"]
            node_type = node.get("node_type", "DATA_TRANSFORM")
            label = node.get("label", node_id)

            print(f"[Exec] → Running node: {node_id} ({label})")

            # Emit NODE_STARTED
            await sse_manager.publish(case_id, "NODE_STARTED", {
                "node_id": node_id,
                "label": label,
                "node_type": node_type,
            })
            async with AsyncSessionLocal() as db:
                await log_event(db, case_id, "NODE_STARTED", "SYSTEM",
                                {"node_id": node_id, "label": label}, node_id=node_id)

            # Short delay for demo UX
            await asyncio.sleep(1.5)

            # ── Firewall check for API_CALL nodes ────────────────────────
            if node_type == "FIREWALL_GATE":
                target_node_id = node.get("guards")
                
                # ALWAYS fetch the target node fresh from SQLite so we don't use a stale in-memory cached version
                async with AsyncSessionLocal() as db:
                    fresh_case = await _get_case(db, case_id)
                    fresh_nodes = fresh_case.compiled_workflow.get("nodes", []) if fresh_case and fresh_case.compiled_workflow else nodes
                    target_node = next((n for n in fresh_nodes if n["node_id"] == target_node_id), {})
                
                print(f"🔥 [DEBUG-FIREWALL] Validating node_id: {target_node_id} with declared_parameters: {target_node.get('declared_parameters')}")

                intent = _build_intent_declaration(node, target_node, case_id)

                async with AsyncSessionLocal() as db:
                    case_obj = await _get_case(db, case_id)
                    case_dict = {
                        "status": case_obj.status,
                        "compiled_workflow": case_obj.compiled_workflow,
                        "checkpoint": case_obj.checkpoint,
                    }

                try:
                    token = validate_intent(intent, case_dict)
                    # Firewall passed — proceed
                    await sse_manager.publish(case_id, "FIREWALL_PASSED", {
                        "node_id": node_id,
                        "token_id": token["token_id"],
                        "service": token.get("service"),
                    })
                    print(f"[Firewall] ✅ PASSED for target {target_node_id}")

                except FirewallViolation as fv:
                    # ── FIREWALL KILL ────────────────────────────────────
                    print(f"[Firewall] 🔥 KILLED {target_node_id}: {fv.violation_type}")

                    violation_report = {
                        "layer": fv.layer,
                        "violation_type": fv.violation_type,
                        "details": fv.details,
                        "node_id": target_node_id,
                        "intent_declared": intent,
                    }

                    checkpoint_data = {
                        "completed_nodes": list(completed),
                        "node_outputs": node_outputs,
                        "current_node_id": target_node_id,
                        "paused_at": datetime.utcnow().isoformat(),
                        "failure_node_id": target_node_id,
                        "violation_report": violation_report,
                    }

                    await _update_case(case_id, {
                        "status": "PAUSED",
                        "checkpoint": checkpoint_data,
                        "current_node_id": target_node_id,
                    })

                    async with AsyncSessionLocal() as db:
                        await log_event(db, case_id, "FIREWALL_TRIGGERED", "FIREWALL",
                                        violation_report, node_id=target_node_id)
                        await log_event(db, case_id, "CASE_PAUSED", "FIREWALL",
                                        {"reason": "Firewall kill", "node_id": target_node_id})
                                        
                        # Fetch court session causal_node_ids
                        causal_node_ids = {}
                        res = await db.execute(select(Case).where(Case.case_id == case_id))
                        case_record = res.scalar_one_or_none()
                        if case_record and case_record.court_session_id:
                            cs_res = await db.execute(select(CourtSession).where(CourtSession.session_id == case_record.court_session_id))
                            cs = cs_res.scalar_one_or_none()
                            if cs and cs.causal_node_ids:
                                causal_node_ids = cs.causal_node_ids

                    await neo4j_service.record_execution(case_id, target_node_id, "FIREWALL_BLOCKED", None, intent)
                    await neo4j_service.record_firewall_result(case_id, target_node_id, False, violation_report)
                    
                    # Write CausalNode for Firewall Kill
                    prev_cid = causal_node_ids.get(target_node_id)
                    if prev_cid:
                        failed_param = ""
                        if isinstance(fv.details, dict):
                            failed_param = fv.details.get("missing_field", fv.details.get("invalid_field", ""))
                        elif isinstance(fv.details, str):
                            failed_param = fv.details
                            
                        await neo4j_service.write_causal_node(
                            case_id, target_node_id, "Firewall Kill",
                            {"failed_param": str(failed_param), "is_failure": True},
                            link_from_internal_id=prev_cid
                        )

                    await sse_manager.publish(case_id, "FIREWALL_KILLED", {
                        "node_id": target_node_id,
                        "label": target_node.get("label", "Unknown"),
                        "layer": fv.layer,
                        "violation_type": fv.violation_type,
                        "details": fv.details,
                        "message": f"Hallucination Firewall killed execution at node '{target_node.get('label')}'",
                    })

                    await sse_manager.publish(case_id, "TRC_ACTIVATING", {
                        "node_id": target_node_id,
                        "message": "Temporal Reasoning Cortex activating...",
                    })

                    from trc.pipeline import run_trc_pipeline
                    await run_trc_pipeline(case_id, target_node_id, violation_report)
                    return
            
            # ── Normal node execution ─────────────────────────────────────
            output = {"status": "COMPLETED"}
            
            if node_type == "API_CALL":
                url = node.get("target_endpoint")
                params = node.get("declared_parameters", {})
                if url:
                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(url, json=params)
                            output = resp.json()
                            output["status"] = "SUCCESS" if resp.status_code == 200 else "ERROR"
                    except Exception as e:
                        output = {"status": "ERROR", "message": str(e)}
            
            elif node_type == "ADG_GATE":
                output = await _execute_adg(case_id, node)

            output["node_id"] = node_id
            output["timestamp"] = datetime.utcnow().isoformat()
            node_outputs[node_id] = output

            completed.add(node_id)
            await neo4j_service.record_execution(case_id, node_id, "COMPLETED", output, node.get("declared_parameters", {}))

            await sse_manager.publish(case_id, "NODE_COMPLETED", {
                "node_id": node_id,
                "label": label,
                "output": output,
            })
            async with AsyncSessionLocal() as db:
                await log_event(db, case_id, "NODE_COMPLETED", "SYSTEM",
                                {"node_id": node_id, "output": output}, node_id=node_id)

            # Update checkpoint
            await _update_case(case_id, {
                "checkpoint": {
                    "completed_nodes": list(completed),
                    "node_outputs": node_outputs,
                    "current_node_id": node_id,
                }
            })

        await asyncio.sleep(0.1)

    # ── All nodes complete ──────────────────────────────────────────────
    await _update_case(case_id, {"status": "CLOSED_SUCCESS"})
    async with AsyncSessionLocal() as db:
        await log_event(db, case_id, "CASE_CLOSED", "SYSTEM",
                        {"result": "SUCCESS", "total_nodes": len(nodes)})

    await sse_manager.publish(case_id, "CASE_COMPLETE", {
        "case_id": case_id,
        "status": "CLOSED_SUCCESS",
        "total_nodes": len(nodes),
    })
    print(f"✅ Case {case_id} completed successfully!")
