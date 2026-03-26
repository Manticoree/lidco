"""MessageQueue — persistent FIFO queue with dead-letter support (stdlib only)."""
from __future__ import annotations

import collections
import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_PATH = Path(".lidco") / "message_queue.json"


@dataclass
class Message:
    id: str
    topic: str
    payload: dict
    attempts: int = 0
    created_at: float = 0.0
    status: str = "pending"  # pending | processing | acked | dead

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex
        if self.created_at == 0.0:
            self.created_at = time.time()


class MessageQueue:
    """
    Persistent FIFO message queue with dead-letter queue.

    Parameters
    ----------
    path:
        JSON file for persistence.  *None* → in-memory only.
    max_attempts:
        Number of delivery attempts before moving to DLQ.
    """

    def __init__(
        self,
        path: object = "DEFAULT",
        max_attempts: int = 3,
    ) -> None:
        if path == "DEFAULT":
            self._path: Path | None = _DEFAULT_PATH
        elif path is None:
            self._path = None
        else:
            self._path = Path(str(path))

        self._max_attempts = max_attempts
        self._queues: dict[str, collections.deque] = {}
        self._processing: dict[str, Message] = {}  # id → Message
        self._dlq: dict[str, list[Message]] = {}
        self._lock = threading.Lock()
        if self._path is not None:
            self._load()

    # ----------------------------------------------------------------- private

    def _save(self) -> None:
        if self._path is None:
            return

        def _msg_to_dict(m: Message) -> dict:
            return {
                "id": m.id, "topic": m.topic, "payload": m.payload,
                "attempts": m.attempts, "created_at": m.created_at, "status": m.status,
            }

        with self._lock:
            data = {
                "queues": {t: [_msg_to_dict(m) for m in dq] for t, dq in self._queues.items()},
                "processing": {mid: _msg_to_dict(m) for mid, m in self._processing.items()},
                "dlq": {t: [_msg_to_dict(m) for m in msgs] for t, msgs in self._dlq.items()},
            }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))

            def _to_msg(d: dict) -> Message:
                return Message(
                    id=d["id"], topic=d["topic"], payload=d["payload"],
                    attempts=d.get("attempts", 0), created_at=d.get("created_at", 0.0),
                    status=d.get("status", "pending"),
                )

            with self._lock:
                for topic, msgs in raw.get("queues", {}).items():
                    self._queues[topic] = collections.deque(_to_msg(m) for m in msgs)
                for mid, m in raw.get("processing", {}).items():
                    self._processing[mid] = _to_msg(m)
                for topic, msgs in raw.get("dlq", {}).items():
                    self._dlq[topic] = [_to_msg(m) for m in msgs]
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    # ------------------------------------------------------------------ public

    def enqueue(self, topic: str, payload: dict) -> Message:
        """Create and enqueue a message.  Return the Message."""
        msg = Message(id=uuid.uuid4().hex, topic=topic, payload=payload)
        with self._lock:
            if topic not in self._queues:
                self._queues[topic] = collections.deque()
            self._queues[topic].append(msg)
        self._save()
        return msg

    def dequeue(self, topic: str) -> Message | None:
        """Pop the oldest message from *topic*.  Return *None* if empty."""
        with self._lock:
            dq = self._queues.get(topic)
            if not dq:
                return None
            msg = dq.popleft()
            updated = Message(
                id=msg.id, topic=msg.topic, payload=msg.payload,
                attempts=msg.attempts + 1, created_at=msg.created_at,
                status="processing",
            )
            self._processing[msg.id] = updated
        self._save()
        return updated

    def ack(self, message_id: str) -> bool:
        """Acknowledge a message.  Remove from processing.  Return True if found."""
        with self._lock:
            if message_id not in self._processing:
                return False
            del self._processing[message_id]
        self._save()
        return True

    def nack(self, message_id: str) -> bool:
        """
        Negative-acknowledge a message.

        If attempts < max_attempts: re-enqueue.
        Otherwise: move to dead-letter queue.
        Return True if found.
        """
        with self._lock:
            msg = self._processing.get(message_id)
            if msg is None:
                return False
            del self._processing[message_id]

            if msg.attempts >= self._max_attempts:
                dead = Message(
                    id=msg.id, topic=msg.topic, payload=msg.payload,
                    attempts=msg.attempts, created_at=msg.created_at, status="dead",
                )
                if msg.topic not in self._dlq:
                    self._dlq[msg.topic] = []
                self._dlq[msg.topic].append(dead)
            else:
                requeue = Message(
                    id=msg.id, topic=msg.topic, payload=msg.payload,
                    attempts=msg.attempts, created_at=msg.created_at, status="pending",
                )
                if msg.topic not in self._queues:
                    self._queues[msg.topic] = collections.deque()
                self._queues[msg.topic].append(requeue)

        self._save()
        return True

    def list_topics(self) -> list[str]:
        """Return all topic names with pending or dead-letter messages."""
        with self._lock:
            topics = set(self._queues.keys()) | set(self._dlq.keys())
        return sorted(topics)

    def dead_letters(self, topic: str | None = None) -> list[Message]:
        """Return dead-letter messages, optionally filtered by topic."""
        with self._lock:
            if topic is not None:
                return list(self._dlq.get(topic, []))
            return [m for msgs in self._dlq.values() for m in msgs]

    def queue_size(self, topic: str) -> int:
        with self._lock:
            return len(self._queues.get(topic, []))

    def clear(self, topic: str | None = None) -> int:
        """Clear pending messages.  *None* = all topics.  Return count."""
        with self._lock:
            if topic is None:
                count = sum(len(dq) for dq in self._queues.values())
                self._queues = {}
            else:
                count = len(self._queues.get(topic, []))
                self._queues.pop(topic, None)
        self._save()
        return count
