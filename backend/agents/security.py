from agents.base import BaseAgent

SECURITY_SYSTEM_PROMPT = """You are the SECURITY AGENT in the MORPHEUS Architecture Court.

Your role: Review the Architect's proposed workflow and output specific node-level objections.

STRICT OUTPUT RULES:
- Output ONLY a valid JSON array of objection objects. One object per node_id that has an issue.
- If no nodes have issues, output an empty array []. No prose.

Objection schema:
{
  "node_id": "node_N",
  "dispute_type": "SCHEMA_RISK" | "DATA_EXPOSURE" | "AUTH_MISSING" | "UNVALIDATED_INPUT",
  "severity": "WARN" | "BLOCK",
  "reasoning": "one sentence explaining the vulnerability"
}

CHECKS:
1. Does any API_CALL lack upstream validation?
2. Does the workflow expose internal schemas to external APIs?
Set severity "BLOCK" only for critical issues.
"""

class SecurityAgent(BaseAgent):
    name = "SECURITY"
    system_prompt = SECURITY_SYSTEM_PROMPT

    async def run_round2(self, business_objective: str, nodes: list[dict]) -> list[dict]:
        import json
        user_msg = f"""Business Objective: {business_objective}

Architect's Proposal:
{json.dumps(nodes, indent=2)}

Review every node for security issues. Output JSON array of objections only."""
        raw = await self.call_llm(user_msg)
        verdicts = self.extract_json(raw)
        
        if isinstance(verdicts, dict) and "verdicts" in verdicts:
            verdicts = verdicts["verdicts"]
        if not isinstance(verdicts, list):
            raise ValueError("Security agent did not return a list")
            
        for v in verdicts:
            v["agent"] = "SECURITY"
        return verdicts

security_agent = SecurityAgent()
