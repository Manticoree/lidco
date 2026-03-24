"""AgentMailbox — peer-to-peer message passing between agents in a team."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from queue import Empty, Queue


@dataclass
class MailMessage:
    from_: str
    to: str
    message: str
    timestamp: float = field(default_factory=time.time)


class AgentMailbox:
    """Thread-safe in-memory message queues per agent name."""

    def __init__(self) -> None:
        self._queues: dict[str, Queue] = defaultdict(Queue)
        self._lock = threading.Lock()

    def send(self, to: str, from_: str, message: str) -> None:
        """Send a message to an agent's inbox."""
        msg = MailMessage(from_=from_, to=to, message=message)
        with self._lock:
            self._queues[to].put(msg)

    def receive(self, agent_name: str, timeout: float = 0) -> list[MailMessage]:
        """Drain all messages for an agent. timeout=0 means non-blocking."""
        messages = []
        q = self._queues[agent_name]
        try:
            while True:
                if timeout > 0:
                    msg = q.get(timeout=timeout)
                    timeout = 0  # only wait on first message
                else:
                    msg = q.get_nowait()
                messages.append(msg)
        except Empty:
            pass
        return messages

    def broadcast(self, from_: str, message: str, recipients: list[str]) -> None:
        """Send the same message to multiple agents."""
        for recipient in recipients:
            self.send(to=recipient, from_=from_, message=message)

    def pending_count(self, agent_name: str) -> int:
        """Number of unread messages for an agent."""
        return self._queues[agent_name].qsize()

    def clear(self, agent_name: str) -> None:
        """Clear all messages for an agent."""
        with self._lock:
            self._queues[agent_name] = Queue()
