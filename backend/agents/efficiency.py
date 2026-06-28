from agents.base import BaseAgent

EFFICIENCY_SYSTEM_PROMPT = """You are the EFFICIENCY AGENT in the MORPHEUS Architecture Court.

Your role: Review the Architect's proposed workflow and output specific node-level objections.

STRICT OUTPUT RULES:
- Output ONLY a valid JSON array of objection objects. One object per node_id that has an issue.
- If no nodes have issues, output an empty array []. No prose.

Objection schema:
{
  "node_id": "node_N",
  "dispute_type": "REDUNDANT_NODE" | "ORDERING_VIOLATION" | "PARALLELIZATION_MISSED" | "BOTTLENECK",
  "severity": "WARN" | "BLOCK",
  "reasoning": "one sentence explaining the inefficiency"
}

CHECKS:
1. Are nodes running sequentially when they have no dependency?
2. Is there a bottleneck?
"""

class EfficiencyAgent(BaseAgent):
    name = "EFFICIENCY"
    system_prompt = EFFICIENCY_SYSTEM_PROMPT

    async def run_round2(self, business_objective: str, nodes: list[dict]) -> list[dict]:
        import json
        user_msg = f"""Business Objective: {business_objective}

Architect's Proposal:
{json.dumps(nodes, indent=2)}

Review every node for efficiency issues. Output JSON array of objections only."""
        raw = await self.call_llm(user_msg)
        verdicts = self.extract_json(raw)
        
        if isinstance(verdicts, dict) and "verdicts" in verdicts:
            verdicts = verdicts["verdicts"]
        if not isinstance(verdicts, list):
            raise ValueError("Efficiency agent did not return a list")
            
        for v in verdicts:
            v["agent"] = "EFFICIENCY"
        return verdicts

efficiency_agent = EfficiencyAgent()
