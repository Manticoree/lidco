"""HTTP-backed slash commands — point a slash command at a remote URL."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError


@dataclass
class HTTPSlashCommand:
    name: str
    url: str
    method: str = "POST"
    timeout: int = 30
    headers: dict[str, str] = field(default_factory=dict)

    def execute(self, args: str) -> str:
        """POST args to URL and return response."""
        payload = json.dumps({"args": args}).encode("utf-8")
        headers = {"Content-Type": "application/json", **self.headers}
        req = Request(self.url, data=payload, headers=headers, method=self.method)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except URLError as exc:
            return f"[HTTP error: {exc}]"
        except Exception as exc:
            return f"[error: {exc}]"


class HTTPCommandRegistry:
    """Registry of HTTP-backed slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, HTTPSlashCommand] = {}

    def register(self, cmd: HTTPSlashCommand) -> None:
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> HTTPSlashCommand | None:
        return self._commands.get(name)

    def list(self) -> list[HTTPSlashCommand]:
        return list(self._commands.values())

    def unregister(self, name: str) -> bool:
        if name in self._commands:
            del self._commands[name]
            return True
        return False

    def load_yaml(self, path: Path) -> int:
        """Load commands from a YAML file. Returns count loaded."""
        if not path.exists():
            return 0
        try:
            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        except ImportError:
            data = _parse_simple_yaml_list(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        count = 0
        for item in data:
            if isinstance(item, dict) and "name" in item and "url" in item:
                cmd = HTTPSlashCommand(
                    name=item["name"],
                    url=item["url"],
                    method=item.get("method", "POST"),
                    timeout=int(item.get("timeout", 30)),
                    headers=item.get("headers", {}),
                )
                self.register(cmd)
                count += 1
        return count


def _parse_simple_yaml_list(text: str) -> list[dict]:
    """Very minimal YAML list parser for when PyYAML unavailable."""
    result = []
    current: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- name:"):
            if current:
                result.append(current)
            current = {"name": line.split(":", 1)[1].strip()}
        elif line.startswith("url:") and current is not None:
            current["url"] = line.split(":", 1)[1].strip()
    if current:
        result.append(current)
    return result
