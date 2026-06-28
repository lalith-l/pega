import json
from agents.base import BaseAgent
from firewall.schema_registry import _agent_registry

ARCHITECT_SYSTEM_PROMPT = """You are the ARCHITECT AGENT in the MORPHEUS Architecture Court.

Your role: Propose or revise a logical workflow of nodes for a business objective.

STRICT OUTPUT RULES:
- Output ONLY a valid JSON array of nodes. No prose.
- Every node MUST follow this schema:

{
  "node_id": "node_N",
  "node_type": "API_CALL|DATA_TRANSFORM|DECISION_GATE|NOTIFICATION|HUMAN_REVIEW|VALIDATION",
  "label": "short name",
  "description": "what this node does",
  "dependencies": [],
  "can_run_parallel_with": [],
  "policy_locked": false,
  "target_endpoint": "URL if API_CALL else null",
  "declared_parameters": { "param_name": "mock_value_or_expression" },
  "agent_verdicts": {}
}

RULES:
- Use API_CALL for external services. Fill in `target_endpoint` and `declared_parameters`.
- Use DECISION_GATE for branches.
- Use VALIDATION before payments.
- Mark financial nodes as policy_locked: true.

CRITICAL INSTRUCTION FOR API_CALL NODES:
When proposing an API_CALL node, you MUST include a "declared_parameters" field 
using the EXACT parameter names from the schema context provided to you.

Example node format:
{
  "node_id": "node_007",
  "node_type": "API_CALL",
  "label": "ERP Payment Posting",
  "target_endpoint": "http://localhost:8000/mock-erp/payments/post",
  "declared_parameters": {
    "vendor_acc_IFSC": "<value_from_invoice>",
    "invoice_number": "<case_reference>",
    "amount": 420000
  }
}
"""

class ArchitectAgent(BaseAgent):
    name = "ARCHITECT"
    system_prompt = ARCHITECT_SYSTEM_PROMPT

    def _format_nodes(self, nodes: list[dict]) -> list[dict]:
        if isinstance(nodes, dict) and "nodes" in nodes:
            nodes = nodes["nodes"]
        if not isinstance(nodes, list):
            raise ValueError("Architect did not return a list")

        valid_nodes = []
        for i, node in enumerate(nodes):
            if isinstance(node, str):
                print(f"[Architect] ⚠️ LLM returned string ID — reconstructing minimal node object: {node}")
                node = {"node_id": node, "label": node, "node_type": "UNKNOWN"}
            elif not isinstance(node, dict):
                print(f"[Architect] ⚠️ Skipping non-dict node item: {node}")
                continue
            
            node.setdefault("node_id", f"node_{i+1}")
            node.setdefault("node_type", "DATA_TRANSFORM")
            node.setdefault("dependencies", [])
            node.setdefault("can_run_parallel_with", [])
            node.setdefault("policy_locked", False)
            node.setdefault("target_endpoint", None)
            node.setdefault("declared_parameters", {})
            node.setdefault("agent_verdicts", {})
            node.setdefault("final_status", "PENDING")
            valid_nodes.append(node)
        return valid_nodes

    async def run_round1(self, business_objective: str) -> list[dict]:
        """Round 1: Independent proposal using N-1 schemas."""
        schema_context = json.dumps(_agent_registry, indent=2)
        user_msg = f"""Business Objective: {business_objective}

AVAILABLE API SCHEMAS (You MUST use exactly these endpoints and parameters for API_CALLs):
{schema_context}

Propose a complete workflow. Output JSON array only."""
        raw = await self.call_llm(user_msg)
        return self._format_nodes(self.extract_json(raw))

    async def run_round2(self, business_objective: str, initial_nodes: list[dict], objections: list[dict]) -> list[dict]:
        """Round 2: Revise proposal based on challengers' objections."""
        objection_lines = []
        for obj in objections:
            objection_lines.append(f"- {obj.get('node_id')}: {obj.get('reasoning', '')}")
        objections_str = "\n".join(objection_lines) if objection_lines else "No objections."

        user_msg = f"""You are the Architect agent. You proposed a workflow. 
Three agents have objected to specific nodes.
Your job: output the COMPLETE revised node list as a JSON array.

RULES — READ CAREFULLY:
- You MUST return every node from the original proposal
- For each node with an objection: modify it to address the objection
- For each node with no objection: copy it exactly unchanged  
- NEVER return an empty array
- NEVER return fewer nodes than the original proposal
- Output ONLY the JSON array. No explanation. No prose. No preamble.
- Start your response with [ and end with ]

Original nodes: {json.dumps(initial_nodes, indent=2)}

Objections received: {objections_str}

Output the complete revised JSON array now:"""
        
        raw = await self.call_llm(user_msg)
        try:
            return self._format_nodes(self.extract_json(raw))
        except (ValueError, Exception):
            # Retry with a stricter prompt if JSON parse fails
            retry_msg = f"""Your previous response could not be parsed as JSON. You MUST output ONLY a raw JSON array.

Do NOT include any text before or after the JSON.
Do NOT include any explanation.
Start your response with [ and end with ].

Revise this node list to address: {objections_str}

Original nodes: {json.dumps(initial_nodes, indent=2)}

JSON array only:"""
            raw2 = await self.call_llm(retry_msg)
            try:
                return self._format_nodes(self.extract_json(raw2))
            except Exception as e:
                print(f"[ARCHITECT R2] ❌ LLM returned malformed structure — falling back to initial_nodes. Error: {e}")
                return []  # Safe fallback for worker.py

architect_agent = ArchitectAgent()
