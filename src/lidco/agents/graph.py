"""LangGraph-based agent orchestration with state machine."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from lidco.agents.base import AgentResponse, BaseAgent, TokenUsage
from lidco.agents.orchestrator import BaseOrchestrator
from lidco.agents.registry import AgentRegistry
from lidco.core.clarification import ClarificationManager, ClarificationNeeded
from lidco.llm.base import BaseLLMProvider, Message

logger = logging.getLogger(__name__)


MAX_REVIEW_ITERATIONS = 2

# Agents that benefit from a planning phase before execution.
# Reviewer, researcher, and docs agents work well without upfront planning.
_PLANNING_AGENTS = frozenset({"coder", "architect", "tester", "refactor", "debugger", "profiler", "security"})

# Required sections that a complete implementation plan must contain.
# Used by _check_plan_sections() to surface structural gaps early.
_REQUIRED_PLAN_SECTIONS: tuple[tuple[str, str], ...] = (
    ("**Goal:**", "Goal"),
    ("**Assumptions:**", "Assumptions"),
    ("**Steps:**", "Steps"),
    ("**Risk Assessment:**", "Risk Assessment"),
    ("**Test Impact:**", "Test Impact"),
)


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
    force_plan: bool  # When True, always run planner regardless of router decision
    accumulated_tokens: int  # Sum of total_tokens across all agents in this run
    accumulated_cost_usd: float  # Sum of costs across all agents in this run
    medium_issues: str  # MEDIUM severity issues from reviewer (advisory, non-blocking)
    parallel_steps: list[str]  # Step descriptions marked [PARALLEL] in the approved plan
    plan_critique: str | None  # Auto-generated critique appended to plan before approval
    plan_critique_addressed: str | None  # Critique text that was addressed by last revision
    plan_revision: str | None  # Revised plan content produced after critique feedback
    plan_assumptions: list[str]  # Assumption lines extracted from **Assumptions:** section
    plan_revision_round: int  # Counts extra re-critique/revise rounds that have run
    execution_map: dict | None  # Parsed **Execution Map:** section from approved plan
    plan_step_deps: dict | None  # {step_num: [dep_nums]} parsed from Deps: lines
    plan_bad_assumptions: list[str]  # Assumption texts that failed verification
    plan_section_issues: list[str]  # Required section names absent from the plan
    plan_health_score: int  # 0–100 quality score emitted before user approval


_CRITIQUE_SYSTEM_PROMPT = """\
You are a technical plan reviewer. Analyze the implementation plan for gaps.

Check each category below and report the N most critical issues (max 5 total), \
ordered by severity. Skip categories with no issues.

Categories:
1. Missing edge cases / error handling — inputs, timeouts, partial failures
2. Breaking changes — callers or dependents of changed interfaces not listed
3. Untested logic — new code paths with no corresponding test coverage
4. Dependency ordering — steps that implicitly depend on prior steps but aren't marked
5. Over-engineering — unnecessarily complex steps that could be simplified
6. Security — user input, authentication, authorization, or sensitive data affected
7. Performance — loops, I/O, or DB queries on hot paths affected by the changes
8. Plan coverage — does the plan fully address the original request? \
   Call out anything the user asked for that the plan doesn't handle.
9. Step decomposition — steps that bundle multiple unrelated changes into one, \
   or that lack a clear Files/Verify/Deps structure.

Format each issue on its own line:
**[Category]** `file.py:symbol()` — what is wrong and why it matters.

If the plan has no significant issues, reply with: "No critical gaps identified."
"""

_REVISE_SYSTEM_PROMPT = """\
You are LIDCO Planner revising your own plan based on a technical review.

Rules:
- Do NOT re-explore the codebase — use your prior knowledge from the planning phase
- Address EVERY critique point: either fix the plan or explain (briefly) why it \
  does not apply to this specific task
- Challenge every [⚠ Unverified] assumption in the **Assumptions:** section: \
  either confirm it with reasoning from your exploration or update the plan to \
  eliminate the dependency on the unverified assumption
- Keep the exact same output format as the original plan (## Implementation Plan \
  with all required sections: Goal, Assumptions, Reasoning & Approach, Chain of \
  Thought, Alternative Considered, Steps, Dependencies, Risk Assessment, Test \
  Impact, Callers/Dependents, Risks & Decisions, Clarifications)
- Add a final "## Addressed Critique" section mapping each flagged issue to your fix \
  or your reason for dismissal
- Ensure all revised steps follow the decomposition format: \
  Files (specific paths), Action (what exactly), Verify (done criterion), Deps (step numbers or "none")
- Do not pad with unnecessary words — be precise and actionable
"""

_RE_CRITIQUE_SYSTEM_PROMPT = """\
You are a technical plan reviewer performing a follow-up review after plan revision.

Your task is NOT to find new issues. Your task is to verify whether each point from \
the original critique was addressed in the revised plan.

For each original critique point:
- If fully addressed: skip it entirely — do not mention it
- If partially addressed: report what is still missing
- If not addressed at all: repeat the issue prefixed with "[UNRESOLVED]"

Only report issues that remain unresolved or are only partially resolved.
If all original critique points were addressed, reply with: "All critique points addressed."

Format each remaining issue on its own line:
**[Category]** `file.py:symbol()` — what remains unresolved and why it matters.
"""

ROUTER_PROMPT = """\
You are a task router. Select the best agent. Respond JSON: {{"agent": "<name>", "needs_review": bool, "needs_planning": bool}}

Available agents:
{agents}

needs_review=true for code modifications. needs_planning=true for new features, multi-file, architecture.
Rules: plan/design→planner, review/audit→reviewer, debug/error/bug/traceback/exception/attributeerror/typeerror/importerror/keyerror/stack trace→debugger, architecture→architect, test/coverage→tester, refactor/cleanup→refactor, docs/docstring/readme→docs, search/research/web→researcher, validate/qa/check compilation/run tests after feature→qa, profile/performance/hotspot/slow/optimize speed→profiler, explain/what does/how does/walk me through/describe→explain, security/vulnerability/owasp/injection/xss/csrf/secrets/pentest→security, implement/create/write/add/build→coder, else→coder.
"""


class GraphOrchestrator(BaseOrchestrator):
    """LangGraph state machine for agent orchestration."""

    # Maximum context chars passed to any single agent to prevent prompt overflow.
    # Content is preserved from the top (newest injections); tail is truncated.
    _MAX_CONTEXT_CHARS = 100_000

    def __init__(
        self,
        llm: BaseLLMProvider,
        agent_registry: AgentRegistry,
        default_agent: str = "coder",
        auto_review: bool = True,
        auto_plan: bool = True,
        max_review_iterations: int = MAX_REVIEW_ITERATIONS,
        agent_timeout: int = 300,
        max_parallel_agents: int = 3,
        project_dir: Path | None = None,
    ) -> None:
        self._llm = llm
        self._registry = agent_registry
        self._default_agent = default_agent
        self._auto_review = auto_review
        self._auto_plan = auto_plan
        self._max_review_iterations = max_review_iterations
        self._agent_timeout = agent_timeout
        self._max_parallel_agents = max_parallel_agents
        self._project_dir: Path = project_dir or Path.cwd()
        self._conversation_history: list[dict[str, str]] = []
        self._status_callback: Any | None = None
        self._permission_handler: Any | None = None
        self._token_callback: Any | None = None
        self._continue_handler: Any | None = None
        self._clarification_handler: Any | None = None
        self._stream_callback: Any | None = None
        self._tool_event_callback: Any | None = None
        self._error_callback: Any | None = None
        self._clarification_mgr: ClarificationManager | None = None
        self._memory_store: Any | None = None
        # Cache the formatted router prompt — agents don't change during a session
        self._router_prompt_cache: str | None = None
        self._context_retriever: Any | None = None
        self._phase_callback: Any | None = None
        self._plan_editor: Any | None = None
        # Callable[[], str] — returns failure-site snippets for debugger injection
        self._error_context_builder: Any | None = None
        # Callable[[], int] — returns current error count for auto-debug suggestion
        self._error_count_reader: Any | None = None
        # Callable[[], str] — returns compact error summary for planning agents
        self._error_summary_builder: Any | None = None
        # When True, inject compact error context into non-debugger planning agents
        self._debug_mode: bool = False
        # When True, run a cheap LLM critique pass on the plan before approval
        self._plan_critique_enabled: bool = True
        # When True, run a planner revision pass after critique before approval
        self._plan_revise_enabled: bool = True
        # Number of extra re-critique/revise rounds after the initial revision (0 = none)
        self._plan_max_revisions: int = 1
        # When True, save/retrieve approved plans to/from memory for warm-start
        self._plan_memory_enabled: bool = True
        # When True, auto-inject git log + coverage snapshot before planner starts
        self._preplan_snapshot_enabled: bool = True
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

    def set_error_callback(self, callback: Any) -> None:
        """Set a callback fired on every tool failure. Propagated to agents."""
        self._error_callback = callback

    def set_clarification_manager(self, mgr: ClarificationManager) -> None:
        """Set the clarification manager for ambiguity analysis."""
        self._clarification_mgr = mgr

    def set_memory_store(self, store: Any) -> None:
        """Set the memory store for auto-extracting learnings."""
        self._memory_store = store

    def set_context_retriever(self, retriever: Any) -> None:
        """Set the RAG context retriever for code-aware context injection."""
        self._context_retriever = retriever

    def set_phase_callback(self, callback: Any) -> None:
        """Set a callback to receive phase transitions (name, status)."""
        self._phase_callback = callback

    def set_plan_editor(self, editor: Any) -> None:
        """Set an interactive plan editor callback ``(plan_text) -> str | None``.

        When set, ``_approve_plan_node`` calls this instead of the standard
        clarification-handler approve/reject flow, enabling step-level editing.
        """
        self._plan_editor = editor

    def set_error_context_builder(self, fn: Any) -> None:
        """Set a callable ``() -> str`` that returns failure-site snippets.

        When set, the snippets are prepended to the debugger agent's system
        prompt via ``prepend_system_context`` so it can see the failing code
        without an extra tool call.
        """
        self._error_context_builder = fn

    def set_error_count_reader(self, fn: Any) -> None:
        """Set a callable ``() -> int`` that returns the current error count.

        Used by ``handle()`` to detect whether 2+ tool failures occurred during
        a run and append a debug suggestion to the response.
        """
        self._error_count_reader = fn

    def set_error_summary_builder(self, fn: Any) -> None:
        """Set a callable ``() -> str`` returning a compact error context string.

        When debug mode is active, this is called in ``_execute_agent_node`` to
        inject a brief error advisory into non-debugger planning agents so they
        can avoid repeating patterns that caused recent failures.
        """
        self._error_summary_builder = fn

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable or disable debug context injection for planning agents.

        When *enabled*, each non-debugger planning agent (coder, tester,
        refactor, etc.) receives a compact ``## Active Debug Context`` section
        in its system prompt containing recent error summaries.
        """
        self._debug_mode = enabled

    def set_plan_critique(self, enabled: bool) -> None:
        """Enable or disable the automatic plan critique pass.

        When *enabled* (default), a cheap LLM call annotates the plan with
        identified risks and gaps before the user sees it for approval.
        Disable via ``config.agents.plan_critique = false`` for faster planning.
        """
        self._plan_critique_enabled = enabled

    def set_plan_revise(self, enabled: bool) -> None:
        """Enable or disable the planner revision pass after critique.

        When *enabled* (default), the planner model sees the critique and rewrites
        the plan to address identified gaps before the user approves it.
        Disable via ``config.agents.plan_revise = false`` to skip the revision step.
        """
        self._plan_revise_enabled = enabled

    def set_plan_max_revisions(self, n: int) -> None:
        """Set the maximum number of extra re-critique/revise rounds after the
        initial revision.  0 = no extra rounds (one-shot critique + revise only).
        """
        self._plan_max_revisions = max(0, n)

    def set_plan_memory(self, enabled: bool) -> None:
        """Enable or disable saving/retrieving approved plans to/from memory.

        When *enabled* (default), the orchestrator retrieves similar past plans
        before the planner starts and saves the approved plan after approval.
        """
        self._plan_memory_enabled = enabled

    def set_preplan_snapshot(self, enabled: bool) -> None:
        """Enable or disable the pre-planning context snapshot.

        When *enabled* (default), git log and coverage data for files mentioned
        in the user request are injected into the planner's context before it
        starts, reducing redundant tool calls during Phase 2 exploration.
        """
        self._preplan_snapshot_enabled = enabled

    # --- Live-reloadable config setters (override BaseOrchestrator no-ops) ---

    def set_agent_timeout(self, timeout: int) -> None:
        self._agent_timeout = timeout

    def set_auto_plan(self, enabled: bool) -> None:
        self._auto_plan = enabled

    def set_auto_review(self, enabled: bool) -> None:
        self._auto_review = enabled

    def set_max_review_iterations(self, n: int) -> None:
        self._max_review_iterations = n

    def set_default_agent(self, name: str) -> None:
        self._default_agent = name

    def _report_status(self, status: str) -> None:
        if self._status_callback is not None:
            self._status_callback(status)

    def _report_phase(self, name: str, phase_status: str) -> None:
        if self._phase_callback is not None:
            self._phase_callback(name, phase_status)

    def _get_router_prompt(self) -> str:
        """Return the formatted router prompt, building it once and caching.

        If any registered agents have ``routing_keywords``, an extra line is
        appended so the LLM routes those keywords to the correct agent.
        """
        if self._router_prompt_cache is None:
            agents = self._registry.list_agents()
            agents_desc = "\n".join(f"- {a.name}: {a.description}" for a in agents)
            prompt = ROUTER_PROMPT.format(agents=agents_desc)

            # Inject routing keywords from custom (or keyword-bearing) agents.
            # Inserted BEFORE built-in rules so custom keywords take priority when
            # they conflict with a built-in keyword (e.g. a custom agent with
            # routing_keywords=["debug"] overrides the debugger route).
            custom_rules = [
                f"{'/'.join(a.config.routing_keywords)}->{a.name}"
                for a in agents
                if a.config.routing_keywords
            ]
            if custom_rules:
                custom_str = "Custom rules (highest priority): " + ", ".join(custom_rules) + "."
                prompt = prompt.replace("Rules: ", f"{custom_str}\nRules: ")

            self._router_prompt_cache = prompt
        return self._router_prompt_cache

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine."""
        graph = StateGraph(GraphState)

        # Add nodes
        graph.add_node("pre_analyze", self._pre_analyze_node)
        graph.add_node("route", self._route_node)
        graph.add_node("plan_gate", self._plan_gate_node)
        graph.add_node("execute_planner", self._execute_planner_node)
        graph.add_node("critique_plan", self._critique_plan_node)
        graph.add_node("revise_plan", self._revise_plan_node)
        graph.add_node("re_critique_plan", self._re_critique_plan_node)
        graph.add_node("verify_assumptions", self._verify_assumptions_node)
        graph.add_node("approve_plan", self._approve_plan_node)
        graph.add_node("execute_agent", self._execute_agent_node)
        graph.add_node("execute_parallel", self._execute_parallel_node)
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
        graph.add_edge("execute_planner", "critique_plan")
        graph.add_edge("critique_plan", "revise_plan")
        # After initial revision, optionally run more critique/revise rounds
        graph.add_edge("revise_plan", "re_critique_plan")
        graph.add_conditional_edges(
            "re_critique_plan",
            self._should_revise_again,
            {
                "revise": "revise_plan",
                "done": "verify_assumptions",
            },
        )
        graph.add_edge("verify_assumptions", "approve_plan")
        graph.add_conditional_edges(
            "approve_plan",
            self._plan_approved,
            {
                "parallel": "execute_parallel",
                "sequential": "execute_agent",
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
            "execute_parallel",
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
        loop = asyncio.get_running_loop()
        answers: list[str] = []
        for q in questions:
            answer = await loop.run_in_executor(
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

        self._report_status("Selecting best agent")
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

        raw = (response.content or "").strip()
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
            logger.warning("Router returned non-JSON: %r — scanning for agent name", raw[:120])
            available = {a.name for a in self._registry.list_agents()}
            for word in raw.lower().replace('"', "").replace("'", "").split():
                cleaned = word.strip(".,;:!?(){}[]")
                if cleaned in available:
                    agent_name = cleaned
                    break

        if not self._registry.get(agent_name):
            logger.warning("Router selected unknown agent %r, falling back to %r", agent_name, self._default_agent)
            agent_name = self._default_agent

        # force_plan (e.g. from /plan command) always enables planning
        final_needs_planning = needs_planning or state.get("force_plan", False)

        return {
            **state,
            "selected_agent": agent_name,
            "needs_review": needs_review and self._auto_review,
            "needs_planning": final_needs_planning,
        }

    async def _execute_agent_node(self, state: GraphState) -> GraphState:
        """Execute the selected agent."""
        agent_name = state["selected_agent"]
        review_iter = state.get("review_iteration", 0)

        if review_iter > 0:
            self._report_status(f"Fixing issues ({agent_name})")
            self._report_phase("Fix", "active")
        else:
            self._report_status(f"Starting {agent_name}")
            self._report_phase("Execute", "active")

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

        # ── Build context in two layers: critical and advisory ───────────────
        # CRITICAL sections are always preserved (plan, review feedback).
        # ADVISORY sections (history, RAG, base context) are truncated first
        # when the total context exceeds _MAX_CONTEXT_CHARS.
        critical_parts: list[str] = []
        advisory_parts: list[str] = []

        # Critical: review feedback when fixing issues (review loop)
        review = state.get("review_response")
        if review_iter > 0 and review:
            medium_advisory = state.get("medium_issues", "")
            advisory_note = (
                f"\n\nAlso consider (non-blocking, no fix required):\n{medium_advisory}"
                if medium_advisory else ""
            )
            fix_prompt = (
                f"## Review Feedback (fix these issues)\n"
                f"{review.content}\n\n"
                f"Fix the CRITICAL and HIGH issues identified above.{advisory_note}"
            )
            critical_parts.append(fix_prompt)

        # Critical: planner exploration results with findings
        plan_response = state.get("plan_response")
        if plan_response and plan_response.tool_calls_made:
            file_reads = [
                tc for tc in plan_response.tool_calls_made
                if tc.get("tool") in ("file_read", "grep", "glob")
            ]
            if file_reads:
                total = len(file_reads)
                summary_lines = []
                for tc in file_reads[:15]:
                    args_str = ", ".join(f"{k}={v}" for k, v in tc.get("args", {}).items())
                    preview = tc.get("result_preview", "")
                    if preview:
                        first_line = preview.split("\n")[0][:120].strip()
                        summary_lines.append(f"- {tc['tool']}({args_str})\n  → {first_line}")
                    else:
                        summary_lines.append(f"- {tc['tool']}({args_str})")
                header = (
                    f"## Planner Exploration Results ({total} files explored"
                    + (", showing 15)" if total > 15 else ")")
                )
                critical_parts.append(header + "\n" + "\n".join(summary_lines))

        # Advisory: conversation history
        history = state.get("conversation_history", [])
        if history:
            recent = history[-5:]
            history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)
            advisory_parts.append(f"## Conversation History\n{history_text}")

        # Advisory: RAG context (relevant code snippets from vector store)
        if self._context_retriever:
            try:
                rag_ctx = self._context_retriever.retrieve(
                    query=state["user_message"],
                    max_results=10,
                )
                if rag_ctx:
                    advisory_parts.append(rag_ctx)
            except Exception as e:
                logger.debug("RAG retrieval failed: %s", e)

        # Advisory: base context (project structure, memory, decisions)
        base_context = state.get("context", "")
        if base_context:
            advisory_parts.append(base_context)

        # Combine with smart truncation
        critical_text = "\n\n".join(critical_parts)
        advisory_text = "\n\n".join(advisory_parts)
        available_for_advisory = self._MAX_CONTEXT_CHARS - len(critical_text)

        if available_for_advisory <= 0:
            logger.warning(
                "Critical context (%d chars) exceeds limit for agent %s — truncating",
                len(critical_text), agent_name,
            )
            context = critical_text[: self._MAX_CONTEXT_CHARS] + "\n\n[... context truncated ...]"
        elif len(advisory_text) > available_for_advisory:
            logger.warning(
                "Advisory context trimmed from %d to %d chars for agent %s",
                len(advisory_text), available_for_advisory, agent_name,
            )
            advisory_text = (
                advisory_text[:available_for_advisory] + "\n\n[... advisory context truncated ...]"
            )
            context = f"{critical_text}\n\n{advisory_text}" if critical_text else advisory_text
        else:
            context = f"{critical_text}\n\n{advisory_text}" if critical_text else advisory_text

        logger.info("Executing agent: %s (review_iter=%d)", agent_name, review_iter)
        agent.set_status_callback(self._status_callback)
        agent.set_permission_handler(self._permission_handler)
        agent.set_token_callback(self._token_callback)
        agent.set_continue_handler(self._continue_handler)
        agent.set_clarification_handler(self._clarification_handler)
        agent.set_stream_callback(self._stream_callback)
        agent.set_tool_event_callback(self._tool_event_callback)
        agent.set_error_callback(self._error_callback)

        # Inject failure-site snippets into the debugger's context so it can
        # see the failing code without needing an extra file_read tool call.
        if agent.config.name == "debugger" and self._error_context_builder is not None:
            snippets = self._error_context_builder()
            if snippets:
                agent.prepend_system_context(snippets)

        # In debug mode, inject a compact error advisory into non-debugger
        # planning agents so they can avoid repeating failing patterns.
        if (
            self._debug_mode
            and agent.config.name != "debugger"
            and agent.config.name in _PLANNING_AGENTS
            and self._error_summary_builder is not None
        ):
            summary = self._error_summary_builder()
            if summary:
                agent.prepend_system_context(
                    "## Active Debug Context\n\n"
                    "Debug mode is active. Recent tool failures are listed below — "
                    "avoid patterns that triggered these errors.\n\n"
                    + summary
                )

        message = state["user_message"]
        if review_iter > 0 and review:
            message = (
                f"{state['user_message']}\n\n"
                f"[REVIEW FEEDBACK - fix these issues]\n{review.content}"
            )

        timeout = self._agent_timeout if self._agent_timeout > 0 else None
        phase_name = "Fix" if review_iter > 0 else "Execute"
        try:
            response = await asyncio.wait_for(
                agent.run(message, context=context),
                timeout=timeout,
            )
            self._report_phase(phase_name, "done")
            return {
                **state,
                "agent_response": response,
                "error": None,
                "accumulated_tokens": state.get("accumulated_tokens", 0) + response.token_usage.total_tokens,
                "accumulated_cost_usd": state.get("accumulated_cost_usd", 0.0) + response.token_usage.total_cost_usd,
            }
        except asyncio.TimeoutError:
            logger.error("Agent %s timed out after %ss", agent_name, timeout)
            self._report_phase(phase_name, "done")
            return {
                **state,
                "agent_response": AgentResponse(
                    content=f"Agent '{agent_name}' timed out after {timeout}s. Try breaking the task into smaller steps.",
                    iterations=0,
                ),
                "error": f"timeout after {timeout}s",
            }
        except Exception as e:
            logger.error("Agent %s failed: %s", agent_name, e)
            self._report_phase(phase_name, "done")
            return {
                **state,
                "agent_response": AgentResponse(
                    content=f"Agent error: {e}",
                    iterations=0,
                ),
                "error": str(e),
            }

    async def _execute_parallel_node(self, state: GraphState) -> GraphState:
        """Execute parallel plan steps using dependency-aware wave scheduling.

        Steps are grouped into *waves* using ``_build_dep_waves``: within each
        wave all steps can run concurrently (``asyncio.gather``); the next wave
        starts only after every step in the current wave has finished.

        When ``plan_step_deps`` is absent or empty the node falls back to the
        original single-gather behaviour (all steps at once).

        A semaphore caps concurrent invocations at ``_max_parallel_agents``.
        Results are merged into a single ``AgentResponse`` before returning.
        """
        parallel_steps = state.get("parallel_steps") or []
        agent_name = state["selected_agent"]
        plan_step_deps = state.get("plan_step_deps") or {}

        # Re-parse all step descriptions to build the description→number mapping
        # needed by _build_dep_waves.  plan_response is always present when we
        # reach this node (approved plan path), but guard defensively.
        plan_response = state.get("plan_response")
        if plan_response and plan_response.content:
            from lidco.cli.plan_editor import parse_plan_steps  # local: avoid circular
            all_steps = parse_plan_steps(plan_response.content)
        else:
            all_steps = []

        waves = self._build_dep_waves(parallel_steps, plan_step_deps, all_steps)
        if not waves:
            waves = [list(parallel_steps)]  # defensive fallback

        n = len(parallel_steps)
        n_waves = len(waves)
        if n_waves > 1:
            self._report_status(
                f"Running {n} steps in {n_waves} dependency waves ({agent_name})"
            )
        else:
            self._report_status(f"Running {n} steps in parallel ({agent_name})")
        self._report_phase("Execute", "active")

        template_agent = self._registry.get(agent_name)
        if not template_agent:
            self._report_phase("Execute", "done")
            return {
                **state,
                "agent_response": AgentResponse(
                    content=f"Agent '{agent_name}' not found.",
                    iterations=0,
                ),
                "error": f"Agent '{agent_name}' not found.",
            }

        # Build shared context (same advisory layers as execute_agent, minus fix prompt)
        advisory_parts: list[str] = []
        history = state.get("conversation_history", [])
        if history:
            recent = history[-5:]
            history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)
            advisory_parts.append(f"## Conversation History\n{history_text}")
        if self._context_retriever:
            try:
                rag_ctx = self._context_retriever.retrieve(
                    query=state["user_message"],
                    max_results=10,
                )
                if rag_ctx:
                    advisory_parts.append(rag_ctx)
            except Exception as e:
                logger.debug("RAG retrieval failed in parallel node: %s", e)
        base_context = state.get("context", "")
        if base_context:
            advisory_parts.append(base_context)
        shared_context = "\n\n".join(advisory_parts)

        semaphore = asyncio.Semaphore(max(1, self._max_parallel_agents))
        timeout = self._agent_timeout if self._agent_timeout > 0 else None

        async def _run_step(step_desc: str) -> AgentResponse:
            async with semaphore:
                # Create a fresh agent instance to avoid shared _conversation state
                fresh = template_agent.clone()
                fresh.set_status_callback(self._status_callback)
                fresh.set_permission_handler(self._permission_handler)
                fresh.set_token_callback(self._token_callback)
                fresh.set_continue_handler(self._continue_handler)
                fresh.set_clarification_handler(self._clarification_handler)
                fresh.set_stream_callback(self._stream_callback)
                fresh.set_tool_event_callback(self._tool_event_callback)
                fresh.set_error_callback(self._error_callback)

                # Mirror debug context injection from _execute_agent_node
                if fresh.config.name == "debugger" and self._error_context_builder is not None:
                    snippets = self._error_context_builder()
                    if snippets:
                        fresh.prepend_system_context(snippets)
                if (
                    self._debug_mode
                    and fresh.config.name != "debugger"
                    and fresh.config.name in _PLANNING_AGENTS
                    and self._error_summary_builder is not None
                ):
                    summary = self._error_summary_builder()
                    if summary:
                        fresh.prepend_system_context(
                            "## Active Debug Context\n\n"
                            "Debug mode is active. Recent tool failures are listed below — "
                            "avoid patterns that triggered these errors.\n\n"
                            + summary
                        )

                message = (
                    f"{state['user_message']}\n\n"
                    f"[PARALLEL STEP]: {step_desc}"
                )
                try:
                    return await asyncio.wait_for(
                        fresh.run(message, context=shared_context),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    logger.error("Parallel step timed out (%ss): %s", timeout, step_desc[:80])
                    return AgentResponse(
                        content=f"Step timed out after {timeout}s: {step_desc[:60]}",
                        iterations=0,
                    )
                except Exception as e:
                    logger.error("Parallel step failed: %s — %s", step_desc[:60], e)
                    return AgentResponse(
                        content=f"Step failed ({e}): {step_desc[:60]}",
                        iterations=0,
                    )

        # Execute wave by wave; within each wave all steps run concurrently.
        all_step_responses: list[tuple[str, AgentResponse]] = []
        for wave_idx, wave in enumerate(waves):
            if n_waves > 1:
                self._report_status(
                    f"Wave {wave_idx + 1}/{n_waves}: {len(wave)} step(s) ({agent_name})"
                )
            wave_responses: list[AgentResponse] = await asyncio.gather(
                *[_run_step(step) for step in wave]
            )
            all_step_responses.extend(zip(wave, wave_responses))

        responses = [resp for _, resp in all_step_responses]
        steps_to_run = [step for step, _ in all_step_responses]

        # Merge responses into one AgentResponse
        content_parts: list[str] = []
        for i, (step, resp) in enumerate(all_step_responses, 1):
            wave_tag = ""
            if n_waves > 1:
                # Find which wave this step belongs to for the header annotation
                for w_idx, w in enumerate(waves):
                    if step in w:
                        wave_tag = f" [wave {w_idx + 1}]"
                        break
            header = f"### Parallel Step {i}{wave_tag}: {step[:80]}"
            content_parts.append(f"{header}\n{resp.content}")

        merged_content = "\n\n".join(content_parts)
        all_tool_calls: list[dict[str, Any]] = []
        for resp in responses:
            all_tool_calls.extend(resp.tool_calls_made)
        merged_usage = TokenUsage(
            total_tokens=sum(r.token_usage.total_tokens for r in responses),
            total_cost_usd=sum(r.token_usage.total_cost_usd for r in responses),
            prompt_tokens=sum(r.token_usage.prompt_tokens for r in responses),
            completion_tokens=sum(r.token_usage.completion_tokens for r in responses),
        )

        merged = AgentResponse(
            content=merged_content,
            tool_calls_made=all_tool_calls,
            iterations=sum(r.iterations for r in responses),
            model_used=responses[0].model_used if responses else "",
            token_usage=merged_usage,
        )

        self._report_phase("Execute", "done")
        return {
            **state,
            "agent_response": merged,
            "error": None,
            "accumulated_tokens": state.get("accumulated_tokens", 0) + merged_usage.total_tokens,
            "accumulated_cost_usd": state.get("accumulated_cost_usd", 0.0) + merged_usage.total_cost_usd,
        }

    async def _plan_gate_node(self, state: GraphState) -> GraphState:
        """Pass-through node; routing is handled by _needs_planning."""
        return state

    def _needs_planning(self, state: GraphState) -> Literal["plan", "skip"]:
        """Decide whether to run planner before the selected agent.

        force_plan (from /plan command) bypasses both the auto_plan flag and the
        _PLANNING_AGENTS restriction so that an explicit plan request always runs
        the planner regardless of global settings or which agent was selected.
        """
        if self._registry.get("planner") is None:
            return "skip"

        # Explicit /plan command: always plan, ignore auto_plan and agent type
        if state.get("force_plan", False) and state.get("selected_agent"):
            return "plan"

        # Normal auto-planning: only for implementation agents when router requests it
        if (
            self._auto_plan
            and state.get("needs_planning")
            and state.get("selected_agent") in _PLANNING_AGENTS
        ):
            return "plan"

        return "skip"

    async def _execute_planner_node(self, state: GraphState) -> GraphState:
        """Run the planner agent to create an implementation plan."""
        self._report_status("Planning: exploring codebase")
        self._report_phase("Plan", "active")
        planner = self._registry.get("planner")
        if not planner:
            logger.warning("Planner agent not found, skipping planning")
            return {**state, "plan_response": None}

        # Propagate callbacks
        planner.set_status_callback(self._status_callback)
        planner.set_permission_handler(self._permission_handler)
        planner.set_token_callback(self._token_callback)
        planner.set_continue_handler(self._continue_handler)
        planner.set_clarification_handler(self._clarification_handler)
        planner.set_stream_callback(self._stream_callback)
        planner.set_tool_event_callback(self._tool_event_callback)
        planner.set_error_callback(self._error_callback)

        context = state.get("context", "")
        user_message = state["user_message"]

        # ── Pre-planning enrichment ───────────────────────────────────────────
        # Inject git log + coverage snapshot
        if self._preplan_snapshot_enabled:
            try:
                snapshot = await self._build_preplan_snapshot(user_message)
                if snapshot:
                    context = f"{snapshot}\n\n{context}" if context else snapshot
            except Exception as e:
                logger.debug("Pre-plan snapshot failed: %s", e)

        # Inject grepped symbol definitions for backtick-quoted identifiers
        symbols = self._extract_mentioned_symbols(user_message)
        if symbols:
            try:
                sym_ctx = await self._build_symbol_context(symbols)
                if sym_ctx:
                    context = f"{sym_ctx}\n\n{context}" if context else sym_ctx
            except Exception as e:
                logger.debug("Symbol context build failed: %s", e)

        # Inject similar past plan as warm-start context
        if self._plan_memory_enabled:
            try:
                similar = self._find_similar_plan(user_message)
                if similar:
                    context = f"{similar}\n\n{context}" if context else similar
            except Exception as e:
                logger.debug("Similar plan retrieval failed: %s", e)

        timeout = self._agent_timeout if self._agent_timeout > 0 else None
        try:
            plan_response = await asyncio.wait_for(
                planner.run(user_message, context=context),
                timeout=timeout,
            )
            assumptions = self._parse_plan_assumptions(plan_response.content or "")
            self._report_phase("Plan", "done")
            return {
                **state,
                "plan_response": plan_response,
                "plan_assumptions": assumptions,
                "accumulated_tokens": state.get("accumulated_tokens", 0) + plan_response.token_usage.total_tokens,
                "accumulated_cost_usd": state.get("accumulated_cost_usd", 0.0) + plan_response.token_usage.total_cost_usd,
            }
        except asyncio.TimeoutError:
            logger.error("Planner timed out after %ss", timeout)
            self._report_status("Planning timed out — continuing without plan")
            self._report_phase("Plan", "done")
            return {**state, "plan_response": None}
        except Exception as e:
            logger.error("Planner failed: %s", e)
            self._report_status("Planning failed — continuing without plan")
            self._report_phase("Plan", "done")
            return {**state, "plan_response": None}

    @staticmethod
    def _parse_parallel_steps(plan_content: str) -> list[str]:
        """Extract step descriptions marked [PARALLEL] from a plan.

        Consecutive ``[PARALLEL]`` lines form one parallel group. This method
        returns the descriptions of all such steps so they can be executed
        concurrently by ``_execute_parallel_node``.
        """
        steps: list[str] = []
        for line in plan_content.splitlines():
            stripped = line.strip()
            upper = stripped.upper()
            if "[PARALLEL]" not in upper:
                continue
            idx = upper.find("[PARALLEL]")
            marker_end = idx + len("[PARALLEL]")
            # Text may appear before OR after the marker
            before = stripped[:idx].strip()
            after = stripped[marker_end:].strip()
            step = before or after
            step = re.sub(r"^\d+\.\s*", "", step)
            step = re.sub(r"^[-•*]\s*", "", step)
            if step:
                steps.append(step)
        # Deduplicate while preserving order
        return list(dict.fromkeys(steps))

    @staticmethod
    def _extract_mentioned_symbols(text: str) -> list[str]:
        """Extract backtick-quoted code identifiers from a user message.

        Returns up to 10 symbols (no spaces, no longer than 60 chars) to
        keep the subsequent grep calls bounded.
        """
        raw = re.findall(r"`([^`\n]+)`", text)
        symbols: list[str] = []
        for s in raw:
            s = s.strip()
            if s and len(s) <= 60 and " " not in s:
                symbols.append(s)
        return symbols[:10]

    @staticmethod
    def _parse_plan_assumptions(plan_content: str) -> list[str]:
        """Extract bullet lines from the **Assumptions:** section of a plan.

        Stops at the next bold header or ``##`` section heading.
        Returns an empty list when no assumptions section is present.
        """
        lines = plan_content.splitlines()
        in_assumptions = False
        assumptions: list[str] = []
        for line in lines:
            stripped = line.strip()
            if "**Assumptions:**" in stripped or stripped == "## Assumptions":
                in_assumptions = True
                continue
            if in_assumptions:
                if not stripped:
                    continue
                # Stop at next section header
                if (stripped.startswith("**") and stripped.endswith("**")) or stripped.startswith("##"):
                    break
                assumptions.append(stripped)
        return assumptions

    @staticmethod
    def _parse_execution_map(plan_content: str) -> dict:
        """Parse **Execution Map:** section from a plan.

        Returns a dict with keys ``critical_path``, ``parallel_groups``, and
        ``integration_points``.  Returns empty defaults when the section is
        absent or unparseable — never raises.
        """
        result: dict = {"critical_path": [], "parallel_groups": [], "integration_points": []}
        lines = plan_content.splitlines()
        in_map = False
        for line in lines:
            stripped = line.strip()
            if "**Execution Map:**" in stripped:
                in_map = True
                continue
            if not in_map:
                continue
            # Stop at next bold header or ## section
            if (stripped.startswith("**") and stripped.endswith("**")) or stripped.startswith("##"):
                break
            if not stripped.startswith("-"):
                continue
            content = stripped.lstrip("-").strip()
            lower = content.lower()
            if lower.startswith("critical path:"):
                result["critical_path"] = [int(n) for n in re.findall(r"\d+", content)]
            elif re.match(r"parallel group", lower):
                # Extract step numbers from [N, M, ...] bracket notation only;
                # ignore numbers in parenthetical "(run after step N)" text.
                bracket = re.search(r"\[([^\]]+)\]", content)
                nums = [int(n) for n in re.findall(r"\d+", bracket.group(1))] if bracket else []
                if nums:
                    result["parallel_groups"].append(nums)
            elif lower.startswith("integration point"):
                # Only the step number(s) before any parenthetical comment.
                step_part = re.split(r"\(", content, maxsplit=1)[0]
                result["integration_points"].extend(int(n) for n in re.findall(r"\d+", step_part))
        return result

    def _grep_symbol(self, sym: str) -> str:
        """Synchronously grep for *sym* in the project directory (Python files only).

        Returns up to 10 matching lines, or empty string when not found / on error.
        """
        import subprocess

        try:
            proc = subprocess.run(
                ["grep", "-r", "--include=*.py", "-n", rf"\b{re.escape(sym)}\b",
                 str(self._project_dir)],
                capture_output=True,
                text=True,
                timeout=3,
            )
            lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
            return "\n".join(lines[:10]) if lines else ""
        except Exception:
            return ""

    async def _build_symbol_context(self, symbols: list[str]) -> str:
        """Grep for backtick-quoted symbols from the user message.

        Returns a ``## Referenced Symbols`` section ready for injection into
        the planner's context, or an empty string when nothing is found.
        """
        if not symbols:
            return ""

        loop = asyncio.get_running_loop()
        snippets: list[str] = []
        for sym in symbols[:8]:
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, self._grep_symbol, sym),
                    timeout=3.0,
                )
                if result:
                    snippets.append(f"### `{sym}`\n{result}")
            except Exception:
                pass

        if not snippets:
            return ""
        return "## Referenced Symbols\n\n" + "\n\n".join(snippets)

    def _run_git_log(self) -> str:
        """Synchronously run ``git log --oneline -10`` in the project directory."""
        import subprocess

        try:
            proc = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True,
                text=True,
                cwd=str(self._project_dir),
                timeout=2,
            )
            return (proc.stdout or "").strip()
        except Exception:
            return ""

    def _run_git_status(self) -> str:
        """Synchronously run ``git status --short`` to show uncommitted changes."""
        import subprocess

        try:
            proc = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=str(self._project_dir),
                timeout=2,
            )
            return (proc.stdout or "").strip()
        except Exception:
            return ""

    async def _build_preplan_snapshot(self, user_message: str) -> str:
        """Build a pre-planning context snapshot for the planner.

        Combines the recent git log, uncommitted changes, and coverage context
        into a ``## Pre-planning Snapshot`` section.  Returns an empty string
        when disabled or when all sources yield no data.

        The *user_message* parameter is kept for future file-mention filtering
        but is not currently used to narrow the git log.
        """
        if not self._preplan_snapshot_enabled:
            return ""

        parts: list[str] = []
        loop = asyncio.get_running_loop()

        # Git log: last 10 commits
        try:
            git_log = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_git_log),
                timeout=2.0,
            )
            if git_log:
                parts.append(f"### Recent Commits\n```\n{git_log}\n```")
        except Exception:
            pass

        # Git status: uncommitted changes
        try:
            git_status = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_git_status),
                timeout=1.5,
            )
            if git_status:
                parts.append(f"### Uncommitted Changes\n```\n{git_status}\n```")
        except Exception:
            pass

        # Coverage context (blocking disk I/O — run off event loop)
        try:
            from lidco.core.coverage_reader import build_coverage_context
            cov_ctx = await asyncio.wait_for(
                loop.run_in_executor(None, build_coverage_context, self._project_dir),
                timeout=2.0,
            )
            if cov_ctx:
                parts.append(cov_ctx)
        except Exception:
            pass

        if not parts:
            return ""
        return "## Pre-planning Snapshot\n\n" + "\n\n".join(parts)

    def _find_similar_plan(self, query: str) -> str | None:
        """Search memory for a similar approved plan to use as warm-start context.

        Returns a formatted ``## Similar Past Plan`` section, or ``None`` when
        no relevant plan is found or memory is unavailable.
        """
        if not self._memory_store:
            return None
        try:
            # Use first 10 keywords from the query for substring search
            keywords = query.lower().split()[:10]
            best: list[tuple[int, object]] = []
            for entry in self._memory_store.list_all(category="approved_plans"):
                score = sum(1 for kw in keywords if kw in entry.content.lower())
                if score > 0:
                    best.append((score, entry))
            if not best:
                return None
            best.sort(key=lambda x: x[0], reverse=True)
            _, top_entry = best[0]
            return (
                f"## Similar Past Plan (warm-start reference)\n"
                f"**Task:** {top_entry.key}\n\n"
                f"{top_entry.content[:2000]}"
            )
        except Exception as e:
            logger.debug("Plan memory retrieval failed: %s", e)
            return None

    def _save_approved_plan(self, user_message: str, plan_content: str) -> None:
        """Persist an approved plan to memory for future warm-start retrieval.

        Strips auto-generated critique sections before saving.
        """
        if not self._memory_store or not self._plan_memory_enabled:
            return
        try:
            import hashlib
            key = "plan_" + hashlib.md5(user_message[:200].encode()).hexdigest()[:8]
            # Strip any appended critique section
            marker = "\n\n---\n## Plan Review (auto-generated)\n"
            clean_plan = plan_content.split(marker)[0] if marker in plan_content else plan_content
            self._memory_store.add(
                key=key,
                content=f"Task: {user_message[:200]}\n\n{clean_plan[:3000]}",
                category="approved_plans",
                tags=["auto-plan"],
                scope="project",
            )
            logger.debug("Saved approved plan to memory (key=%s)", key)
        except Exception as e:
            logger.debug("Could not save approved plan: %s", e)

    @staticmethod
    def _compute_critique_budget(plan_content: str) -> int:
        """Return max_tokens for the critique LLM call scaled by plan step count.

        Avoids spending the full critique budget on trivial plans:

        * 0–2 steps  → 300 tokens  (quick sanity check)
        * 3–5 steps  → 500 tokens  (moderate depth)
        * 6+ steps   → 800 tokens  (full critique)

        Never raises — falls back to 500 (moderate) on any parsing error.
        """
        try:
            from lidco.cli.plan_editor import parse_plan_steps  # local: avoid circular
            n = len(parse_plan_steps(plan_content))
        except Exception:
            return 500
        if n <= 2:
            return 300
        if n <= 5:
            return 500
        return 800

    async def _critique_plan_node(self, state: GraphState) -> GraphState:
        """Run a cheap LLM critique pass on the plan before the user sees it.

        Makes a single LLM call (role="routing" for the cheap/fast model) to
        identify risks, gaps, and missing steps in the plan.  The critique is
        appended as a ``## Plan Review (auto-generated)`` section so the user
        can see it during approval.  On failure or when disabled, the plan
        passes through unchanged.
        """
        plan_response = state.get("plan_response")
        if not plan_response or not self._plan_critique_enabled:
            return state

        plan_content = (plan_response.content or "").strip()
        if not plan_content:
            return state

        self._report_status("Reviewing plan for gaps")
        user_message = state.get("user_message", "")
        try:
            critique_response = await asyncio.wait_for(
                self._llm.complete(
                    [
                        Message(role="system", content=_CRITIQUE_SYSTEM_PROMPT),
                        Message(role="user", content=(
                            f"## Original Request\n{user_message}\n\n"
                            f"## Implementation Plan\n{plan_content}"
                        )),
                    ],
                    temperature=0.0,
                    max_tokens=self._compute_critique_budget(plan_content),
                    role="routing",
                ),
                timeout=45,
            )
            critique_text = (critique_response.content or "").strip()
            if not critique_text:
                return state

            # Always append critique to plan display so the user can see it.
            # Only set plan_critique (to trigger revision) when there are real issues;
            # a clean-pass message ("No critical gaps identified.") skips revision.
            is_clean_pass = "no critical gaps" in critique_text.lower()
            from dataclasses import replace as dc_replace
            updated_content = (
                f"{plan_content}\n\n---\n"
                f"## Plan Review (auto-generated)\n{critique_text}"
            )
            updated_response = dc_replace(plan_response, content=updated_content)
            return {
                **state,
                "plan_response": updated_response,
                "plan_critique": None if is_clean_pass else critique_text,
                "accumulated_tokens": (
                    state.get("accumulated_tokens", 0)
                    + (
                        critique_response.usage.get("total_tokens")
                        or (
                            critique_response.usage.get("prompt_tokens", 0)
                            + critique_response.usage.get("completion_tokens", 0)
                        )
                    )
                ),
                "accumulated_cost_usd": (
                    state.get("accumulated_cost_usd", 0.0)
                    + critique_response.cost_usd
                ),
            }
        except Exception as e:
            logger.warning("Plan critique failed (non-fatal): %s", e)
            return state

    async def _revise_plan_node(self, state: GraphState) -> GraphState:
        """Ask the planner model to revise the plan based on the auto-critique.

        This node runs after ``_critique_plan_node`` and before ``_approve_plan_node``.
        When enabled, it feeds the critique back to the planner model so gaps are
        addressed before the user sees the plan.  On any failure the original plan
        is kept unchanged (failure-safe).

        Skipped when:
        - ``_plan_revise_enabled`` is False
        - No ``plan_critique`` is present (critique step was skipped or failed)
        - No ``plan_response`` exists
        """
        plan_response = state.get("plan_response")
        plan_critique = state.get("plan_critique") or ""
        if not self._plan_revise_enabled or not plan_critique or not plan_response:
            return state

        plan_content = (plan_response.content or "").strip()
        if not plan_content:
            return state

        # Strip the critique section that was appended by _critique_plan_node so we
        # hand the planner only its original text (without the auto-generated review).
        critique_marker = "\n\n---\n## Plan Review (auto-generated)\n"
        if critique_marker in plan_content:
            plan_original = plan_content.split(critique_marker)[0]
        else:
            plan_original = plan_content

        self._report_status("Revising plan based on critique")
        user_message = state.get("user_message", "")
        revision_input = (
            f"## Original Request\n{user_message}\n\n"
            f"## Original Plan\n{plan_original}\n\n"
            f"## Critique\n{plan_critique}"
        )

        try:
            from dataclasses import replace as dc_replace

            revision_response = await asyncio.wait_for(
                self._llm.complete(
                    [
                        Message(role="system", content=_REVISE_SYSTEM_PROMPT),
                        Message(role="user", content=revision_input),
                    ],
                    temperature=0.1,
                    max_tokens=3000,
                    role="planner",
                ),
                timeout=60,
            )
            revised_text = (revision_response.content or "").strip()
            if not revised_text:
                return state

            # Sanity-check: if the response has no "##" section headers it is
            # not a valid plan (could be a router JSON or other junk) — skip.
            if "##" not in revised_text:
                logger.warning(
                    "Plan revision skipped: response does not contain plan structure"
                )
                return state

            updated_response = dc_replace(plan_response, content=revised_text)
            updated_assumptions = self._parse_plan_assumptions(revised_text)
            return {
                **state,
                "plan_response": updated_response,
                "plan_critique": None,  # consumed — cleared so approve sees clean plan
                "plan_critique_addressed": plan_critique,  # save what was addressed
                "plan_revision": revised_text,
                "plan_assumptions": updated_assumptions,  # re-parsed from revised plan
                "accumulated_tokens": (
                    state.get("accumulated_tokens", 0)
                    + (
                        revision_response.usage.get("total_tokens")
                        or (
                            revision_response.usage.get("prompt_tokens", 0)
                            + revision_response.usage.get("completion_tokens", 0)
                        )
                    )
                ),
                "accumulated_cost_usd": (
                    state.get("accumulated_cost_usd", 0.0)
                    + revision_response.cost_usd
                ),
            }
        except Exception as e:
            logger.warning("Plan revision failed (non-fatal): %s", e)
            # Clear critique so _should_revise_again exits the loop instead of
            # burning tokens on another revision attempt that will also fail.
            return {**state, "plan_critique": None}

    async def _re_critique_plan_node(self, state: GraphState) -> GraphState:
        """Run an additional critique pass after revision for multi-round refinement.

        Called after ``_revise_plan_node`` when ``_plan_max_revisions > 0``.
        Increments ``plan_revision_round`` and generates a new ``plan_critique``
        so ``_revise_plan_node`` can address it in the next loop iteration.
        On any failure the plan passes through unchanged.
        """
        plan_response = state.get("plan_response")
        if not plan_response:
            return state

        plan_content = (plan_response.content or "").strip()
        if not plan_content:
            return state

        self._report_status("Re-reviewing revised plan")
        original_critique = state.get("plan_critique_addressed") or ""
        try:
            critique_response = await asyncio.wait_for(
                self._llm.complete(
                    [
                        Message(role="system", content=_RE_CRITIQUE_SYSTEM_PROMPT),
                        Message(role="user", content=(
                            f"## Original Critique\n{original_critique}\n\n"
                            f"## Revised Plan\n{plan_content}"
                        )),
                    ],
                    temperature=0.0,
                    max_tokens=max(150, self._compute_critique_budget(plan_content) // 2),
                    role="routing",
                ),
                timeout=45,
            )
            critique_text = (critique_response.content or "").strip()
            round_num = state.get("plan_revision_round", 0) + 1
            # Normalize clean-pass message to None so the revision loop exits
            is_clean_pass = (
                not critique_text
                or "all critique points addressed" in critique_text.lower()
            )
            return {
                **state,
                "plan_critique": None if is_clean_pass else critique_text,
                "plan_revision_round": round_num,
                "accumulated_tokens": (
                    state.get("accumulated_tokens", 0)
                    + (
                        critique_response.usage.get("total_tokens")
                        or (
                            critique_response.usage.get("prompt_tokens", 0)
                            + critique_response.usage.get("completion_tokens", 0)
                        )
                    )
                ),
                "accumulated_cost_usd": (
                    state.get("accumulated_cost_usd", 0.0)
                    + critique_response.cost_usd
                ),
            }
        except Exception as e:
            logger.warning("Re-critique pass failed (non-fatal): %s", e)
            round_num = state.get("plan_revision_round", 0) + 1
            return {**state, "plan_revision_round": round_num, "plan_critique": None}

    def _should_revise_again(self, state: GraphState) -> str:
        """Decide whether to run another revise pass after re-critique.

        Returns ``"revise"`` when:
        - A non-empty ``plan_critique`` is present (new issues found), AND
        - ``plan_revision_round`` has not yet reached ``_plan_max_revisions``.

        Returns ``"done"`` otherwise (proceed to ``approve_plan``).
        """
        critique = state.get("plan_critique") or ""
        if not critique.strip():
            return "done"
        round_num = state.get("plan_revision_round", 0)
        if round_num < self._plan_max_revisions:
            return "revise"
        return "done"

    def _augment_parallel_steps(
        self, parallel_steps: list[str], execution_map: dict, plan_content: str
    ) -> list[str]:
        """Supplement *parallel_steps* with steps named in execution-map groups.

        Steps referenced by number in ``execution_map["parallel_groups"]`` are
        added to *parallel_steps* if not already present.  Uses
        ``parse_plan_steps`` (imported locally to avoid circular import) to
        resolve 1-based step numbers to step-description strings.
        """
        if not execution_map["parallel_groups"]:
            return parallel_steps
        from lidco.cli.plan_editor import parse_plan_steps  # local import: avoid circular
        all_steps = parse_plan_steps(plan_content)
        result = list(parallel_steps)
        for group in execution_map["parallel_groups"]:
            for step_num in group:
                idx = step_num - 1  # 1-based → 0-based
                if 0 <= idx < len(all_steps):
                    step_desc = all_steps[idx]
                    # Normalize: strip [PARALLEL] marker so dedup works whether
                    # the step was already added via marker or via execution map.
                    normalized = re.sub(r"\s*\[PARALLEL\]\s*", "", step_desc, flags=re.IGNORECASE).strip()
                    if normalized not in result and step_desc not in result:
                        result.append(normalized)
        return result

    @staticmethod
    def _check_plan_sections(plan_content: str) -> list[str]:
        """Return names of required sections missing from *plan_content*.

        Checks for the 5 core sections mandated by the planner output format:
        Goal, Assumptions, Steps, Risk Assessment, Test Impact.

        Returns an empty list when all are present.  Never raises.
        """
        lower = plan_content.lower()
        return [
            name
            for marker, name in _REQUIRED_PLAN_SECTIONS
            if marker.lower() not in lower
        ]

    @staticmethod
    def _verify_one_assumption(text: str, project_dir: Path) -> tuple[str, str]:
        """Check one ``[⚠ Unverified]`` assumption against the filesystem.

        Extracts all backtick-quoted tokens and probes each one:

        * **File path** (contains ``/`` or has a known extension) → ``Path.exists()``
          with a fallback ``rglob`` by filename.
        * **Python module** (dotted identifier, no slashes) → ``importlib.util.find_spec``.
        * **Symbol** (pure identifier, >2 chars) → ``grep -r --include=*.py``.

        Returns ``(status, detail)`` where *status* is:

        * ``"verified"`` — at least one check passed and none explicitly failed.
        * ``"wrong"``    — at least one check failed.
        * ``"skip"``     — nothing verifiable found (status unchanged).

        Subprocess errors and missing tools are silently ignored (treated as
        "skip") so Windows environments without ``grep`` on PATH work fine.
        Never raises.
        """
        import importlib.util
        import subprocess

        _FILE_EXTS = frozenset({
            ".py", ".ts", ".js", ".jsx", ".tsx",
            ".yaml", ".yml", ".json", ".toml", ".md", ".txt", ".cfg", ".ini",
        })

        tokens = re.findall(r"`([^`\n]+)`", text)
        if not tokens:
            return "skip", ""

        passed: list[str] = []
        failed: list[str] = []

        for token in tokens[:6]:
            token = token.strip()
            if not token or len(token) > 200:
                continue

            has_slash = "/" in token or "\\" in token
            has_known_ext = any(token.endswith(ext) for ext in _FILE_EXTS)
            has_dot = "." in token
            is_pure_id = bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token))

            if has_slash or has_known_ext:
                # File path check
                candidate = project_dir / token
                if candidate.exists():
                    passed.append(token)
                else:
                    filename = Path(token).name
                    found = next(iter(project_dir.rglob(filename)), None)
                    if found:
                        passed.append(token)
                    else:
                        failed.append(f"file not found: {token}")
                continue

            if has_dot and not has_slash and " " not in token:
                # Python module import check (dotted identifier, not a version string)
                parts = token.split(".")
                if all(p.isidentifier() for p in parts if p):
                    try:
                        spec = importlib.util.find_spec(token)
                        if spec is not None:
                            passed.append(token)
                        else:
                            failed.append(f"module not importable: {token}")
                    except Exception:
                        failed.append(f"module not importable: {token}")
                continue

            if is_pure_id and len(token) > 2:
                # Symbol check via grep — errors/missing tool → skip (no penalty)
                try:
                    result = subprocess.run(
                        ["grep", "-r", "--include=*.py", "-l",
                         rf"\b{re.escape(token)}\b", str(project_dir)],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        passed.append(token)
                    elif result.returncode == 1:
                        # grep exit 1 = no matches found
                        failed.append(f"symbol not found: {token}")
                    # returncode > 1 = grep error → skip
                except Exception:
                    pass  # No grep or timeout → treat as skip

        if failed:
            return "wrong", "; ".join(failed[:2])
        if passed:
            return "verified", ""
        return "skip", ""

    async def _verify_assumptions_node(self, state: GraphState) -> GraphState:
        """Verify ``[⚠ Unverified]`` assumptions against the filesystem.

        Runs after ``re_critique_plan`` and before ``approve_plan``.  For each
        unverified assumption (capped at 10 to bound execution time):

        1. Calls ``_verify_one_assumption`` in a thread-pool executor.
        2. Annotates the matching line in ``plan_response.content``:
           ``[⚠ Unverified]`` → ``[✓ Verified]`` or ``[✗ Wrong: detail]``.
        3. Collects failures in ``plan_bad_assumptions``.

        When failures are found, appends a visible
        ``## Assumption Verification Issues`` section to the plan so the user
        sees them prominently during the approval step.

        On any error the node passes state through unchanged.
        """
        plan_response = state.get("plan_response")
        assumptions = state.get("plan_assumptions") or []
        unverified = [a for a in assumptions if "[⚠" in a]

        if not plan_response:
            return {**state, "plan_bad_assumptions": [], "plan_section_issues": []}

        if not unverified:
            # Still run section completeness check even with no unverified assumptions.
            section_issues = self._check_plan_sections(plan_response.content or "")
            return {**state, "plan_bad_assumptions": [], "plan_section_issues": section_issues}

        self._report_status("Verifying plan assumptions")
        loop = asyncio.get_running_loop()
        plan_content = plan_response.content or ""
        lines = plan_content.split("\n")
        bad_assumptions: list[str] = []

        for assumption in unverified[:10]:
            try:
                status, detail = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, self._verify_one_assumption, assumption, self._project_dir
                    ),
                    timeout=5.0,
                )
            except Exception:
                status, detail = "skip", ""

            if status == "skip":
                continue

            replacement = (
                "[✓ Verified]"
                if status == "verified"
                else (f"[✗ Wrong: {detail}]" if detail else "[✗ Wrong]")
            )

            # Update the target line in-place (assumption == line.strip())
            for i, line in enumerate(lines):
                if line.strip() == assumption:
                    lines[i] = line.replace("[⚠ Unverified]", replacement, 1)
                    break

            if status == "wrong":
                label = re.sub(r"\[⚠\s*Unverified\]", "", assumption).strip().lstrip("-•* ").strip()
                bad_assumptions.append(f"{label}: {detail}" if detail else label)

        plan_content = "\n".join(lines)

        if bad_assumptions:
            issues = "\n".join(f"- {b}" for b in bad_assumptions)
            plan_content += (
                "\n\n---\n## Assumption Verification Issues\n"
                "The following assumptions could **not** be verified and may indicate "
                "planning errors:\n\n" + issues
            )

        # Section completeness check — report missing required sections.
        # Runs as a pure analysis pass (no plan content modification) so that
        # the health score in _approve_plan_node can factor in structural gaps.
        section_issues = self._check_plan_sections(plan_content)

        from dataclasses import replace as dc_replace
        updated_response = dc_replace(plan_response, content=plan_content)
        updated_assumptions = self._parse_plan_assumptions(plan_content)

        return {
            **state,
            "plan_response": updated_response,
            "plan_assumptions": updated_assumptions,
            "plan_bad_assumptions": bad_assumptions,
            "plan_section_issues": section_issues,
        }

    @staticmethod
    def _compute_plan_health(
        plan_content: str,
        bad_assumptions: list[str],
        plan_critique: str | None,
        section_issues: list[str],
    ) -> int:
        """Compute a 0–100 quality score for the plan.

        Four equal-weight components (25 pts each):

        1. **Section completeness** — all 5 required sections present.
        2. **Assumption health**    — no failed assumption checks.
        3. **Critique resolved**    — ``plan_critique`` is ``None`` (clean pass or all
           issues addressed before approval).
        4. **Step format**          — ≥ 50 % of numbered steps have a ``Verify:`` field.

        Never raises.
        """
        score = 0

        # 1. Section completeness
        if not section_issues:
            score += 25

        # 2. Assumption health
        if not bad_assumptions:
            score += 25

        # 3. Critique resolved
        if not plan_critique:
            score += 25

        # 4. Step format compliance
        try:
            from lidco.cli.plan_editor import parse_plan_steps  # local: avoid circular
            n_steps = len(parse_plan_steps(plan_content))
            n_verify = sum(
                1 for line in plan_content.splitlines()
                if re.match(r"^\s*verify\s*:", line, re.IGNORECASE)
            )
            if n_steps == 0:
                score += 12  # no numbered steps — give partial credit
            elif n_verify / n_steps >= 0.5:
                score += 25
        except Exception:
            score += 12  # error in step parsing — give partial credit

        return score

    def _parse_parallel_info(self, plan_content: str) -> tuple[list[str], dict, dict]:
        """Return ``(parallel_steps, execution_map, plan_step_deps)`` from plan text.

        Consolidates the three parallel-related parsing calls that every approval
        path in ``_approve_plan_node`` needs:
        1. Extract ``[PARALLEL]``-marked step descriptions.
        2. Parse the ``**Execution Map:**`` section.
        3. Augment ``parallel_steps`` with groups from the execution map.
        4. Parse ``Deps:`` lines into ``{step_num: [dep_nums]}``.

        Never raises — parsing errors produce empty defaults.
        """
        from lidco.cli.plan_editor import _parse_step_deps  # local: avoid circular import
        parallel_steps = self._parse_parallel_steps(plan_content)
        execution_map = self._parse_execution_map(plan_content)
        parallel_steps = self._augment_parallel_steps(parallel_steps, execution_map, plan_content)
        plan_step_deps = _parse_step_deps(plan_content)
        return parallel_steps, execution_map, plan_step_deps

    @staticmethod
    def _build_dep_waves(
        parallel_steps: list[str],
        plan_step_deps: dict,
        all_steps: list[str],
    ) -> list[list[str]]:
        """Topological-sort *parallel_steps* into dependency waves.

        Each wave is a list of step descriptions that can execute concurrently.
        Wave N starts only after every step in waves 0…N-1 has completed.

        A dep is "relevant" only when it is itself in *parallel_steps* — deps on
        sequential steps (outside the parallel set) are already satisfied before
        ``_execute_parallel_node`` is called.

        Falls back to a single wave when *plan_step_deps* is empty, *all_steps*
        is empty, or a dependency cycle is detected.  Never raises.
        """
        if not parallel_steps:
            return []
        if not plan_step_deps or not all_steps:
            return [list(parallel_steps)]

        def _normalize(s: str) -> str:
            return re.sub(r"\s*\[PARALLEL\]\s*", "", s, flags=re.IGNORECASE).strip()

        # Build normalized description → 1-based step number map
        norm_to_num: dict[str, int] = {_normalize(d): i + 1 for i, d in enumerate(all_steps)}
        parallel_set_norm = {_normalize(s) for s in parallel_steps}

        # For each parallel step, collect the deps that are also parallel steps
        dep_map: dict[str, list[str]] = {}
        for step in parallel_steps:
            norm = _normalize(step)
            step_num = norm_to_num.get(norm)
            if step_num is None:
                dep_map[norm] = []
                continue
            relevant: list[str] = []
            for dep_num in plan_step_deps.get(step_num, []):
                dep_idx = dep_num - 1
                if 0 <= dep_idx < len(all_steps):
                    dep_norm = _normalize(all_steps[dep_idx])
                    if dep_norm in parallel_set_norm:
                        relevant.append(dep_norm)
            dep_map[norm] = relevant

        # Kahn's algorithm — group into waves
        completed: set[str] = set()
        remaining = list(parallel_steps)
        waves: list[list[str]] = []

        while remaining:
            wave = [
                s for s in remaining
                if all(d in completed for d in dep_map.get(_normalize(s), []))
            ]
            if not wave:
                # Cycle or unresolvable — run all remaining together as fallback
                logger.warning(
                    "Dependency cycle in plan steps — running remaining %d steps in one wave",
                    len(remaining),
                )
                wave = remaining[:]
            waves.append(wave)
            completed.update(_normalize(s) for s in wave)
            remaining = [s for s in remaining if s not in wave]

        return waves

    async def _approve_plan_node(self, state: GraphState) -> GraphState:
        """Ask the user to approve, reject, or edit the plan.

        When a plan editor is registered (``set_plan_editor``), it receives the
        full plan text and returns either a (possibly filtered) plan string or
        ``None`` to reject.  Otherwise the standard clarification-handler flow
        is used with Approve / Reject / Edit options.

        After approval the plan content is scanned for ``[PARALLEL]`` step
        markers; if any are found they are stored in ``parallel_steps`` so the
        routing can dispatch to ``execute_parallel`` instead of ``execute_agent``.
        The ``**Execution Map:**`` section is also parsed and stored in
        ``execution_map`` — its parallel groups supplement any ``[PARALLEL]``
        markers found in individual step lines.
        """
        plan_response = state.get("plan_response")
        if not plan_response:
            return {
                **state,
                "plan_approved": True,
                "parallel_steps": [],
                "execution_map": None,
                "plan_step_deps": None,
                "plan_health_score": 0,
            }

        # Compute and emit plan quality score before showing plan to user.
        health = self._compute_plan_health(
            plan_response.content or "",
            state.get("plan_bad_assumptions") or [],
            state.get("plan_critique"),
            state.get("plan_section_issues") or [],
        )
        quality_label = "excellent" if health >= 90 else "good" if health >= 75 else "fair" if health >= 50 else "poor"
        self._report_status(f"Plan quality: {health}/100 ({quality_label})")

        # ── Interactive plan editor path ──────────────────────────────────────
        if self._plan_editor:
            try:
                filtered_plan = await asyncio.get_running_loop().run_in_executor(
                    None,
                    self._plan_editor,
                    plan_response.content,
                )
            except Exception as e:
                logger.error("Plan editor failed: %s", e)
                self._report_status("Plan editor error — auto-approving plan")
                parallel_steps, execution_map, plan_step_deps = self._parse_parallel_info(plan_response.content)
                return {**state, "plan_approved": True, "parallel_steps": parallel_steps, "execution_map": execution_map, "plan_step_deps": plan_step_deps, "plan_health_score": health}

            if filtered_plan is None:
                return {
                    **state,
                    "plan_approved": False,
                    "agent_response": plan_response,
                    "parallel_steps": [],
                    "execution_map": None,
                    "plan_step_deps": None,
                    "plan_health_score": health,
                }

            plan_context = f"## Implementation Plan (approved)\n{filtered_plan}"
            existing_context = state.get("context", "")
            merged = (
                f"{plan_context}\n\n{existing_context}" if existing_context else plan_context
            )
            parallel_steps, execution_map, plan_step_deps = self._parse_parallel_info(filtered_plan)
            await asyncio.get_running_loop().run_in_executor(None, self._save_approved_plan, state["user_message"], filtered_plan)
            return {**state, "plan_approved": True, "context": merged, "parallel_steps": parallel_steps, "execution_map": execution_map, "plan_step_deps": plan_step_deps, "plan_health_score": health}

        # ── Fallback: standard clarification-handler flow ────────────────────
        if not self._clarification_handler:
            parallel_steps, execution_map, plan_step_deps = self._parse_parallel_info(plan_response.content)
            await asyncio.get_running_loop().run_in_executor(None, self._save_approved_plan, state["user_message"], plan_response.content)
            return {**state, "plan_approved": True, "parallel_steps": parallel_steps, "execution_map": execution_map, "plan_step_deps": plan_step_deps, "plan_health_score": health}

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
            self._report_status("Plan approval error — auto-approving plan")
            parallel_steps, execution_map, plan_step_deps = self._parse_parallel_info(plan_response.content)
            await asyncio.get_running_loop().run_in_executor(None, self._save_approved_plan, state["user_message"], plan_response.content)
            return {**state, "plan_approved": True, "parallel_steps": parallel_steps, "execution_map": execution_map, "plan_step_deps": plan_step_deps, "plan_health_score": health}

        answer_lower = (answer or "").strip().lower()

        if answer_lower in ("approve", "y", "yes", ""):
            plan_context = f"## Implementation Plan (approved)\n{plan_response.content}"
            existing_context = state.get("context", "")
            merged = (
                f"{plan_context}\n\n{existing_context}" if existing_context else plan_context
            )
            parallel_steps, execution_map, plan_step_deps = self._parse_parallel_info(plan_response.content)
            await asyncio.get_running_loop().run_in_executor(None, self._save_approved_plan, state["user_message"], plan_response.content)
            return {**state, "plan_approved": True, "context": merged, "parallel_steps": parallel_steps, "execution_map": execution_map, "plan_step_deps": plan_step_deps, "plan_health_score": health}

        if answer_lower in ("reject", "n", "no"):
            return {
                **state,
                "plan_approved": False,
                "agent_response": plan_response,
                "parallel_steps": [],
                "execution_map": None,
                "plan_step_deps": None,
                "plan_health_score": health,
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
        # Parse parallel info from the approved plan only (not user edit notes)
        parallel_steps, execution_map, plan_step_deps = self._parse_parallel_info(plan_response.content)
        await asyncio.get_running_loop().run_in_executor(None, self._save_approved_plan, state["user_message"], plan_response.content)
        return {**state, "plan_approved": True, "context": merged, "parallel_steps": parallel_steps, "execution_map": execution_map, "plan_step_deps": plan_step_deps, "plan_health_score": health}

    def _plan_approved(self, state: GraphState) -> Literal["parallel", "sequential", "rejected"]:
        """Route based on plan approval status and parallel step detection."""
        if not state.get("plan_approved", False):
            return "rejected"
        if state.get("parallel_steps"):
            return "parallel"
        return "sequential"

    def _should_review(self, state: GraphState) -> Literal["review", "skip"]:
        """Decide whether to run auto-review."""
        # Never review if the agent execution failed
        if state.get("error"):
            return "skip"
        if state.get("needs_review") and state.get("agent_response"):
            response = state["agent_response"]
            # Only review if the agent made tool calls (i.e. modified something)
            if response.tool_calls_made:
                return "review"
        return "skip"

    async def _auto_review_node(self, state: GraphState) -> GraphState:
        """Automatically review code changes."""
        prev_iter = state.get("review_iteration", 0)
        review_iter = prev_iter + 1
        self._report_status("Reviewing changes")
        self._report_phase("Review", "active")
        reviewer = self._registry.get("reviewer")
        if not reviewer:
            return {**state, "review_iteration": review_iter}

        reviewer.set_status_callback(self._status_callback)
        reviewer.set_permission_handler(self._permission_handler)
        reviewer.set_token_callback(self._token_callback)
        reviewer.set_continue_handler(self._continue_handler)
        reviewer.set_tool_event_callback(self._tool_event_callback)
        reviewer.set_clarification_handler(self._clarification_handler)
        reviewer.set_stream_callback(self._stream_callback)
        reviewer.set_error_callback(self._error_callback)

        agent_response = state.get("agent_response")
        if not agent_response:
            return {**state, "review_iteration": review_iter}

        # Build review context: tool call summary + actual file contents
        tool_calls_summary = "\n".join(
            f"- {tc['tool']}({', '.join(f'{k}={v}' for k, v in tc['args'].items())})"
            for tc in agent_response.tool_calls_made[:20]
        )

        # Include actual content of written/edited files so reviewer doesn't re-read
        write_changes: list[str] = []
        for tc in agent_response.tool_calls_made:
            tool = tc.get("tool", "")
            if tool == "file_write":
                path = tc.get("args", {}).get("path", "?")
                content = tc.get("args", {}).get("content", "")[:1500]
                write_changes.append(f"### {path} (written)\n```\n{content}\n```")
            elif tool == "file_edit":
                path = tc.get("args", {}).get("path", "?")
                old_str = tc.get("args", {}).get("old_string", "")[:300]
                new_str = tc.get("args", {}).get("new_string", "")[:300]
                write_changes.append(
                    f"### {path} (edited)\n```diff\n-{old_str}\n+{new_str}\n```"
                )
        files_section = (
            "\n\nActual file changes:\n" + "\n\n".join(write_changes[:5])
            if write_changes else ""
        )

        # Inject learned review patterns (top-5 most recent) as reviewer guidance
        patterns_hint = self._build_review_patterns_hint()

        review_prompt = (
            f"Review the following changes made by the {state['selected_agent']} agent:\n\n"
            f"Original request: {state['user_message']}\n\n"
            f"Tool calls made:\n{tool_calls_summary}"
            f"{files_section}\n\n"
            f"Agent response:\n{agent_response.content[:2000]}\n\n"
            f"{patterns_hint}"
            "Provide a brief review. Use ONLY these severity labels for real issues:\n"
            "  CRITICAL: <description>  (must fix)\n"
            "  HIGH: <description>  (should fix)\n"
            "  MEDIUM: <description>  (quality improvement, non-blocking)\n"
            "If there are no CRITICAL or HIGH issues, output 'NO_ISSUES_FOUND' on the first line.\n"
            "MEDIUM issues may still be listed after NO_ISSUES_FOUND."
        )

        timeout = self._agent_timeout if self._agent_timeout > 0 else None
        try:
            review = await asyncio.wait_for(
                reviewer.run(review_prompt),
                timeout=timeout,
            )
            self._report_phase("Review", "done")
            medium_issues = self._extract_medium_issues(review.content or "")

            # Learn from clean reviews: save patterns for future reviewer runs
            review_content = review.content or ""
            if self._memory_store and (
                review_content.startswith("NO_ISSUES_FOUND")
                or not self._SEVERITY_LABEL_RE.search(review_content)
            ):
                self._save_review_patterns(review_content)

            return {
                **state,
                "review_response": review,
                "review_iteration": review_iter,
                "medium_issues": medium_issues,
                "accumulated_tokens": state.get("accumulated_tokens", 0) + review.token_usage.total_tokens,
                "accumulated_cost_usd": state.get("accumulated_cost_usd", 0.0) + review.token_usage.total_cost_usd,
            }
        except asyncio.TimeoutError:
            logger.warning("Reviewer timed out after %ss", timeout)
            self._report_phase("Review", "done")
            # Advance the counter so a persistent timeout cannot cause an
            # infinite review→fix→review loop.
            return {**state, "review_iteration": review_iter}
        except Exception as e:
            logger.warning("Auto-review failed: %s", e)
            self._report_phase("Review", "done")
            return {**state, "review_iteration": review_iter}

    # Matches "CRITICAL:" or "HIGH:" as a severity label at the start of a line.
    # Prevents false positives like "high quality".
    _SEVERITY_LABEL_RE = re.compile(r"^\s*(CRITICAL|HIGH)\s*:", re.MULTILINE | re.IGNORECASE)

    # Matches "MEDIUM:" severity label lines (advisory, non-blocking).
    _MEDIUM_LABEL_RE = re.compile(r"^\s*MEDIUM\s*:.*", re.MULTILINE | re.IGNORECASE)

    def _extract_medium_issues(self, content: str) -> str:
        """Extract MEDIUM severity issue lines from reviewer output (advisory only)."""
        matches = self._MEDIUM_LABEL_RE.findall(content)
        return "\n".join(m.strip() for m in matches[:5])

    def _save_review_patterns(self, review_content: str) -> None:
        """Persist non-trivial reviewer findings as reusable patterns in memory.

        Called after a clean review (no CRITICAL/HIGH issues) so future reviewer
        runs know what this project considers acceptable and what to emphasise.
        """
        if not self._memory_store or not review_content.strip():
            return
        # Extract only lines that contain actual observations (MEDIUM lines)
        medium = self._MEDIUM_LABEL_RE.findall(review_content)
        if not medium:
            return
        pattern_text = "\n".join(m.strip() for m in medium[:5])
        # Use a rolling key so we keep the last few patterns (overwrite old ones)
        existing = self._memory_store.list_all(category="review_patterns")
        idx = (len(existing) % 10) + 1  # rotate through 10 slots
        key = f"review_pattern_{idx:02d}"
        try:
            self._memory_store.add(
                key=key,
                content=pattern_text,
                category="review_patterns",
                tags=["auto-review"],
                scope="project",
            )
            logger.debug("Saved review patterns to memory (key=%s)", key)
        except Exception as exc:
            logger.debug("Could not save review patterns: %s", exc)

    def _build_review_patterns_hint(self) -> str:
        """Return a prompt section with the most recent review patterns, or empty string."""
        if not self._memory_store:
            return ""
        patterns = self._memory_store.list_all(category="review_patterns")
        if not patterns:
            return ""
        recent = patterns[-5:]  # last 5 entries
        lines = [e.content for e in recent if e.content]
        if not lines:
            return ""
        hint = "## Past review patterns (emphasise these):\n" + "\n".join(f"- {line}" for line in lines) + "\n\n"
        return hint

    def _should_fix(self, state: GraphState) -> Literal["fix", "done"]:
        """Decide whether to send code back for fixes based on review."""
        review = state.get("review_response")
        review_iter = state.get("review_iteration", 0)

        # No review or max iterations reached → done
        if not review or review_iter >= self._max_review_iterations:
            return "done"

        # If reviewer explicitly said no issues → done
        content = (review.content or "").strip()
        if content.startswith("NO_ISSUES_FOUND"):
            return "done"

        # Check for severity labels "CRITICAL:" / "HIGH:" at the start of a line
        if self._SEVERITY_LABEL_RE.search(content):
            return "fix"

        return "done"

    async def _finalize_node(self, state: GraphState) -> GraphState:
        """Finalize the response, optionally extracting learnings to memory."""
        if self._memory_store and state.get("agent_response"):
            await self._extract_memory(state)

        # Update RAG index for any files modified during this run (blocking I/O)
        if self._context_retriever and state.get("agent_response"):
            await asyncio.get_running_loop().run_in_executor(None, self._update_rag_index, state)

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

            raw = (llm_response.content or "").strip()
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
        force_plan: bool = False,
    ) -> AgentResponse:
        """Handle a user message through the graph.

        Args:
            user_message: The user's request.
            agent_name: Pre-select a specific agent (skips LLM routing).
            context: Additional context injected into the agent.
            force_plan: When True, always run the planner phase regardless of
                the router's needs_planning decision. Used by the /plan command.
        """
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
            "needs_planning": force_plan,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 0,
            "force_plan": force_plan,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "medium_issues": "",
            "parallel_steps": [],
            "plan_critique": None,
            "plan_revision": None,
            "plan_assumptions": [],
            "plan_revision_round": 0,
        }

        errors_before = self._error_count_reader() if self._error_count_reader else 0

        result = await self._graph.ainvoke(initial_state)

        errors_after = self._error_count_reader() if self._error_count_reader else 0

        response = result.get("agent_response") or AgentResponse(
            content="No response generated.", iterations=0
        )

        # Build aggregated token usage from all agents (planner + coder + reviewer)
        combined_usage = TokenUsage(
            total_tokens=result.get("accumulated_tokens", 0),
            total_cost_usd=result.get("accumulated_cost_usd", 0.0),
        )
        # Carry per-type counts from the main agent response (best approximation)
        combined_usage.prompt_tokens = response.token_usage.prompt_tokens
        combined_usage.completion_tokens = response.token_usage.completion_tokens

        # Append review if available
        review = result.get("review_response")
        medium_issues = result.get("medium_issues", "")
        if review and review.content:
            # Append medium issues as advisory note if not already in review content
            # (medium issues are already visible in review.content, but add a header hint
            # if they exist and NO_ISSUES_FOUND was the primary verdict)
            review_text = review.content
            if medium_issues and review_text.startswith("NO_ISSUES_FOUND"):
                review_text = f"NO_ISSUES_FOUND\n\n**Advisory (MEDIUM):**\n{medium_issues}"
            response = AgentResponse(
                content=f"{response.content}\n\n---\n**Auto-Review:**\n{review_text}",
                tool_calls_made=response.tool_calls_made,
                iterations=response.iterations,
                model_used=response.model_used,
                token_usage=combined_usage,
            )
        else:
            response = AgentResponse(
                content=response.content,
                tool_calls_made=response.tool_calls_made,
                iterations=response.iterations,
                model_used=response.model_used,
                token_usage=combined_usage,
            )

        # Auto-debug suggestion: append an advisory when 2+ tool failures occurred
        # during this run and the routed agent was not the debugger itself.
        selected_agent = result.get("selected_agent", "")
        new_errors = errors_after - errors_before
        if new_errors >= 2 and selected_agent != "debugger" and response.content:
            advisory = (
                "\n\n---\n⚠ **Debug tip:** 2 or more tool failures occurred during this run. "
                "Type `/errors` to inspect them or ask me to `/debug analyze`."
            )
            response = AgentResponse(
                content=response.content + advisory,
                tool_calls_made=response.tool_calls_made,
                iterations=response.iterations,
                model_used=response.model_used,
                token_usage=response.token_usage,
            )

        # Update history
        self._conversation_history.append({"role": "user", "content": user_message})
        self._conversation_history.append({"role": "assistant", "content": response.content})

        return response

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()

    def restore_history(self, messages: list[dict[str, str]]) -> None:
        """Restore conversation history from a list of message dicts."""
        valid: list[dict[str, str]] = []
        for i, m in enumerate(messages):
            if not isinstance(m, dict) or "role" not in m or "content" not in m:
                logger.warning("restore_history: skipping invalid message at index %d", i)
                continue
            valid.append(m)
        self._conversation_history = valid
