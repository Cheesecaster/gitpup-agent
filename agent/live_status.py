"""Agent live status manager + SSE broadcast."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentStatus:
    """Current live state of the agent."""
    state: str = "sleeping"  # sleeping, thinking, writing_code, running_tests, committing, chatting
    current_task: str = ""
    current_file: str = ""
    thoughts: str = ""
    last_update: float = 0.0
    mood: str = "peaceful"  # peaceful, focused, curious, excited, confused

    def __post_init__(self):
        if self.last_update == 0.0:
            self.last_update = time.time()

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "current_task": self.current_task,
            "current_file": self.current_file,
            "thoughts": self.thoughts,
            "last_update": self.last_update,
            "mood": self.mood,
        }


class StatusManager:
    """Manages agent live status and broadcasts to SSE clients."""

    def __init__(self):
        self._clients: list[asyncio.Queue] = []
        self._status = AgentStatus()
        self._chat_history: list[dict] = []

    async def broadcast(self, data: dict):
        """Send update to all connected SSE clients."""
        for key, value in data.items():
            if hasattr(self._status, key):
                setattr(self._status, key, value)
        self._status.last_update = time.time()

        payload = json.dumps(self._status.to_dict())

        dead = []
        for queue in self._clients:
            try:
                queue.put_nowait(payload)
            except Exception:
                dead.append(queue)

        for q in dead:
            if q in self._clients:
                self._clients.remove(q)

    def register_client(self) -> asyncio.Queue:
        """Register a new SSE client, return its queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._clients.append(queue)
        queue.put_nowait(json.dumps(self._status.to_dict()))
        return queue

    def unregister_client(self, queue: asyncio.Queue):
        if queue in self._clients:
            self._clients.remove(queue)

    def add_chat_message(self, role: str, content: str):
        self._chat_history.append({"role": role, "content": content, "time": time.time()})

    def get_chat_history(self, limit: int = 50) -> list[dict]:
        return self._chat_history[-limit:]
