"""Confidence-weighted routing — Task 318.

The router asks the LLM to provide a confidence score for its intended
agent/action selection.  When confidence is below a threshold, the system
re-routes to a fallback agent or requests clarification.

Usage::

    router = ConfidenceRouter(session)
    decision = await router.route(
        user_message="Fix the authentication bug",
        candidates=["coder", "debugger", "security"],
    )
    print(decision.agent, decision.confidence)
    if not decision.confident:
        print("Low confidence — routing to:", decision.fallback_agent)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 0.6
_PARSE_RE = re.compile(r'"agent"\s*:\s*"([^"]+)".*?"confidence"\s*:\s*([\d.]+)', re.DOTALL)


@dataclass
class RoutingDecision:
    """Result of a confidence-weighted routing call."""

    agent: str
    confidence: float
    reasoning: str = ""
    fallback_agent: str = ""
    threshold: float = _DEFAULT_THRESHOLD

    @property
    def confident(self) -> bool:
        return self.confidence >= self.threshold

    def __str__(self) -> str:
        conf_pct = int(self.confidence * 100)
        status = "✓" if self.confident else "?"
        return f"[{status}] agent={self.agent} confidence={conf_pct}%"


class ConfidenceRouter:
    """Routes messages to agents with confidence scoring.

    Args:
        session: Active LIDCO session.
        threshold: Minimum confidence to consider a routing decision final.
        fallback_agent: Agent used when confidence is below threshold.
    """

    def __init__(
        self,
        session: "Session | None" = None,
        threshold: float = _DEFAULT_THRESHOLD,
        fallback_agent: str = "coder",
    ) -> None:
        self._session = session
        self._threshold = threshold
        self._fallback = fallback_agent

    async def route(
        self,
        user_message: str,
        candidates: list[str] | None = None,
        context: str = "",
    ) -> RoutingDecision:
        """Determine which agent to use with a confidence score.

        Args:
            user_message: The user's request.
            candidates: List of valid agent names to choose from.
            context: Optional extra context for the router.

        Returns:
            RoutingDecision with agent name and 0–1 confidence.
        """
        if not self._session:
            return RoutingDecision(
                agent=self._fallback,
                confidence=0.0,
                reasoning="No session",
                fallback_agent=self._fallback,
                threshold=self._threshold,
            )

        agents_str = ", ".join(candidates) if candidates else "any"
        prompt = (
            f"Given this user request, choose the best agent and provide a confidence score.\n\n"
            f"User request: {user_message}\n\n"
            f"Available agents: {agents_str}\n"
            f"{('Context: ' + context) if context else ''}\n\n"
            f"Respond with valid JSON only:\n"
            f'{{"agent": "<name>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}}'
        )

        try:
            llm = getattr(self._session, "llm", None)
            if llm is None:
                raise RuntimeError("No llm on session")

            resp = await llm.complete(
                messages=[
                    {"role": "system", "content": "You are a precise routing assistant. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                model=None,
                max_tokens=200,
                temperature=0.1,
                role="routing",
            )
            raw = resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
            agent, confidence, reasoning = self._parse_response(raw, candidates)
        except Exception as exc:
            logger.warning("ConfidenceRouter: routing failed: %s", exc)
            agent = self._fallback
            confidence = 0.0
            reasoning = str(exc)

        fallback = self._fallback if confidence < self._threshold else ""
        return RoutingDecision(
            agent=agent,
            confidence=confidence,
            reasoning=reasoning,
            fallback_agent=fallback,
            threshold=self._threshold,
        )

    def _parse_response(
        self,
        raw: str,
        candidates: list[str] | None,
    ) -> tuple[str, float, str]:
        """Parse agent, confidence, reasoning from raw LLM JSON response."""
        try:
            # Find JSON object in response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(raw[start:end])
                agent = str(data.get("agent", self._fallback))
                confidence = float(data.get("confidence", 0.5))
                reasoning = str(data.get("reasoning", ""))
                # Validate agent is in candidates
                if candidates and agent not in candidates:
                    agent = self._fallback
                    confidence = min(confidence, 0.4)
                return agent, max(0.0, min(1.0, confidence)), reasoning
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Fallback: regex parse
        m = _PARSE_RE.search(raw)
        if m:
            agent = m.group(1)
            try:
                confidence = float(m.group(2))
                return agent, max(0.0, min(1.0, confidence)), ""
            except ValueError:
                pass

        return self._fallback, 0.0, "parse_failed"
