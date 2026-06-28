"""
Base agent class — shared OpenRouter (nvidia) LLM client.
All agents inherit from this and override their system prompt + parse logic.
"""
import json
import re
import httpx
import asyncio
import random
from config import settings


class BaseAgent:
    name: str = "BASE"
    system_prompt: str = ""

    async def call_llm(self, user_message: str) -> str:
        """Call OpenRouter API and return raw text response."""
        # ── FAST MOCK FOR DEMO PROMPTS ───────────────────────────────────────
        print(f"[{self.name}] ⚡ FAST DEMO MOCK TRIGGERED")
        await asyncio.sleep(1) # simulate small delay
        if self.name == "ARCHITECT":
            if "Three agents have objected" in user_message:
                # Round 2: Just return the same nodes but pretend we addressed them
                try:
                    match = re.search(r"Original nodes: (\[.*?\])", user_message, re.DOTALL)
                    if match:
                        return match.group(1)
                except Exception:
                    pass
            
            # Round 1: Return guaranteed failure node for TRC demo
            return """[
              {
                "node_id": "fw_node_002",
                "node_type": "FIREWALL_GATE",
                "label": "Firewall: Validate ERP Payment",
                "guards": "node_003"
              },
              {
                "node_id": "node_003",
                "node_type": "API_CALL",
                "label": "ERP Payment Posting",
                "target_endpoint": "http://localhost:8000/mock-erp/payments/post",
                "declared_parameters": {
                  "invoice_number": "INV-123",
                  "vendor_id": "V-100",
                  "amount": 125000,
                  "ifsc_code": "HDFC0001",
                  "account_number": "12345678",
                  "vendor_gstin": "29ABCDE1234F1Z5"
                }
              }
            ]"""
        else:
            # Security/Compliance/Efficiency - no objections to speed up
            return "[]"
        # ───────────────────────────────────────────────────────────────────────

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://morpheus.ai",
            "X-Title": "MORPHEUS",
        }
        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            retries = 5
            for attempt in range(retries):
                try:
                    resp = await client.post(
                        f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 429:
                        if attempt < retries - 1:
                            jitter = random.uniform(1, 5)
                            wait = (5 * (attempt + 1)) + jitter
                            print(f"[{self.name}] ⚠️ 429 rate-limited — retry {attempt+1}/{retries}, waiting {wait:.1f}s")
                            await asyncio.sleep(wait)
                            continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                except Exception as e:
                    if attempt < retries - 1:
                        await asyncio.sleep(3)
                    else:
                        print(f"[{self.name}] Final LLM error: {e}")
                        return "[]"
        return "[]"

    def extract_json(self, text: str) -> any:
        """Extract JSON from LLM response — handles markdown code blocks."""
        # Strip markdown code blocks
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # Remove common preamble phrases before JSON
        # e.g. "Here is the revised JSON:" or "Sure, here is:"
        preamble_patterns = [
            r'^[^\[\{]*?(?=\[|\{)',  # Everything before first [ or {
        ]

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON array first (most common for architect)
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        # Try JSON object
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        # Last resort: try to find any valid JSON chunk
        json_pattern = re.compile(r'(\[.*?\]|\{.*?\})', re.DOTALL)
        for match in json_pattern.finditer(text):
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

        raise ValueError(f"Could not extract JSON from LLM response: {text[:300]}")
