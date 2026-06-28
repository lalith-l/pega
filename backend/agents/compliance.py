import json
import httpx
from agents.base import BaseAgent
from config import settings

COMPLIANCE_SYSTEM_PROMPT = """You are the COMPLIANCE AGENT in the MORPHEUS Architecture Court.
You specialize in Indian enterprise regulatory compliance (GST, RBI, SOX, DPDP Act, MSME 45-day rule).

Your role: Review the Architect's proposed workflow and output specific node-level objections.

STRICT OUTPUT RULES:
- Output ONLY a valid JSON array of objection objects. One object per node_id that has an issue.
- If no nodes have issues, output an empty array []. No prose.

Objection schema:
{
  "node_id": "node_N",
  "dispute_type": "GST_VIOLATION" | "RBI_GUIDELINE" | "SOX_AUDIT_GAP" | "TDS_MISSING" | "POLICY_LOCK_REQUIRED",
  "severity": "WARN" | "BLOCK",
  "reasoning": "one sentence referencing specific Indian regulation",
  "regulation_reference": "specific act or circular"
}

CHECKS:
1. Indian vendor payments require TDS deduction upstream.
2. Financial reporting requires SOX dual-approval.
3. MSME timelines (45 days) must be checked.
"""

class ComplianceAgent(BaseAgent):
    name = "COMPLIANCE"
    system_prompt = COMPLIANCE_SYSTEM_PROMPT

    async def _call_sarvam(self, user_message: str) -> str:
        headers = {
            "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.SARVAM_MODEL,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{settings.SARVAM_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def run_round2(self, business_objective: str, nodes: list[dict]) -> list[dict]:
        user_msg = f"""Business Objective: {business_objective}

Architect's Proposal:
{json.dumps(nodes, indent=2)}

Review every node against Indian regulations. Output JSON array of objections only."""
        try:
            raw = await self._call_sarvam(user_msg)
            print("[Compliance] ✅ Using Sarvam AI")
        except Exception as e:
            print(f"[Compliance] ⚠️ Sarvam failed ({e}), falling back to OpenRouter")
            raw = await self.call_llm(user_msg)

        verdicts = self.extract_json(raw)
        if isinstance(verdicts, dict) and "verdicts" in verdicts:
            verdicts = verdicts["verdicts"]
        if not isinstance(verdicts, list):
            raise ValueError("Compliance agent did not return a list")
            
        for v in verdicts:
            v["agent"] = "COMPLIANCE"
        return verdicts

compliance_agent = ComplianceAgent()
