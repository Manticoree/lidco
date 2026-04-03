"""Conversation pattern detection (Q248)."""
from __future__ import annotations


class PatternDetector:
    """Detect anti-patterns in a conversation message list."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = list(messages)

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def detect_loops(self, window: int = 5) -> list[dict]:
        """Find repeated message content within a sliding *window*."""
        alerts: list[dict] = []
        for i, msg in enumerate(self._messages):
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            start = max(0, i - window)
            for j in range(start, i):
                prev = (self._messages[j].get("content") or "").strip()
                if prev and prev == content:
                    alerts.append({
                        "type": "loop",
                        "indices": [j, i],
                        "content_preview": content[:80],
                    })
                    break  # one alert per repeated turn
        return alerts

    def detect_dead_ends(self) -> list[int]:
        """Return indices of turns followed by an error or empty response."""
        dead: list[int] = []
        for i in range(len(self._messages) - 1):
            nxt = self._messages[i + 1]
            content = (nxt.get("content") or "").strip()
            role = nxt.get("role", "")
            if not content and role == "assistant":
                dead.append(i)
            elif content.lower().startswith("error"):
                dead.append(i)
        return dead

    def detect_excessive_retries(self, threshold: int = 3) -> list[dict]:
        """Detect the same tool called more than *threshold* times consecutively."""
        alerts: list[dict] = []
        if not self._messages:
            return alerts

        streak_tool: str | None = None
        streak_count = 0
        streak_start = 0

        for i, msg in enumerate(self._messages):
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                name = tool_calls[0] if isinstance(tool_calls[0], str) else (
                    tool_calls[0].get("name", "") if isinstance(tool_calls[0], dict) else ""
                )
                if name == streak_tool:
                    streak_count += 1
                else:
                    if streak_tool and streak_count > threshold:
                        alerts.append({
                            "type": "excessive_retries",
                            "tool": streak_tool,
                            "count": streak_count,
                            "start_index": streak_start,
                        })
                    streak_tool = name
                    streak_count = 1
                    streak_start = i
            else:
                if streak_tool and streak_count > threshold:
                    alerts.append({
                        "type": "excessive_retries",
                        "tool": streak_tool,
                        "count": streak_count,
                        "start_index": streak_start,
                    })
                streak_tool = None
                streak_count = 0

        # flush remaining streak
        if streak_tool and streak_count > threshold:
            alerts.append({
                "type": "excessive_retries",
                "tool": streak_tool,
                "count": streak_count,
                "start_index": streak_start,
            })

        return alerts

    def detect_all(self) -> list[dict]:
        """Run all detectors and return combined alerts."""
        alerts: list[dict] = []
        alerts.extend(self.detect_loops())
        for idx in self.detect_dead_ends():
            alerts.append({"type": "dead_end", "index": idx})
        alerts.extend(self.detect_excessive_retries())
        return alerts

    def summary(self) -> str:
        """Human-readable summary of detected patterns."""
        alerts = self.detect_all()
        if not alerts:
            return "No problematic patterns detected."
        counts: dict[str, int] = {}
        for a in alerts:
            t = a.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        parts = ", ".join(f"{t}: {c}" for t, c in sorted(counts.items()))
        return f"Detected {len(alerts)} pattern(s): {parts}"
