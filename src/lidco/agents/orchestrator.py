"""Agent orchestrator - routes tasks to appropriate agents."""

from __future__ import annotations

import logging
from typing import Any

from lidco.agents.base import AgentResponse, BaseAgent
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import BaseLLMProvider, Message

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """\
Route to agent. Output name only. Default: coder.
plan/design→planner, review/audit→reviewer, debug/error/bug→debugger, else→coder.

Available agents:
{agents_description}
"""


class Orchestrator:
    """Routes user messages to the appropriate agent."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        agent_registry: AgentRegistry,
        default_agent: str = "coder",
        auto_plan: bool = True,
    ) -> None:
        self._llm = llm
        self._registry = agent_registry
        self._default_agent = default_agent
        self._auto_plan = auto_plan
        self._conversation_history: list[dict[str, str]] = []
        self._status_callback: Any | None = None
        self._permission_handler: Any | None = None
        self._token_callback: Any | None = None
        self._continue_handler: Any | None = None
        self._clarification_handler: Any | None = None
        self._stream_callback: Any | None = None
        self._tool_event_callback: Any | None = None
        # Cache the formatted router system prompt — agents don't change during a session
        self._router_system_cache: str | None = None

    def set_status_callback(self, callback: Any) -> None:
        """Set a callback to report status updates."""
        self._status_callback = callback

    def set_permission_handler(self, handler: Any) -> None:
        """Set a callback to check tool permissions. Propagated to agents."""
        self._permission_handler = handler

    def set_token_callback(self, callback: Any) -> None:
        """Set a callback to report token usage. Propagated to agents."""
        self._token_callback = callback

    def set_continue_handler(self, handler: Any) -> None:
        """Set a callback to ask user to continue at iteration limit."""
        self._continue_handler = handler

    def set_clarification_handler(self, handler: Any) -> None:
        """Set a callback to handle clarification questions. Propagated to agents."""
        self._clarification_handler = handler

    def set_stream_callback(self, callback: Any) -> None:
        """Set a callback to receive streaming text chunks. Propagated to agents."""
        self._stream_callback = callback

    def set_tool_event_callback(self, callback: Any) -> None:
        """Set a callback for tool call events. Propagated to agents."""
        self._tool_event_callback = callback

    def _report_status(self, status: str) -> None:
        if self._status_callback is not None:
            self._status_callback(status)

    def _get_router_system(self) -> str:
        """Return the formatted router system prompt, building it once and caching."""
        if self._router_system_cache is None:
            agents_desc = "\n".join(
                f"- {a.name}: {a.description}" for a in self._registry.list_agents()
            )
            self._router_system_cache = ROUTER_SYSTEM_PROMPT.format(
                agents_description=agents_desc
            )
        return self._router_system_cache

    async def route(self, user_message: str) -> str:
        """Determine which agent should handle this message."""
        if len(self._registry.list_agents()) <= 1:
            return self._default_agent

        response = await self._llm.complete(
            [
                Message(role="system", content=self._get_router_system()),
                Message(role="user", content=user_message),
            ],
            temperature=0.0,
            max_tokens=50,
            role="routing",
        )

        agent_name = response.content.strip().lower().strip('"\'.')
        if self._registry.get(agent_name):
            return agent_name

        logger.info("Router returned unknown agent '%s', using default.", agent_name)
        return self._default_agent

    def _propagate_callbacks(self, agent: BaseAgent) -> None:
        """Propagate all callbacks to an agent."""
        agent.set_status_callback(self._status_callback)
        agent.set_permission_handler(self._permission_handler)
        agent.set_token_callback(self._token_callback)
        agent.set_continue_handler(self._continue_handler)
        agent.set_clarification_handler(self._clarification_handler)
        agent.set_stream_callback(self._stream_callback)
        agent.set_tool_event_callback(self._tool_event_callback)

    async def _run_auto_planning(
        self, user_message: str, context: str
    ) -> tuple[str, bool]:
        """Run planner and ask user for approval.

        Returns (updated_context, approved).
        """
        planner = self._registry.get("planner")
        if not planner or not self._clarification_handler:
            return context, True

        self._report_status("Planning")
        self._propagate_callbacks(planner)

        try:
            plan_response = await planner.run(user_message, context=context)
        except Exception as e:
            logger.error("Planner failed: %s", e)
            return context, True

        import asyncio

        try:
            answer = await asyncio.get_running_loop().run_in_executor(
                None,
                self._clarification_handler,
                "Approve this plan?",
                ["Approve", "Reject", "Edit"],
                plan_response.content,
            )
        except Exception as e:
            logger.error("Plan approval failed: %s", e)
            return context, True

        answer_lower = answer.strip().lower()

        if answer_lower in ("reject", "n", "no"):
            return context, False

        plan_section = f"## Implementation Plan (approved)\n{plan_response.content}"
        if answer_lower not in ("approve", "y", "yes", ""):
            plan_section = (
                f"## Implementation Plan (edited by user)\n"
                f"{plan_response.content}\n\n"
                f"## User Edits\n{answer}"
            )

        merged = f"{plan_section}\n\n{context}" if context else plan_section
        return merged, True

    async def handle(
        self,
        user_message: str,
        *,
        agent_name: str | None = None,
        context: str = "",
    ) -> AgentResponse:
        """Handle a user message by routing to the appropriate agent."""
        explicit_agent = agent_name is not None
        if agent_name is None:
            agent_name = await self.route(user_message)

        agent = self._registry.get(agent_name)
        if not agent:
            agent = self._registry.get(self._default_agent)
        if not agent:
            return AgentResponse(
                content=f"No agent found for '{agent_name}'.",
                iterations=0,
            )

        logger.info("Routing to agent: %s", agent.name)
        self._propagate_callbacks(agent)

        # Build context from conversation history
        history_context = ""
        if self._conversation_history:
            recent = self._conversation_history[-5:]
            history_lines = [f"{m['role']}: {m['content'][:200]}" for m in recent]
            history_context = "\n".join(history_lines)

        full_context = context
        if history_context:
            full_context = f"## Conversation History\n{history_context}\n\n{context}"

        # Auto-planning: run planner before coder when routed (not explicit)
        if self._auto_plan and agent.name == "coder" and not explicit_agent:
            full_context, approved = await self._run_auto_planning(
                user_message, full_context,
            )
            if not approved:
                self._conversation_history.append({"role": "user", "content": user_message})
                self._conversation_history.append(
                    {"role": "assistant", "content": "Plan was rejected by user."}
                )
                return AgentResponse(
                    content="Plan was rejected. No changes were made.",
                    iterations=0,
                )

        response = await agent.run(user_message, context=full_context)

        # Save to history
        self._conversation_history.append({"role": "user", "content": user_message})
        self._conversation_history.append({"role": "assistant", "content": response.content})

        return response

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()
