"""
Temporal Reasoning Cortex — Full 5-phase pipeline.
Phase 1: Self Autopsy
Phase 2: Causal Chain Reconstruction
Phase 3: Architectural Patch Proposal
Phase 4: Mini-Court Re-submission
Phase 5: Human Approval (stores result, waits for API call)
"""
import asyncio
import uuid
import json
from datetime import datetime

from sqlalchemy import select, update
from db import AsyncSessionLocal
from models import Case
from audit import log_event, get_audit_trail
from sse_manager import sse_manager
from neo4j_service import neo4j_service
from agents.base import BaseAgent


class TRCAgent(BaseAgent):
    """Shared LLM agent for TRC phases."""
    name = "TRC"
    system_prompt = "You are the MORPHEUS Temporal Reasoning Cortex."


trc_agent = TRCAgent()


async def _get_case(case_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Case).where(Case.case_id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            return {}
        return {
            "case_id": case.case_id,
            "title": case.title,
            "business_objective": case.business_objective,
            "status": case.status,
            "compiled_workflow": case.compiled_workflow,
            "checkpoint": case.checkpoint,
            "trc_attempt_number": case.trc_attempt_number,
            "rejected_patches": case.rejected_patches or [],
        }


async def _update_case(case_id: str, updates: dict):
    async with AsyncSessionLocal() as db:
        await db.execute(update(Case).where(Case.case_id == case_id).values(**updates))
        await db.commit()


# ────────────────────────────────────────────────────────────
# Phase 1 — Self Autopsy
# ────────────────────────────────────────────────────────────
async def phase1_autopsy(case_id: str, failed_node_id: str, violation_report: dict) -> dict:
    """Identify failure type, root cause, and related court warnings."""
    # Get nearby flags from Neo4j
    nearby_flags = await neo4j_service.get_nearby_flags(case_id, failed_node_id, hops=2)

    # Get audit trail
    async with AsyncSessionLocal() as db:
        trail = await get_audit_trail(db, case_id)

    system_prompt = """You are the TRC Autopsy Engine for MORPHEUS.
You receive a Case audit trail ending in a critical failure and nearby agent warnings.
Your output MUST be a JSON object with these exact fields:
{
  "failure_node_id": "...",
  "failure_type": "SCHEMA_VIOLATION|POLICY_VIOLATION|TIMEOUT|DEPENDENCY_FAILURE|HALLUCINATED_PARAM",
  "related_court_warnings": [...],
  "preliminary_root_cause": "one sentence",
  "severity": "CRITICAL|HIGH|MEDIUM"
}
Output JSON only. No prose."""

    trc_agent.system_prompt = system_prompt
    user_msg = f"""Failed Node: {failed_node_id}
Violation Report: {json.dumps(violation_report, indent=2)}
Nearby Agent Warnings: {json.dumps(nearby_flags, indent=2)}
Recent Audit Trail (last 10 events): {json.dumps(trail[-10:], indent=2)}

Perform autopsy and identify root cause."""

    # Fast mock for demo purposes
    await asyncio.sleep(2.0)
    result = {
        "failure_node_id": failed_node_id,
        "failure_type": "SCHEMA_VIOLATION",
        "related_court_warnings": nearby_flags,
        "preliminary_root_cause": "Hallucinated parameter 'vendor_gstin' detected by Firewall during runtime schema validation.",
        "severity": "CRITICAL"
    }
    return result


# ────────────────────────────────────────────────────────────
# Phase 2 — Causal Chain Reconstruction
# ────────────────────────────────────────────────────────────
async def phase2_causal_chain(case_id: str, autopsy: dict) -> dict:
    """Build causal chain from Neo4j graph traversal + LLM narrative."""
    failed_node_id = autopsy["failure_node_id"]

    # Graph traversal: first build causal graph from execution nodes
    try:
        await neo4j_service.create_causal_graph(case_id, failed_node_id)
    except Exception as e:
        pass
        
    chain_data = await neo4j_service.get_causal_chain_path(case_id, failed_node_id)
    path_nodes = chain_data.get("path_nodes", [])
    flagged = []

    # LLM narrative
    system_prompt = """You are the TRC Causal Chain Reconstructor.
Given a graph traversal path and agent warnings, generate a causal narrative.
Output JSON:
{
  "causal_narrative": "Step A → Step B → ... → FAILURE (one flowing sentence using →)",
  "root_node_id": "...",
  "chain_length": N,
  "key_decision_points": ["node_id that was a pivotal decision"]
}
Output JSON only."""

    trc_agent.system_prompt = system_prompt
    user_msg = f"""Causal Path Nodes: {json.dumps(path_nodes, indent=2)}
Agent Warnings Along Path: {json.dumps(flagged, indent=2)}
Failure Type: {autopsy['failure_type']}
Root Cause: {autopsy['preliminary_root_cause']}

Reconstruct the causal chain narrative."""

    # Fast mock for demo purposes
    await asyncio.sleep(2.0)
    
    narrative_steps = [n["label"] for n in path_nodes]
    if narrative_steps:
        narrative_str = " → ".join(narrative_steps) + " → Firewall blocked hallucinated parameter → FAILURE"
    else:
        narrative_str = f"Workflow progressed → reached {failed_node_id} → Firewall blocked hallucinated parameter → FAILURE"
        
    narrative = {
        "causal_narrative": narrative_str,
        "root_node_id": path_nodes[0].get("node_id", failed_node_id) if path_nodes else failed_node_id,
        "chain_length": len(path_nodes) if path_nodes else 1,
        "key_decision_points": [failed_node_id],
        "path_nodes": path_nodes
    }
    narrative["flagged_warnings"] = flagged
    return narrative


# ────────────────────────────────────────────────────────────
# Phase 3 — Architectural Patch Proposal
# ────────────────────────────────────────────────────────────
def _cosine_similarity_simple(text1: str, text2: str) -> float:
    """Simple word-overlap similarity (no sklearn needed)."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    return len(intersection) / (len(words1 | words2))


async def phase3_patch_proposal(
    case_id: str, autopsy: dict, causal_chain: dict,
    attempt_number: int, rejected_patches: list
) -> dict:
    """Propose a workflow patch. Checks 80% similarity against rejected patches."""
    case = await _get_case(case_id)
    compiled = case.get("compiled_workflow", {})
    failed_node_id = autopsy["failure_node_id"]

    # Get subgraph around failure (3 nodes)
    all_nodes = compiled.get("nodes", [])
    failure_node = next((n for n in all_nodes if n["node_id"] == failed_node_id), {})
    nearby = [n for n in all_nodes
              if failed_node_id in n.get("dependencies", [])
              or n["node_id"] in failure_node.get("dependencies", [])][:2]
    subgraph = [failure_node] + nearby

    rejected_context = ""
    if rejected_patches:
        rejected_context = f"\nPREVIOUSLY REJECTED PATCHES (do NOT propose similar):\n{json.dumps(rejected_patches, indent=2)}"

    attempt_instruction = {
        1: "Propose a comprehensive patch to fix the root cause.",
        2: f"Constrained: Previous patch was rejected. Address SPECIFICALLY: {rejected_patches[-1].get('rejection_reason', 'unknown') if rejected_patches else 'unknown'}",
        3: "MINIMAL patch only. Propose a single-node fix. No subgraph rewrites permitted.",
    }.get(attempt_number, "Propose a patch.")

    system_prompt = f"""You are the TRC Patch Engine for MORPHEUS.
Attempt #{attempt_number}: {attempt_instruction}

Output JSON:
{{
  "patch_id": "generate a uuid",
  "attempt_number": {attempt_number},
  "patch_type": "INSERT_NODE|REPLACE_NODE|ADD_DEPENDENCY|ADD_VALIDATION_STEP",
  "affected_nodes": ["node_ids being modified"],
  "new_nodes": [
    {{
      "node_id": "patch_node_1",
      "node_type": "VALIDATION|DATA_TRANSFORM|API_CALL",
      "label": "...",
      "description": "...",
      "dependencies": [],
      "can_run_parallel_with": [],
      "policy_locked": false
    }}
  ],
  "new_edges": [{{"from": "node_id", "to": "node_id"}}],
  "patch_rationale": "one sentence",
  "addresses_root_cause": "how this fixes the identified root cause"
}}
Output JSON only.{rejected_context}"""

    trc_agent.system_prompt = system_prompt
    user_msg = f"""Root Cause: {autopsy['preliminary_root_cause']}
Failure Type: {autopsy['failure_type']}
Causal Narrative: {causal_chain['causal_narrative']}
Failed Subgraph: {json.dumps(subgraph, indent=2)}

Propose patch."""

    # Fast mock for demo purposes
    await asyncio.sleep(3.0)
    patch = {
        "patch_id": str(uuid.uuid4()),
        "attempt_number": attempt_number,
        "patch_type": "ADD_VALIDATION_STEP",
        "affected_nodes": [failed_node_id],
        "new_nodes": [
            {
                "node_id": f"patch_node_{str(uuid.uuid4())[:8]}",
                "node_type": "VALIDATION",
                "label": "Input Data Sanitization",
                "description": "Pre-validates vendor_gstin to ensure it meets schema requirements.",
                "dependencies": failure_node.get("dependencies", []),
                "can_run_parallel_with": [],
                "policy_locked": False
            }
        ],
        "new_edges": [],
        "patch_rationale": "Insert schema validation step before the failing API call to intercept hallucinated parameters.",
        "addresses_root_cause": "Validates parameters before reaching the Firewall, ensuring clean data flow."
    }
    return patch


# ────────────────────────────────────────────────────────────
# Phase 4 — Mini-Court
# ────────────────────────────────────────────────────────────
async def phase4_mini_court(
    case_id: str, patch: dict, autopsy: dict, causal_chain: dict
) -> dict:
    """Re-run mini Architecture Court on the patch only."""
    case = await _get_case(case_id)
    attempt = patch.get("attempt_number", 1)

    system_prompt = f"""You are the MORPHEUS Architecture Court conducting a Mini-Court review.
A workflow patch has been proposed by the TRC (Attempt #{attempt}).
Review the patch and give a court verdict.

Output JSON:
{{
  "court_verdict": "APPROVE" | "REJECT",
  "verdict_summary": "one sentence",
  "blocking_issues": [],
  "approved_nodes": ["node_ids that are safe"],
  "disputed_nodes": ["node_ids with issues"],
  "rejection_reason": null | "specific reason if rejected"
}}
Output JSON only."""

    trc_agent.system_prompt = system_prompt
    user_msg = f"""Original Business Objective: {case.get('business_objective', '')}
Failure Context: {autopsy['preliminary_root_cause']}
Causal Chain: {causal_chain['causal_narrative']}
Proposed Patch: {json.dumps(patch, indent=2)}

Court verdict on this patch."""

    # Fast mock for demo purposes
    await asyncio.sleep(2.0)
    verdict = {
        "court_verdict": "APPROVE",
        "verdict_summary": "Patch approved by mini-court. Schema validation correctly mitigates the hallucinated parameter.",
        "blocking_issues": [],
        "approved_nodes": patch.get("affected_nodes", []),
        "disputed_nodes": [],
        "rejection_reason": None
    }
    return verdict


# ────────────────────────────────────────────────────────────
# Main TRC Pipeline
# ────────────────────────────────────────────────────────────
async def run_trc_pipeline(case_id: str, failed_node_id: str, violation_report: dict):
    """Entry point — called automatically after Firewall kill."""
    print(f"\n🧠 TRC activating for Case {case_id}, failed node: {failed_node_id}")
    print(f"[TRC] Phase 1 START — case_id: {case_id}")

    try:
        case = await _get_case(case_id)
        attempt = (case.get("trc_attempt_number") or 0) + 1
        await _update_case(case_id, {"trc_attempt_number": attempt, "status": "AWAITING_HUMAN"})

        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "TRC_ACTIVATED", "TRC",
                            {"attempt": attempt, "failed_node_id": failed_node_id},
                            node_id=failed_node_id)

        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 1, "name": "Self Autopsy", "status": "RUNNING"
        })

        # ── Phase 1 ─────────────────────────────────────────────────────────
        autopsy = await phase1_autopsy(case_id, failed_node_id, violation_report)
        
        # Write partial checkpoint
        case_now = await _get_case(case_id)
        cp = case_now.get("checkpoint") or {}
        cp["trc_autopsy"] = autopsy
        await _update_case(case_id, {"checkpoint": cp})

        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 1, "name": "Self Autopsy", "status": "DONE", "result": autopsy
        })
        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "TRC_AUTOPSY_COMPLETE", "TRC", autopsy)

        await asyncio.sleep(2)  # Throttle for OpenRouter free tier

        # ── Phase 2 ─────────────────────────────────────────────────────────
        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 2, "name": "Causal Chain", "status": "RUNNING"
        })
        causal_chain = await phase2_causal_chain(case_id, autopsy)
        
        # Write partial checkpoint
        case_now = await _get_case(case_id)
        cp = case_now.get("checkpoint") or {}
        cp["trc_causal_chain"] = causal_chain
        await _update_case(case_id, {"checkpoint": cp})

        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 2, "name": "Causal Chain", "status": "DONE",
            "result": causal_chain,
            "highlight_nodes": causal_chain.get("path_node_ids", []),
        })
        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "TRC_CAUSAL_CHAIN_COMPLETE", "TRC", causal_chain)

        await asyncio.sleep(2)  # Throttle for OpenRouter free tier

        # ── Phase 3 ─────────────────────────────────────────────────────────
        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 3, "name": "Patch Proposal", "status": "RUNNING"
        })
        rejected = case.get("rejected_patches", [])
        patch = await phase3_patch_proposal(case_id, autopsy, causal_chain, attempt, rejected)
        
        # Write partial checkpoint
        case_now = await _get_case(case_id)
        cp = case_now.get("checkpoint") or {}
        cp["trc_patch"] = patch
        await _update_case(case_id, {"checkpoint": cp})

        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 3, "name": "Patch Proposal", "status": "DONE", "result": patch
        })
        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "TRC_PATCH_PROPOSED", "TRC", patch)

        await asyncio.sleep(2)  # Throttle for OpenRouter free tier

        # ── Phase 4 ─────────────────────────────────────────────────────────
        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 4, "name": "Mini-Court Review", "status": "RUNNING"
        })
        court_verdict = await phase4_mini_court(case_id, patch, autopsy, causal_chain)
        
        # Write partial checkpoint
        case_now = await _get_case(case_id)
        cp = case_now.get("checkpoint") or {}
        cp["trc_court_verdict"] = court_verdict
        await _update_case(case_id, {"checkpoint": cp})

        await sse_manager.publish(case_id, "TRC_PHASE", {
            "phase": 4, "name": "Mini-Court Review", "status": "DONE", "result": court_verdict
        })
        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "COURT_RECONVENED", "TRC", court_verdict)

        if court_verdict["court_verdict"] == "REJECT":
            # Store rejected patch
            rejected.append({
                "patch_id": patch.get("patch_id"),
                "rationale": patch.get("patch_rationale", ""),
                "description": " ".join(n.get("description", "") for n in patch.get("new_nodes", [])),
                "rejection_reason": court_verdict.get("rejection_reason"),
            })
            await _update_case(case_id, {"rejected_patches": rejected})

            if attempt >= 3:
                # SUSPENDED — Structured System Report
                report = {
                    "type": "STRUCTURED_SYSTEM_REPORT",
                    "case_id": case_id,
                    "objective": case.get("business_objective"),
                    "conclusion": "Three TRC attempts exhausted. Irresolvable architectural contradiction.",
                    "what_human_must_do": "Restate the objective with explicit priority ordering between conflicting constraints.",
                }
                await _update_case(case_id, {"status": "SUSPENDED"})
                await sse_manager.publish(case_id, "CASE_SUSPENDED", report)
                async with AsyncSessionLocal() as db:
                    await log_event(db, case_id, "CASE_SUSPENDED", "TRC", report)
                return

        # ── Phase 5 — Store for human approval ─────────────────────────────
        trc_result = {
            "trc_session_id": str(uuid.uuid4()),
            "attempt_number": attempt,
            "autopsy": autopsy,
            "causal_chain": causal_chain,
            "patch": patch,
            "court_verdict": court_verdict,
            "status": "AWAITING_HUMAN_APPROVAL",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Store TRC result in checkpoint
        case_now = await _get_case(case_id)
        cp = case_now.get("checkpoint") or {}
        cp["trc_result"] = trc_result
        await _update_case(case_id, {
            "checkpoint": cp,
            "status": "AWAITING_HUMAN",
        })

        await sse_manager.publish(case_id, "TRC_COMPLETE", {
            "phase": 5,
            "name": "Awaiting Human Approval",
            "status": "WAITING",
            "trc_result": trc_result,
            "message": f"TRC has proposed a patch. Human approval required.",
        })

        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "TRC_AWAITING_HUMAN", "TRC", trc_result)

        print(f"[TRC] Phase 5 COMPLETE — trc_result written to checkpoint")
        print(f"🧠 TRC complete. Awaiting human approval for Case {case_id}")

    except Exception as e:
        print(f"[TRC] ❌ Fatal error in TRC Pipeline: {e}")
        await _update_case(case_id, {"status": "FAILED"})
        await sse_manager.publish(case_id, "TRC_ERROR", {"error": str(e)})
        async with AsyncSessionLocal() as db:
            await log_event(db, case_id, "TRC_FAILED", "SYSTEM", {"error": str(e)})
