"""
Server-Sent Events manager.
Allows the frontend to subscribe to real-time Case events.
"""
import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator


class SSEManager:
    def __init__(self):
        # case_id → list of asyncio.Queue
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, case_id: str) -> AsyncIterator[str]:
        """Yield SSE-formatted event strings for a case."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[case_id].append(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:  # sentinel = done
                    break
                yield event
        finally:
            self._subscribers[case_id].remove(queue)

    async def publish(self, case_id: str, event_type: str, data: dict):
        """Push an event to all subscribers of a case."""
        payload = json.dumps({"event": event_type, "data": data})
        message = f"data: {payload}\n\n"
        for queue in list(self._subscribers.get(case_id, [])):
            await queue.put(message)

    async def close(self, case_id: str):
        """Send sentinel to close all subscriber streams."""
        for queue in list(self._subscribers.get(case_id, [])):
            await queue.put(None)


sse_manager = SSEManager()
