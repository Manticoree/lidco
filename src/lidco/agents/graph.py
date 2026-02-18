"""LangGraph-based agent orchestration with state machine."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from lidco.agents.base import AgentResponse, BaseAgent
from lidco.agents.registry import AgentRegistry
from lidco.core.clarification import ClarificationManager, ClarificationNeeded
from lidco.llm.base import BaseLLMProvider, Message

logger = logging.getLogger(__name__)


MAX_REVIEW_ITERATIONS = 2


class GraphState(TypedDict, total=False):
    """State passed between nodes in the orchestration graph."""

    user_message: str
    context: str
    selected_agent: str
    agent_response: AgentResponse | None
    conversation_history: list[dict[str, str]]
    needs_review: bool
    review_response: AgentResponse | None
    error: str | None
    iteration: int
    clarification_context: str
    needs_planning: bool
    plan_response: AgentResponse | None
    plan_approved: bool
    review_iteration: int


ROUTER_PROMPT = """\
You are a task router. Select the best agent. Respond JSON: {{"agent": "<name>", "needs_review": bool, "needs_planning": bool}}

Available agents:
{agents}

needs_review=true for code modifications. needs_planning=true for new features, multi-file, architecture.
Rules: plan/design→planner, review/audit→reviewer, debug/error/bug→debugger, architecture→architect, test/coverage→tester, refactor/cleanup→refactor, docs/docstring/readme→docs, search/research/web→researcher, else→coder.
"""


class GraphOrchestrator:
    """LangGraph state machine for agent orchestration."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        agent_registry: AgentRegistry,
        default_agent: str = "coder",
        auto_review: bool = True,
        auto_plan: bool = True,
        max_review_iterations: int = MAX_REVIEW_ITERATIONS,
    ) -> None:
        self._llm = llm
        self._registry = agent_registry
        self._default_agent = default_agent
        self._auto_review = auto_review
        self._auto_plan = auto_plan
        self._max_review_iterations = max_review_iterations
        self._conversation_history: list[dict[str, str]] = []
        self._status_callback: Any | None = None
        self._permission_handler: Any | None = None
        self._token_callback: Any | None = None
        self._continue_handler: Any | None = None
        self._clarification_handler: Any | None = None
        self._stream_callback: Any | None = None
        self._tool_event_callback: Any | None = None
        self._clarification_mgr: ClarificationManager | None = None
        self._memory_store: Any | None = None
        # Cache the formatted router prompt — agents don't change during a session
        self._router_prompt_cache: str | None = None
        self._context_retriever: Any | None = None
        self._graph = self._build_graph()

    def set_status_callback(self, callback: Any) -> None:
        """Set a callback to report status updates (e.g., for UI timers)."""
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

    def set_clarification_manager(self, mgr: ClarificationManager) -> None:
        """Set the clarification manager for ambiguity analysis."""
        self._clarification_mgr = mgr

    def set_memory_store(self, store: Any) -> None:
        """Set the memory store for auto-extracting learnings."""
        self._memory_store = store

    def set_context_retriever(self, retriever: Any) -> None:
        """Set the RAG context retriever for code-aware context injection."""
        self._context_retriever = retriever

    def _report_status(self, status: str) -> None:
        if self._status_callback is not None:
            self._status_callback(status)

    def _get_router_prompt(self) -> str:
        """Return the formatted router prompt, building it once and caching."""
        if self._router_prompt_cache is None:
            agents = self._registry.list_agents()
            agents_desc = "\n".join(f"- {a.name}: {a.description}" for a in agents)
            self._router_prompt_cache = ROUTER_PROMPT.format(agents=agents_desc)
        return self._router_prompt_cache

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine."""
        graph = StateGraph(GraphState)

        # Add nodes
        graph.add_node("pre_analyze", self._pre_analyze_node)
        graph.add_node("route", self._route_node)
        graph.add_node("plan_gate", self._plan_gate_node)
        graph.add_node("execute_planner", self._execute_planner_node)
        graph.add_node("approve_plan", self._approve_plan_node)
        graph.add_node("execute_agent", self._execute_agent_node)
        graph.add_node("auto_review", self._auto_review_node)
        graph.add_node("finalize", self._finalize_node)

        # Set entry point
        graph.set_entry_point("pre_analyze")

        # Add edges
        graph.add_edge("pre_analyze", "route")
        graph.add_edge("route", "plan_gate")
        graph.add_conditional_edges(
            "plan_gate",
            self._needs_planning,
            {
                "plan": "execute_planner",
                "skip": "execute_agent",
            },
        )
        graph.add_edge("execute_planner", "approve_plan")
        graph.add_conditional_edges(
            "approve_plan",
            self._plan_approved,
            {
                "approved": "execute_agent",
                "rejected": "finalize",
            },
        )
        graph.add_conditional_edges(
            "execute_agent",
            self._should_review,
            {
                "review": "auto_review",
                "skip": "finalize",
            },
        )
        graph.add_conditional_edges(
            "auto_review",
            self._should_fix,
            {
                "fix": "execute_agent",
                "done": "finalize",
            },
        )
        graph.add_edge("finalize", END)

        return graph.compile()

    async def _pre_analyze_node(self, state: GraphState) -> GraphState:
        """Analyze the user message for ambiguity before routing."""
        if not self._clarification_mgr or not self._clarification_handler:
            return state

        self._report_status("Analyzing request")
        user_message = state["user_message"]

        try:
            questions = await self._clarification_mgr.analyze_ambiguity(
                user_message, self._llm,
            )
        except Exception as e:
            logger.debug("Pre-analysis failed: %s", e)
            return state

        if not questions:
            return state

        # Ask the user each question and collect answers
        import asyncio
        answers: list[str] = []
        for q in questions:
            answer = await asyncio.get_event_loop().run_in_executor(
                None,
                self._clarification_handler,
                q.question,
                q.options,
                q.context,
            )
            self._clarification_mgr.save_decision(
                question=q.question,
                answer=answer,
                context=q.context,
                agent="pre_analyze",
            )
            answers.append(f"- {q.question}: {answer}")

        clarification_text = "## User Clarifications\n" + "\n".join(answers)
        existing_context = state.get("context", "")
        merged_context = (
            f"{clarification_text}\n\n{existing_context}"
            if existing_context
            else clarification_text
        )

        return {**state, "context": merged_context, "clarification_context": clarification_text}

    async def _route_node(self, state: GraphState) -> GraphState:
        """Route the user message to the appropriate agent."""
        # Skip LLM routing if agent was explicitly pre-selected (e.g. @reviewer)
        if state.get("selected_agent"):
            return state

        self._report_status("Routing")
        user_message = state["user_message"]

        if len(self._registry.list_agents()) <= 1:
            return {
                **state,
                "selected_agent": self._default_agent,
                "needs_review": False,
            }

        prompt = self._get_router_prompt()

        response = await self._llm.complete(
            [
                Message(role="system", content=prompt),
                Message(role="user", content=user_message),
            ],
            temperature=0.0,
            max_tokens=100,
            role="routing",
        )

        raw = response.content.strip()
        agent_name = self._default_agent
        needs_review = False
        needs_planning = False

        # Try JSON first: {"agent": "coder", "needs_review": true, "needs_planning": true}
        try:
            # Extract JSON from possible markdown code blocks
            json_str = raw
            if "```" in json_str:
                json_str = json_str.split("```")[1].lstrip("json\n")
            if "{" in json_str:
                json_str = json_str[json_str.index("{"):json_str.rindex("}") + 1]
            result = json.loads(json_str)
            agent_name = result.get("agent", self._default_agent)
            needs_review = result.get("needs_review", False)
            needs_planning = result.get("needs_planning", False)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback: find a known agent name in the response
            available = {a.name for a in self._registry.list_agents()}
            for word in raw.lower().replace('"', "").replace("'", "").split():
                cleaned = word.strip(".,;:!?(){}[]")
                if cleaned in available:
                    agent_name = cleaned
                    break

        if not self._registry.get(agent_name):
            agent_name = self._default_agent

        return {
            **state,
            "selected_agent": agent_name,
            "needs_review": needs_review and self._auto_review,
            "needs_planning": needs_planning,
        }

    async def _execute_agent_node(self, state: GraphState) -> GraphState:
        """Execute the selected agent."""
        agent_name = state["selected_agent"]
        review_iter = state.get("review_iteration", 0)

        if review_iter > 0:
            self._report_status(f"Agent: {agent_name} (fixing review issues)")
        else:
            self._report_status(f"Agent: {agent_name}")

        agent = self._registry.get(agent_name)

        if not agent:
            return {
                **state,
                "agent_response": AgentResponse(
                    content=f"Agent '{agent_name}' not found.",
                    iterations=0,
                ),
                "error": f"Agent '{agent_name}' not found.",
            }

        # Build context
        context = state.get("context", "")
        history = state.get("conversation_history", [])
        if history:
            recent = history[-5:]
            history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)
            context = f"## Conversation History\n{history_text}\n\n{context}"

        # Inject RAG context (relevant code snippets from vector store)
        if self._context_retriever:
            try:
                rag_ctx = self._context_retriever.retrieve(
                    query=state["user_message"],
                    max_results=10,
                )
                if rag_ctx:
                    context = f"{rag_ctx}\n\n{context}"
            except Exception as e:
                logger.debug("RAG retrieval failed: %s", e)

        # Inject planner tool call summaries so coder knows what was explored
        plan_response = state.get("plan_response")
        if plan_response and plan_response.tool_calls_made:
            file_reads = [
                tc for tc in plan_response.tool_calls_made
                if tc.get("tool") in ("file_read", "grep", "glob")
            ]
            if file_reads:
                summary_lines = []
                for tc in file_reads[:15]:
                    args_str = ", ".join(f"{k}={v}" for k, v in tc.get("args", {}).items())
                    summary_lines.append(f"- {tc['tool']}({args_str})")
                planner_ctx = "## Planner Exploration Results\n" + "\n".join(summary_lines)
                context = f"{planner_ctx}\n\n{context}"

        # Inject review feedback when fixing issues (review loop)
        review = state.get("review_response")
        if review_iter > 0 and review:
            fix_prompt = (
                f"## Review Feedback (fix these issues)\n"
                f"{review.content}\n\n"
                f"Fix the CRITICAL and HIGH issues identified above."
            )
            context = f"{fix_prompt}\n\n{context}"

        logger.info("Executing agent: %s (review_iter=%d)", agent_name, review_iter)
        agent.set_status_callback(self._status_callback)
        agent.set_permission_handler(self._permission_handler)
        agent.set_token_callback(self._token_callback)
        agent.set_continue_handler(self._continue_handler)
        agent.set_clarification_handler(self._clarification_handler)
        agent.set_stream_callback(self._stream_callback)
        agent.set_tool_event_callback(self._tool_event_callback)

        message = state["user_message"]
        if review_iter > 0 and review:
            message = (
                f"{state['user_message']}\n\n"
                f"[REVIEW FEEDBACK - fix these issues]\n{review.content}"
            )

        try:
            response = await agent.run(message, context=context)
            return {**state, "agent_response": response, "error": None}
        except Exception as e:
            logger.error("Agent %s failed: %s", agent_name, e)
            return {
                **state,
                "agent_response": AgentResponse(
                    content=f"Agent error: {e}",
                    iterations=0,
                ),
                "error": str(e),
            }

    async def _plan_gate_node(self, state: GraphState) -> GraphState:
        """Pass-through node; routing is handled by _needs_planning."""
        return state

    def _needs_planning(self, state: GraphState) -> Literal["plan", "skip"]:
        """Decide whether to run planner before coder."""
        if (
            self._auto_plan
            and state.get("needs_planning")
            and state.get("selected_agent") == "coder"
            and self._registry.get("planner") is not None
        ):
            return "plan"
        return "skip"

    async def _execute_planner_node(self, state: GraphState) -> GraphState:
        """Run the planner agent to create an implementation plan."""
        self._report_status("Planning")
        planner = self._registry.get("planner")
        if not planner:
            logger.warning("Planner agent not found, skipping planning")
            return {**state, "plan_response": None, "plan_approved": True}

        # Propagate callbacks
        planner.set_status_callback(self._status_callback)
        planner.set_permission_handler(self._permission_handler)
        planner.set_token_callback(self._token_callback)
        planner.set_continue_handler(self._continue_handler)
        planner.set_clarification_handler(self._clarification_handler)
        planner.set_stream_callback(self._stream_callback)
        planner.set_tool_event_callback(self._tool_event_callback)

        context = state.get("context", "")
        try:
            plan_response = await planner.run(state["user_message"], context=context)
            return {**state, "plan_response": plan_response}
        except Exception as e:
            logger.error("Planner failed: %s", e)
            return {**state, "plan_response": None, "plan_approved": True}

    async def _approve_plan_node(self, state: GraphState) -> GraphState:
        """Ask the user to approve, reject, or edit the plan."""
        plan_response = state.get("plan_response")
        if not plan_response or not self._clarification_handler:
            return {**state, "plan_approved": True}

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
            return {**state, "plan_approved": True}

        answer_lower = answer.strip().lower()

        if answer_lower in ("approve", "y", "yes", ""):
            plan_context = f"## Implementation Plan (approved)\n{plan_response.content}"
            existing_context = state.get("context", "")
            merged = (
                f"{plan_context}\n\n{existing_context}" if existing_context else plan_context
            )
            return {**state, "plan_approved": True, "context": merged}

        if answer_lower in ("reject", "n", "no"):
            return {
                **state,
                "plan_approved": False,
                "agent_response": plan_response,
            }

        # "Edit" or custom text — treat as user edits to the plan
        plan_context = (
            f"## Implementation Plan (edited by user)\n"
            f"{plan_response.content}\n\n"
            f"## User Edits\n{answer}"
        )
        existing_context = state.get("context", "")
        merged = (
            f"{plan_context}\n\n{existing_context}" if existing_context else plan_context
        )
        return {**state, "plan_approved": True, "context": merged}

    def _plan_approved(self, state: GraphState) -> Literal["approved", "rejected"]:
        """Route based on plan approval status."""
        if state.get("plan_approved", True):
            return "approved"
        return "rejected"

    def _should_review(self, state: GraphState) -> Literal["review", "skip"]:
        """Decide whether to run auto-review."""
        if state.get("needs_review") and state.get("agent_response"):
            response = state["agent_response"]
            # Only review if the agent made tool calls (i.e. modified something)
            if response.tool_calls_made:
                return "review"
        return "skip"

    async def _auto_review_node(self, state: GraphState) -> GraphState:
        """Automatically review code changes."""
        review_iter = state.get("review_iteration", 0) + 1
        self._report_status(f"Reviewing (pass {review_iter})")
        reviewer = self._registry.get("reviewer")
        if not reviewer:
            return {**state, "review_iteration": review_iter}

        reviewer.set_status_callback(self._status_callback)
        reviewer.set_permission_handler(self._permission_handler)
        reviewer.set_token_callback(self._token_callback)
        # Don't pass stream_callback to reviewer — saves narration prompt tokens

        agent_response = state.get("agent_response")
        if not agent_response:
            return {**state, "review_iteration": review_iter}

        # Build review context
        tool_calls_summary = "\n".join(
            f"- {tc['tool']}({', '.join(f'{k}={v}' for k, v in tc['args'].items())})"
            for tc in agent_response.tool_calls_made[:20]
        )

        review_prompt = (
            f"Review the following changes made by the {state['selected_agent']} agent:\n\n"
            f"Original request: {state['user_message']}\n\n"
            f"Tool calls made:\n{tool_calls_summary}\n\n"
            f"Agent response:\n{agent_response.content[:2000]}\n\n"
            "Provide a brief review focusing on CRITICAL and HIGH issues only.\n"
            "If there are no CRITICAL or HIGH issues, start your response with: NO_ISSUES_FOUND"
        )

        try:
            review = await reviewer.run(review_prompt)
            return {**state, "review_response": review, "review_iteration": review_iter}
        except Exception as e:
            logger.warning("Auto-review failed: %s", e)
            return {**state, "review_iteration": review_iter}

    def _should_fix(self, state: GraphState) -> Literal["fix", "done"]:
        """Decide whether to send code back for fixes based on review."""
        review = state.get("review_response")
        review_iter = state.get("review_iteration", 0)

        # No review or max iterations reached → done
        if not review or review_iter >= self._max_review_iterations:
            return "done"

        # If reviewer explicitly said no issues → done
        content = review.content.strip()
        if content.startswith("NO_ISSUES_FOUND"):
            return "done"

        # Check for CRITICAL or HIGH severity markers
        content_upper = content.upper()
        if "CRITICAL" in content_upper or "HIGH" in content_upper:
            return "fix"

        return "done"

    async def _finalize_node(self, state: GraphState) -> GraphState:
        """Finalize the response, optionally extracting learnings to memory."""
        if self._memory_store and state.get("agent_response"):
            await self._extract_memory(state)

        # Update RAG index for any files modified during this run
        if self._context_retriever and state.get("agent_response"):
            self._update_rag_index(state)

        return state

    def _update_rag_index(self, state: GraphState) -> None:
        """Re-index files that were written or edited during agent execution."""
        response = state.get("agent_response")
        if not response or not response.tool_calls_made:
            return

        modified_files: set[str] = set()
        for tc in response.tool_calls_made:
            tool_name = tc.get("tool", "")
            if tool_name in ("file_write", "file_edit"):
                file_path = tc.get("args", {}).get("path", "")
                if file_path:
                    modified_files.add(file_path)

        for file_path in modified_files:
            try:
                from pathlib import Path
                self._context_retriever.update_file(Path(file_path))
                logger.debug("Updated RAG index for: %s", file_path)
            except Exception as e:
                logger.debug("RAG index update failed for %s: %s", file_path, e)

    async def _extract_memory(self, state: GraphState) -> None:
        """Extract key learnings from agent response and save to memory."""
        response = state.get("agent_response")
        if not response or not response.tool_calls_made:
            return

        # Skip memory extraction for read-only tasks (no file modifications)
        write_tools = {"file_write", "file_edit"}
        has_writes = any(
            tc.get("tool") in write_tools for tc in response.tool_calls_made
        )
        if not has_writes:
            return

        prompt = (
            "Analyze the following task and response. Extract 0-2 reusable learnings "
            "worth remembering for future tasks. Only extract genuinely useful patterns, "
            "decisions, or solutions — not task-specific details.\n\n"
            "Return JSON array (empty if nothing worth saving):\n"
            '[{"key": "short-id", "content": "what was learned", "category": "pattern|decision|solution"}]\n\n'
            f"Task: {state['user_message'][:500]}\n"
            f"Agent: {state['selected_agent']}\n"
            f"Response summary: {response.content[:1000]}"
        )

        try:
            llm_response = await self._llm.complete(
                [Message(role="user", content=prompt)],
                temperature=0.0,
                max_tokens=150,
                role="memory_extraction",
            )

            raw = llm_response.content.strip()
            # Extract JSON from possible markdown
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json\n")
            if "[" in raw:
                raw = raw[raw.index("["):raw.rindex("]") + 1]

            entries = json.loads(raw)
            if not isinstance(entries, list):
                return

            for entry in entries[:2]:
                key = entry.get("key", "")
                content = entry.get("content", "")
                category = entry.get("category", "general")
                if key and content:
                    self._memory_store.add(
                        key=key,
                        content=content,
                        category=category,
                        tags=["auto-extracted"],
                        source=f"agent:{state['selected_agent']}",
                    )
                    logger.info("Auto-extracted memory: %s", key)
        except Exception as e:
            logger.debug("Memory extraction failed (non-critical): %s", e)

    async def handle(
        self,
        user_message: str,
        *,
        agent_name: str | None = None,
        context: str = "",
    ) -> AgentResponse:
        """Handle a user message through the graph."""
        initial_state: GraphState = {
            "user_message": user_message,
            "context": context,
            "selected_agent": agent_name or "",
            "agent_response": None,
            "conversation_history": list(self._conversation_history),
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 0,
        }

        result = await self._graph.ainvoke(initial_state)

        response = result.get("agent_response") or AgentResponse(
            content="No response generated.", iterations=0
        )

        # Append review if available
        review = result.get("review_response")
        if review and review.content:
            response = AgentResponse(
                content=f"{response.content}\n\n---\n**Auto-Review:**\n{review.content}",
                tool_calls_made=response.tool_calls_made,
                iterations=response.iterations,
                model_used=response.model_used,
            )

        # Update history
        self._conversation_history.append({"role": "user", "content": user_message})
        self._conversation_history.append({"role": "assistant", "content": response.content})

        return response

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()
