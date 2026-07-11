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
        fallback_models = [
            settings.OPENROUTER_MODEL,
            "google/gemma-2-9b-it:free",
            "meta-llama/llama-3-8b-instruct:free",
            "qwen/qwen-2-7b-instruct:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "mistralai/mistral-7b-instruct:free"
        ]

        async with httpx.AsyncClient(timeout=90.0) as client:
            retries = len(fallback_models)
            for attempt, model in enumerate(fallback_models):
                payload["model"] = model
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
                    error_details = str(e)
                    if hasattr(e, 'response') and e.response:
                        error_details += f" - Response: {e.response.text}"
                        
                    print(f"[{self.name}] LLM error on model {model}: {error_details}")
                    if attempt == retries - 1:
                        raise RuntimeError(f"LLM API Error (All models failed): {error_details}")
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
