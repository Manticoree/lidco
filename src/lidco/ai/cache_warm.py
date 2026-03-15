"""Cache warming strategies — Task 425.

Pre-warms Anthropic prompt cache by sending minimal "ready" messages to
agents and pinging tool schemas before the first real user turn.

Usage::

    warmer = CacheWarmer(session)
    results = await warmer.warm_system_prompts()
    results += await warmer.warm_tools()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

_WARM_MESSAGE = "ready"
_WARM_SYSTEM_SUFFIX = "\n\n[cache-warm: system prompt primed]"


@dataclass
class WarmResult:
    """Result of a single cache-warm operation."""

    agent_name: str
    tokens_cached: int = 0
    duration_ms: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error


class CacheWarmer:
    """Sends minimal LLM calls to prime Anthropic's prompt cache.

    Args:
        session: The active LIDCO session with agents and tool registry.
    """

    def __init__(self, session: "Session") -> None:
        self._session = session

    async def _warm_agent(self, agent_name: str) -> WarmResult:
        """Send a minimal ping to one agent to prime its system-prompt cache."""
        t0 = time.monotonic()
        try:
            agent = self._session.agent_registry.get(agent_name)
            if agent is None:
                return WarmResult(agent_name=agent_name, error="agent not found")

            llm = getattr(agent, "_llm", None) or getattr(self._session, "llm", None)
            if llm is None:
                return WarmResult(agent_name=agent_name, error="no LLM provider")

            sys_prompt = ""
            if hasattr(agent, "build_system_prompt"):
                try:
                    sys_prompt = agent.build_system_prompt()
                except Exception:
                    pass
            if not sys_prompt and hasattr(agent, "_config"):
                sys_prompt = getattr(agent._config, "system_prompt", "") or ""

            messages: list[dict[str, Any]] = [
                {"role": "user", "content": _WARM_MESSAGE},
            ]

            params: dict[str, Any] = {
                "messages": messages,
                "max_tokens": 1,
            }
            if sys_prompt:
                params["system"] = sys_prompt + _WARM_SYSTEM_SUFFIX

            model = getattr(agent._config, "model", None) or ""
            if model:
                params["model"] = model

            resp = await llm.complete(**params)
            tokens = 0
            if resp and hasattr(resp, "usage") and resp.usage:
                tokens = getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
                tokens += getattr(resp.usage, "cache_read_input_tokens", 0) or 0

            duration = (time.monotonic() - t0) * 1000
            return WarmResult(agent_name=agent_name, tokens_cached=tokens, duration_ms=duration)

        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.debug("Cache warm failed for %s: %s", agent_name, exc)
            return WarmResult(agent_name=agent_name, duration_ms=duration, error=str(exc))

    async def warm_system_prompts(
        self, agent_names: list[str] | None = None
    ) -> list[WarmResult]:
        """Warm system prompts for all (or specified) agents.

        Args:
            agent_names: List of agent names to warm. Defaults to all registered.

        Returns:
            List of :class:`WarmResult` instances.
        """
        if agent_names is None:
            try:
                agents = self._session.agent_registry.list_agents()
                agent_names = [a._config.name for a in agents]
            except Exception:
                agent_names = []

        if not agent_names:
            return []

        tasks = [self._warm_agent(name) for name in agent_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: list[WarmResult] = []
        for name, r in zip(agent_names, results):
            if isinstance(r, Exception):
                output.append(WarmResult(agent_name=name, error=str(r)))
            else:
                output.append(r)
        return output

    async def warm_tools(self) -> list[WarmResult]:
        """Send a tool-schema ping to cache tool descriptions.

        Returns:
            A single :class:`WarmResult` representing the tool warm.
        """
        t0 = time.monotonic()
        try:
            registry = getattr(self._session, "tool_registry", None)
            if registry is None:
                return [WarmResult(agent_name="tools", error="no tool registry")]

            tools = registry.list_tools()
            if not tools:
                return [WarmResult(agent_name="tools", error="no tools registered")]

            llm = getattr(self._session, "llm", None)
            if llm is None:
                return [WarmResult(agent_name="tools", error="no LLM provider")]

            tool_schemas = []
            for t in tools:
                if hasattr(t, "to_schema"):
                    try:
                        tool_schemas.append(t.to_schema())
                    except Exception:
                        pass

            messages: list[dict[str, Any]] = [
                {"role": "user", "content": "What tools are available?"},
            ]
            params: dict[str, Any] = {
                "messages": messages,
                "max_tokens": 1,
            }
            if tool_schemas:
                params["tools"] = tool_schemas

            resp = await llm.complete(**params)
            tokens = 0
            if resp and hasattr(resp, "usage") and resp.usage:
                tokens = getattr(resp.usage, "cache_creation_input_tokens", 0) or 0

            duration = (time.monotonic() - t0) * 1000
            return [WarmResult(agent_name="tools", tokens_cached=tokens, duration_ms=duration)]

        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.debug("Tool cache warm failed: %s", exc)
            return [WarmResult(agent_name="tools", duration_ms=duration, error=str(exc))]

    async def warm_all(self, agent_names: list[str] | None = None) -> list[WarmResult]:
        """Warm system prompts and tools concurrently."""
        sys_task = self.warm_system_prompts(agent_names)
        tools_task = self.warm_tools()
        sys_results, tool_results = await asyncio.gather(sys_task, tools_task)
        return list(sys_results) + list(tool_results)
