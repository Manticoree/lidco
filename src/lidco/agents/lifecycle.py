"""Agent lifecycle management — pause, resume, kill, status."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class AgentLifecycleStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"


@dataclass
class AgentRecord:
    name: str
    status: AgentLifecycleStatus = AgentLifecycleStatus.IDLE
    started_at: float | None = None
    paused_at: float | None = None
    terminated_at: float | None = None


class AgentLifecycleManager:
    """Persist and manage agent lifecycle state in .lidco/agent_status.json."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._status_path = self._project_dir / ".lidco" / "agent_status.json"
        self._agents: dict[str, AgentRecord] = {}
        self._load()

    def register(self, name: str) -> AgentRecord:
        record = AgentRecord(name=name)
        self._agents[name] = record
        self._save()
        return record

    def start(self, name: str) -> bool:
        record = self._agents.get(name)
        if record is None:
            record = self.register(name)
        if record.status == AgentLifecycleStatus.TERMINATED:
            return False
        record.status = AgentLifecycleStatus.RUNNING
        record.started_at = time.time()
        self._save()
        return True

    def pause(self, name: str) -> bool:
        record = self._agents.get(name)
        if record and record.status == AgentLifecycleStatus.RUNNING:
            record.status = AgentLifecycleStatus.PAUSED
            record.paused_at = time.time()
            self._save()
            return True
        return False

    def resume(self, name: str) -> bool:
        record = self._agents.get(name)
        if record and record.status == AgentLifecycleStatus.PAUSED:
            record.status = AgentLifecycleStatus.RUNNING
            record.paused_at = None
            self._save()
            return True
        return False

    def kill(self, name: str) -> bool:
        record = self._agents.get(name)
        if record:
            record.status = AgentLifecycleStatus.TERMINATED
            record.terminated_at = time.time()
            self._save()
            return True
        return False

    def get(self, name: str) -> AgentRecord | None:
        return self._agents.get(name)

    def list_all(self) -> list[AgentRecord]:
        return list(self._agents.values())

    def _save(self) -> None:
        self._status_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            name: {
                "name": r.name,
                "status": r.status.value,
                "started_at": r.started_at,
                "paused_at": r.paused_at,
                "terminated_at": r.terminated_at,
            }
            for name, r in self._agents.items()
        }
        self._status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self._status_path.exists():
            return
        try:
            data = json.loads(self._status_path.read_text(encoding="utf-8"))
            for name, d in data.items():
                self._agents[name] = AgentRecord(
                    name=d["name"],
                    status=AgentLifecycleStatus(d["status"]),
                    started_at=d.get("started_at"),
                    paused_at=d.get("paused_at"),
                    terminated_at=d.get("terminated_at"),
                )
        except Exception:
            pass
