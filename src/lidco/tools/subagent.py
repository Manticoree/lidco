"""SubagentTool — agent forking via Task tool — Task 275.

Allows an agent to spawn a named sub-agent to handle a specific sub-task.
The parent agent receives the sub-agent's response as a tool result.

Usage in agent context::

    <tool_call>subagent</tool_call>
    {"agent_name": "security", "task": "review auth.py for SQL injection"}
"""

from __future__ import annotations

import logging
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


class SubagentTool(BaseTool):
    """Spawn a named sub-agent and return its response.

    The sub-agent runs synchronously within the parent's execution loop.
    Circular spawning (A → B → A) is detected and blocked.
    """

    _MAX_DEPTH = 3  # prevent deep recursion

    def __init__(self, session: Any) -> None:
        self._session = session
        self._depth = 0  # current nesting depth

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def description(self) -> str:
        return (
            "Spawn a named sub-agent to handle a specific sub-task. "
            "Returns the sub-agent's complete response. "
            "Use for delegation: security review, code generation, documentation."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="agent_name",
                type="string",
                description="Name of the agent to spawn (e.g. 'security', 'tester', 'coder')",
                required=True,
            ),
            ToolParameter(
                name="task",
                type="string",
                description="The task to delegate to the sub-agent",
                required=True,
            ),
            ToolParameter(
                name="context",
                type="string",
                description="Optional additional context for the sub-agent",
                required=False,
            ),
            ToolParameter(
                name="wait",
                type="boolean",
                description=(
                    "If True (default), run the sub-agent synchronously and return its output. "
                    "If False, submit to BackgroundTaskManager and return the task_id immediately."
                ),
                required=False,
            ),
            ToolParameter(
                name="context_passthrough",
                type="string",
                description=(
                    "Additional context injected directly into the sub-agent's system prompt "
                    "for this invocation only. Complements the 'context' parameter."
                ),
                required=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(
        self,
        agent_name: str,
        task: str,
        context: str = "",
        wait: bool = True,
        context_passthrough: str = "",
        **_: Any,
    ) -> ToolResult:
        if self._depth >= self._MAX_DEPTH:
            return ToolResult(
                output="",
                success=False,
                error=f"SubagentTool: max recursion depth {self._MAX_DEPTH} reached",
            )

        # Validate agent exists
        agent_registry = getattr(self._session, "agent_registry", None)
        if agent_registry and agent_registry.get(agent_name) is None:
            available = getattr(agent_registry, "list_names", lambda: [])()
            return ToolResult(
                output="",
                success=False,
                error=(
                    f"SubagentTool: agent '{agent_name}' not found. "
                    f"Available: {', '.join(available) or 'none'}"
                ),
            )

        # Build full context, merging context_passthrough
        full_context = context or ""
        if hasattr(self._session, "get_full_context"):
            base_ctx = self._session.get_full_context()
            if base_ctx and full_context:
                full_context = f"{full_context}\n\n{base_ctx}"
            elif base_ctx:
                full_context = base_ctx

        if context_passthrough:
            if full_context:
                full_context = f"{context_passthrough}\n\n{full_context}"
            else:
                full_context = context_passthrough

        # wait=False: fire-and-forget via BackgroundTaskManager
        if not wait:
            bg_mgr = getattr(self._session, "background_tasks", None)
            if bg_mgr is None:
                return ToolResult(
                    output="",
                    success=False,
                    error="SubagentTool: BackgroundTaskManager not available for wait=False",
                )
            task_id = bg_mgr.submit(task, self._session, agent_name=agent_name)
            return ToolResult(
                output=f"Background task submitted: task_id={task_id}",
                success=True,
                metadata={"task_id": task_id, "agent_name": agent_name},
            )

        self._depth += 1
        try:
            response = await self._session.orchestrator.handle(
                task,
                agent_name=agent_name,
                context=full_context,
            )
            content = response.content if hasattr(response, "content") else str(response)
            return ToolResult(output=content, success=True)

        except Exception as exc:
            return ToolResult(
                output="",
                success=False,
                error=f"SubagentTool: sub-agent '{agent_name}' failed: {exc}",
            )
        finally:
            self._depth -= 1
