"""Integration tests for the full orchestration flow.

Tests the complete pipeline: user message → routing → agent → review → response.
Uses mock LLM but real orchestrator graph, agent registry, and state machine.
"""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from lidco.agents.base import AgentConfig, AgentResponse, BaseAgent
from lidco.agents.graph import GraphOrchestrator, GraphState
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import LLMResponse, Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubAgent(BaseAgent):
    """Agent that returns a predetermined response."""

    def __init__(
        self,
        name: str = "coder",
        response_content: str = "done",
        tool_calls: list[dict] | None = None,
    ) -> None:
        config = AgentConfig(
            name=name,
            description=f"{name} agent for testing",
            system_prompt="test prompt",
        )
        llm = MagicMock()
        registry = MagicMock()
        super().__init__(config=config, llm=llm, tool_registry=registry)
        self._response_content = response_content
        self._tool_calls = tool_calls or []
        self.last_message: str | None = None
        self.last_context: str | None = None

    def get_system_prompt(self) -> str:
        return "test"

    async def run(self, message: str, *, context: str = "") -> AgentResponse:
        self.last_message = message
        self.last_context = context
        return AgentResponse(
            content=self._response_content,
            iterations=1,
            tool_calls_made=self._tool_calls,
        )


def _build_registry(**agents: _StubAgent) -> AgentRegistry:
    """Build a registry with named agents."""
    reg = AgentRegistry()
    for agent in agents.values():
        reg.register(agent)
    return reg


def _router_llm(agent: str, needs_review: bool = False, needs_planning: bool = False) -> AsyncMock:
    """Build a mock LLM that returns a specific router decision."""
    payload = json.dumps({
        "agent": agent,
        "needs_review": needs_review,
        "needs_planning": needs_planning,
    })
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(content=payload, model="test"))
    return llm


# ---------------------------------------------------------------------------
# Test: Simple end-to-end flow (no review, no planning)
# ---------------------------------------------------------------------------


class TestSimpleFlow:
    """User message → route to coder → execute → finalize."""

    @pytest.mark.asyncio
    async def test_simple_coder_flow(self):
        """A simple coding request routes to coder and returns response."""
        coder = _StubAgent(name="coder", response_content="Here is the code.")
        registry = _build_registry(coder=coder)
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle("write a hello world function")

        assert "Here is the code" in response.content
        assert coder.last_message == "write a hello world function"

    @pytest.mark.asyncio
    async def test_routes_to_correct_agent(self):
        """Router picks debugger for a bug-fix request."""
        coder = _StubAgent(name="coder", response_content="code")
        debugger = _StubAgent(name="debugger", response_content="Fixed the bug.")
        registry = _build_registry(coder=coder, debugger=debugger)
        llm = _router_llm("debugger")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle("fix the TypeError in main.py")

        assert "Fixed the bug" in response.content
        assert debugger.last_message is not None
        assert coder.last_message is None  # coder was not called

    @pytest.mark.asyncio
    async def test_explicit_agent_bypasses_router(self):
        """When agent_name is provided explicitly, routing is skipped."""
        coder = _StubAgent(name="coder", response_content="explicit response")
        registry = _build_registry(coder=coder)
        llm = _router_llm("debugger")  # router would pick debugger

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle(
            "write code",
            agent_name="coder",
        )

        assert "explicit response" in response.content

    @pytest.mark.asyncio
    async def test_context_is_passed_to_agent(self):
        """External context is forwarded to the selected agent."""
        coder = _StubAgent(name="coder", response_content="done")
        registry = _build_registry(coder=coder)
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        await orch.handle(
            "implement feature",
            context="Project uses FastAPI and SQLAlchemy",
        )

        assert "FastAPI" in (coder.last_context or "")


# ---------------------------------------------------------------------------
# Test: Planning flow
# ---------------------------------------------------------------------------


class TestPlanningFlow:
    """User message → route → planning → approve → coder → finalize."""

    @pytest.mark.asyncio
    async def test_planning_runs_before_coder(self):
        """When needs_planning, planner runs first then coder executes."""
        planner = _StubAgent(
            name="planner",
            response_content="## Implementation Plan\n1. Create auth module\n2. Add tests",
        )
        coder = _StubAgent(name="coder", response_content="Code implemented.")
        registry = _build_registry(planner=planner, coder=coder)
        llm = _router_llm("coder", needs_planning=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=True,
        )
        # Auto-approve the plan
        orch.set_clarification_handler(lambda q, opts, ctx: "Approve")

        response = await orch.handle("add OAuth2 authentication")

        # Coder should have received the plan in context
        assert coder.last_message is not None
        assert "Code implemented" in response.content
        assert planner.last_message is not None

    @pytest.mark.asyncio
    async def test_plan_rejection_returns_plan(self):
        """When user rejects the plan, the plan response is returned directly."""
        planner = _StubAgent(
            name="planner",
            response_content="## Plan\n1. Step one",
        )
        coder = _StubAgent(name="coder", response_content="Code done")
        registry = _build_registry(planner=planner, coder=coder)
        llm = _router_llm("coder", needs_planning=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=True,
        )
        orch.set_clarification_handler(lambda q, opts, ctx: "Reject")

        response = await orch.handle("add complex feature")

        # Plan should be the final response, coder should NOT have run
        assert "Plan" in response.content
        assert coder.last_message is None

    @pytest.mark.asyncio
    async def test_no_planning_when_disabled(self):
        """auto_plan=False skips planning even if router says needs_planning."""
        planner = _StubAgent(name="planner", response_content="plan")
        coder = _StubAgent(name="coder", response_content="code done")
        registry = _build_registry(planner=planner, coder=coder)
        llm = _router_llm("coder", needs_planning=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle("add feature")

        assert "code done" in response.content
        assert planner.last_message is None  # planner was not called

    @pytest.mark.asyncio
    async def test_no_planning_for_non_coder_agents(self):
        """Planning only triggers when routed to coder, not other agents."""
        planner = _StubAgent(name="planner", response_content="plan")
        debugger = _StubAgent(name="debugger", response_content="bug fixed")
        coder = _StubAgent(name="coder", response_content="code")
        registry = _build_registry(planner=planner, debugger=debugger, coder=coder)
        llm = _router_llm("debugger", needs_planning=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=True,
        )

        response = await orch.handle("fix the bug")

        assert "bug fixed" in response.content
        assert planner.last_message is None  # planner not triggered


# ---------------------------------------------------------------------------
# Test: Review flow
# ---------------------------------------------------------------------------


class TestReviewFlow:
    """Coder → reviewer → fix loop."""

    @pytest.mark.asyncio
    async def test_review_appended_to_response(self):
        """Review output is appended to the agent response."""
        coder = _StubAgent(
            name="coder",
            response_content="Wrote the feature",
            tool_calls=[{"tool": "file_write", "args": {"path": "/f.py"}, "result": "ok"}],
        )
        reviewer = _StubAgent(name="reviewer", response_content="NO_ISSUES_FOUND Looks good!")
        registry = _build_registry(coder=coder, reviewer=reviewer)
        llm = _router_llm("coder", needs_review=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=True,
            auto_plan=False,
        )

        response = await orch.handle("implement feature X")

        assert "Wrote the feature" in response.content
        assert "Auto-Review" in response.content

    @pytest.mark.asyncio
    async def test_no_review_when_disabled(self):
        """auto_review=False skips review even if router requests it."""
        coder = _StubAgent(
            name="coder",
            response_content="done",
            tool_calls=[{"tool": "file_write", "args": {"path": "/f.py"}, "result": "ok"}],
        )
        reviewer = _StubAgent(name="reviewer", response_content="issues found")
        registry = _build_registry(coder=coder, reviewer=reviewer)
        llm = _router_llm("coder", needs_review=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle("write code")

        assert "Auto-Review" not in response.content
        assert reviewer.last_message is None

    @pytest.mark.asyncio
    async def test_no_review_when_no_tool_calls(self):
        """Review is skipped if agent made no tool calls (e.g. answered a question)."""
        coder = _StubAgent(
            name="coder",
            response_content="The answer is 42",
            tool_calls=[],
        )
        reviewer = _StubAgent(name="reviewer", response_content="review")
        registry = _build_registry(coder=coder, reviewer=reviewer)
        llm = _router_llm("coder", needs_review=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=True,
            auto_plan=False,
        )

        response = await orch.handle("what does this function do?")

        assert "Auto-Review" not in response.content
        assert reviewer.last_message is None


# ---------------------------------------------------------------------------
# Test: Conversation history
# ---------------------------------------------------------------------------


class TestConversationHistory:
    """Conversation context accumulates across calls."""

    @pytest.mark.asyncio
    async def test_history_accumulates(self):
        """Each handle() call adds to conversation history."""
        coder = _StubAgent(name="coder", response_content="response")
        registry = _build_registry(coder=coder)
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        await orch.handle("first message")
        await orch.handle("second message")

        assert len(orch._conversation_history) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_clear_history(self):
        """clear_history() resets the conversation."""
        coder = _StubAgent(name="coder", response_content="r")
        registry = _build_registry(coder=coder)
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        await orch.handle("message")
        orch.clear_history()

        assert len(orch._conversation_history) == 0


# ---------------------------------------------------------------------------
# Test: RAG context injection in orchestration
# ---------------------------------------------------------------------------


class TestRAGInOrchestration:
    """RAG retriever injects relevant context during agent execution."""

    @pytest.mark.asyncio
    async def test_rag_context_injected_into_agent(self):
        """When a retriever is set, its results appear in agent context."""
        coder = _StubAgent(name="coder", response_content="implemented")
        registry = _build_registry(coder=coder)
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = (
            "## Relevant Code Context\n"
            "### [1] src/auth.py (L1-30) [function: login] (score: 0.92)\n"
            "```python\ndef login(): pass\n```"
        )
        orch.set_context_retriever(mock_retriever)

        await orch.handle("update the login function")

        # Agent should have received RAG context
        assert "Relevant Code Context" in (coder.last_context or "")
        assert "login" in (coder.last_context or "")

    @pytest.mark.asyncio
    async def test_rag_index_updated_on_file_write(self):
        """After agent writes files, RAG index is updated."""
        coder = _StubAgent(
            name="coder",
            response_content="done",
            tool_calls=[
                {"tool": "file_write", "args": {"path": "/tmp/new.py"}, "result": "ok"},
            ],
        )
        registry = _build_registry(coder=coder)
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = ""
        orch.set_context_retriever(mock_retriever)

        await orch.handle("create a new file")

        mock_retriever.update_file.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Memory extraction in finalize
# ---------------------------------------------------------------------------


class TestMemoryExtraction:
    """Auto-memory extraction runs in finalize node."""

    @pytest.mark.asyncio
    async def test_memory_extracted_when_store_set(self):
        """When memory_store is set, extraction LLM call is made."""
        coder = _StubAgent(
            name="coder",
            response_content="Created auth module with JWT tokens",
            tool_calls=[
                {"tool": "file_write", "args": {"path": "/auth.py"}, "result": "ok"},
            ],
        )
        # Need 2+ agents so router actually calls LLM (1 agent = skip routing)
        debugger = _StubAgent(name="debugger", response_content="debug")
        registry = _build_registry(coder=coder, debugger=debugger)

        # Router call returns coder, memory extraction returns a learning
        router_response = LLMResponse(
            content=json.dumps({"agent": "coder", "needs_review": False, "needs_planning": False}),
            model="test",
        )
        extraction_response = LLMResponse(
            content='[{"key": "jwt-auth", "content": "Use JWT for auth", "category": "decision"}]',
            model="test",
        )
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=[router_response, extraction_response])

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        mock_memory = MagicMock()
        orch.set_memory_store(mock_memory)

        await orch.handle("add JWT authentication")

        # Verify: routing call + extraction call = 2 LLM calls total
        assert llm.complete.call_count == 2
        mock_memory.add.assert_called_once()
        # Verify the saved memory entry
        call_kwargs = mock_memory.add.call_args[1]
        assert call_kwargs["key"] == "jwt-auth"
        assert call_kwargs["category"] == "decision"


# ---------------------------------------------------------------------------
# Test: Error resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """Orchestrator handles agent failures gracefully."""

    @pytest.mark.asyncio
    async def test_unknown_agent_returns_error(self):
        """Selecting a non-existent agent returns an error response."""
        registry = _build_registry()
        llm = _router_llm("nonexistent_agent")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle("do something")

        # Should get default agent error or fallback
        assert response.content  # Has some content (error or default)

    @pytest.mark.asyncio
    async def test_agent_exception_is_caught(self):
        """Agent raising an exception returns error response, not crash."""
        class _CrashingAgent(BaseAgent):
            def __init__(self):
                config = AgentConfig(name="coder", description="crashes", system_prompt="t")
                super().__init__(config=config, llm=MagicMock(), tool_registry=MagicMock())

            def get_system_prompt(self) -> str:
                return "t"

            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                raise RuntimeError("Agent crashed!")

        registry = AgentRegistry()
        registry.register(_CrashingAgent())
        llm = _router_llm("coder")

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=False,
            auto_plan=False,
        )

        response = await orch.handle("trigger crash")

        assert "error" in response.content.lower() or "crashed" in response.content.lower()


# ---------------------------------------------------------------------------
# Test: Full pipeline (planning + review)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Complete flow: routing → planning → approval → coder → review → finalize."""

    @pytest.mark.asyncio
    async def test_plan_then_code_then_review(self):
        """Full pipeline: plan → approve → code → review → response."""
        planner = _StubAgent(
            name="planner",
            response_content="## Implementation Plan\n1. Create module\n2. Add tests",
        )
        coder = _StubAgent(
            name="coder",
            response_content="Module created with tests.",
            tool_calls=[
                {"tool": "file_write", "args": {"path": "/m.py"}, "result": "ok"},
            ],
        )
        reviewer = _StubAgent(
            name="reviewer",
            response_content="NO_ISSUES_FOUND Code looks great!",
        )
        registry = _build_registry(
            planner=planner,
            coder=coder,
            reviewer=reviewer,
        )
        llm = _router_llm("coder", needs_review=True, needs_planning=True)

        orch = GraphOrchestrator(
            llm=llm,
            agent_registry=registry,
            auto_review=True,
            auto_plan=True,
        )
        orch.set_clarification_handler(lambda q, opts, ctx: "Approve")

        response = await orch.handle("add a new authentication module")

        # All three agents should have executed
        assert planner.last_message is not None
        assert coder.last_message is not None
        assert reviewer.last_message is not None
        # Response includes both coder output and review
        assert "Module created" in response.content
        assert "Auto-Review" in response.content
