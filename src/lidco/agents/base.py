"""Base agent architecture."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from typing import Callable

from lidco.core.clarification import ClarificationNeeded
from lidco.core.conversation_pruner import (
    compress_tool_results,
    prune_conversation,
    summarize_conversation_if_needed,
)
from lidco.core.token_estimation import estimate_conversation_tokens
from lidco.core.truncation import truncate_tool_result
from lidco.llm.base import BaseLLMProvider, LLMResponse, Message
from lidco.llm.litellm_provider import calculate_cost
from lidco.tools.base import BaseTool, ToolResult
from lidco.tools.registry import ToolRegistry

# ── Streaming narration prompt ──────────────────────────────────────────────
# Appended to every agent's system prompt when streaming is active so the
# user sees a conversational reasoning flow instead of silent tool calls.

_STREAMING_NARRATION_PROMPT = """

## Streaming Style
Think out loud like a senior engineer:
- Before tools: say WHAT you're looking for and WHY (NOT "I'll read auth.py" — SAY "Looking for existing session handling")
- After results: share what's relevant (e.g., "Auth class found — I'll extend its login method" or "No JWT yet, adding it")
- Before writing: state your approach in one sentence
Keep to 1 sentence. Never describe tool mechanics — focus on intent and findings.
"""

# ── Clarification hint (appended when agent has ask_user tool) ──────────────
_CLARIFICATION_HINT = """

## Clarification
When the request is ambiguous or multiple valid approaches exist, use ask_user. Do NOT use for trivial decisions.
"""


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    description: str
    system_prompt: str
    model: str | None = None  # None = use default
    temperature: float = 0.1
    max_tokens: int = 4096
    tools: list[str] = field(default_factory=list)  # tool names
    max_iterations: int = 200  # prevent infinite loops
    fallback_model: str | None = None
    context_window: int = 128_000  # tokens; override per model if known
    routing_keywords: list[str] = field(default_factory=list)


@dataclass
class AgentMessage:
    """A message in the agent's conversation."""

    role: str
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class TokenUsage:
    """Cumulative token usage across LLM calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def add(self, usage: dict[str, int], cost_usd: float = 0.0) -> None:
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)
        self.total_cost_usd += cost_usd


@dataclass
class AgentResponse:
    """Final response from an agent."""

    content: str
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    model_used: str = ""
    token_usage: TokenUsage = field(default_factory=TokenUsage)


class BaseAgent(ABC):
    """Abstract base for all agents. Implements ReAct pattern."""

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMProvider,
        tool_registry: ToolRegistry,
    ) -> None:
        self._config = config
        self._llm = llm
        self._tool_registry = tool_registry
        self._conversation: list[Message] = []
        self._status_callback: Any | None = None
        self._permission_handler: Any | None = None
        self._token_callback: Any | None = None
        self._continue_handler: Any | None = None
        self._clarification_handler: Any | None = None
        self._stream_callback: Callable[[str], None] | None = None
        self._tool_event_callback: Callable[[str, str, dict, ToolResult | None], None] | None = None
        self._error_callback: Callable[..., None] | None = None
        # Cache tool schemas once — tools don't change between runs
        self._tool_schemas_cache: list[dict[str, Any]] | None = None
        # Per-run context injection — consumed once by build_system_prompt
        self._pending_context: list[str] = []

    def set_status_callback(self, callback: Any) -> None:
        """Set a callback to report status updates."""
        self._status_callback = callback

    def set_permission_handler(self, handler: Any) -> None:
        """Set a callback to check tool permissions. handler(tool_name, args) -> bool."""
        self._permission_handler = handler

    def set_token_callback(self, callback: Any) -> None:
        """Set a callback to report token usage.

        callback(total_tokens: int, total_cost_usd: float) -> None
        """
        self._token_callback = callback

    def set_continue_handler(self, handler: Any) -> None:
        """Set a callback to ask user to continue. handler(iteration, max) -> bool."""
        self._continue_handler = handler

    def set_clarification_handler(self, handler: Any) -> None:
        """Set a callback to handle clarification questions.

        handler(question: str, options: list[str], context: str) -> str
        """
        self._clarification_handler = handler

    def set_stream_callback(self, callback: Callable[[str], None] | None) -> None:
        """Set a callback to receive text chunks as they stream from the LLM."""
        self._stream_callback = callback

    def set_error_callback(self, callback: Callable[..., None] | None) -> None:
        """Set a callback fired on every tool failure.

        callback(record: ErrorRecord) -> None
        """
        self._error_callback = callback

    def clone(self) -> "BaseAgent":
        """Create a fresh instance sharing the same config, LLM, and tool registry.

        Used by the parallel execution engine to give each parallel step its own
        empty ``_conversation`` list.  Subclasses that require additional ``__init__``
        arguments must override this method.
        """
        return type(self)(
            config=self._config,
            llm=self._llm,
            tool_registry=self._tool_registry,
        )

    def prepend_system_context(self, text: str) -> None:
        """Inject *text* at the top of the context block for the next run only.

        Appends to ``_pending_context``; the list is consumed and reset by
        ``build_system_prompt`` so subsequent runs start clean.
        """
        self._pending_context.append(text)

    def set_tool_event_callback(
        self, callback: Callable[[str, str, dict, ToolResult | None], None] | None
    ) -> None:
        """Set a callback for tool call events.

        callback(event, tool_name, args, result) where event is "start" or "end".
        """
        self._tool_event_callback = callback

    def _report_status(self, status: str) -> None:
        if self._status_callback is not None:
            self._status_callback(f"{self._config.name} · {status}")

    def _report_token_usage(self, usage: TokenUsage) -> None:
        if self._token_callback is not None:
            self._token_callback(usage.total_tokens, usage.total_cost_usd)

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def description(self) -> str:
        return self._config.description

    @property
    def config(self) -> AgentConfig:
        return self._config

    def _get_tools(self) -> list[BaseTool]:
        """Get the tools this agent can use."""
        if not self._config.tools:
            return self._tool_registry.list_tools()
        return [
            t for t in self._tool_registry.list_tools()
            if t.name in self._config.tools
        ]

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format tool schemas for this agent's tools (cached)."""
        if self._tool_schemas_cache is None:
            self._tool_schemas_cache = [t.to_openai_schema() for t in self._get_tools()]
        return self._tool_schemas_cache

    async def _stream_complete(
        self,
        llm_kwargs: dict[str, Any],
    ) -> LLMResponse:
        """Call the LLM with streaming, forwarding chunks to _stream_callback.

        Accumulates content and tool_calls from delta chunks, extracts usage
        from the final chunk, and returns a fully assembled LLMResponse.
        """
        import json as _json

        full_content = ""
        accumulated_tool_calls: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] = {}
        finish_reason = "stop"
        model = llm_kwargs.get("model") or ""

        async for chunk in self._llm.stream(self._conversation, **llm_kwargs):
            # Accumulate text
            if chunk.content:
                full_content += chunk.content
                if self._stream_callback is not None:
                    self._stream_callback(chunk.content)

            # Accumulate tool call deltas (indexed by position)
            for tc_delta in chunk.tool_calls:
                idx = tc_delta.get("index", 0)
                if idx not in accumulated_tool_calls:
                    accumulated_tool_calls[idx] = {
                        "id": tc_delta.get("id") or "",
                        "type": "function",
                        "function": {
                            "name": tc_delta.get("function", {}).get("name") or "",
                            "arguments": "",
                        },
                    }
                else:
                    # Merge: update id/name if present, append arguments
                    if tc_delta.get("id"):
                        accumulated_tool_calls[idx]["id"] = tc_delta["id"]
                    fname = tc_delta.get("function", {}).get("name")
                    if fname:
                        accumulated_tool_calls[idx]["function"]["name"] = fname

                arg_chunk = tc_delta.get("function", {}).get("arguments") or ""
                accumulated_tool_calls[idx]["function"]["arguments"] += arg_chunk

            # Extract usage from final chunk
            if chunk.usage:
                usage = {**chunk.usage}

            if chunk.finish_reason:
                finish_reason = chunk.finish_reason

        tool_calls = [accumulated_tool_calls[k] for k in sorted(accumulated_tool_calls)]
        cost = calculate_cost(model, usage)

        return LLMResponse(
            content=full_content,
            model=model,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            cost_usd=cost,
        )

    async def run(self, user_message: str, context: str = "") -> AgentResponse:
        """Execute the agent's ReAct loop.

        1. Build messages with system prompt + context + user message
        2. Call LLM
        3. If LLM wants to call tools, execute them and loop
        4. If LLM returns text, return it as the final response
        """
        # Build initial messages — system prompt is assembled dynamically so
        # subclasses can customise it or conditional hints can be toggled off.
        system_content = self.build_system_prompt(context)

        self._conversation = [
            Message(role="system", content=system_content),
            Message(role="user", content=user_message),
        ]

        tool_schemas = self._get_tool_schemas()
        all_tool_calls: list[dict[str, Any]] = []
        usage = TokenUsage()
        iteration = 0
        max_iter = self._config.max_iterations

        while True:
            # Check if we hit the iteration limit
            if iteration >= max_iter:
                if self._continue_handler is not None:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    should_continue = await loop.run_in_executor(
                        None, self._continue_handler, iteration, max_iter,
                    )
                    if should_continue:
                        max_iter += self._config.max_iterations
                    else:
                        break
                else:
                    break

            iteration += 1

            # Summarize old turns before pruning when conversation is long.
            # Summarization is tried first (preserves semantic content);
            # pruning is a hard fallback for extreme sizes.
            # Use the fallback model (cheaper) for summarization when available.
            if len(self._conversation) > 8:
                summarize_model = self._config.fallback_model or self._config.model
                self._conversation = await summarize_conversation_if_needed(
                    self._conversation,
                    self._llm,
                    model=summarize_model,
                )

            # Compress large tool results early — reduces token pressure before
            # the harder message-level pruning step below kicks in.
            if len(self._conversation) > 8:
                self._conversation = compress_tool_results(self._conversation)

            # Prune conversation if it's getting large (> 8 messages or
            # estimated tokens exceed threshold of the model's context window).
            # Start early (75%/50%) to avoid quality degradation near the limit.
            if len(self._conversation) > 8:
                est_tokens = estimate_conversation_tokens(self._conversation)
                context_limit = self._config.context_window
                # 4 chars per token; prune to 40% or 60% of context window
                if est_tokens > context_limit * 0.75:
                    self._conversation = prune_conversation(
                        self._conversation,
                        max_chars=int(context_limit * 4 * 0.40),
                    )
                elif est_tokens > context_limit * 0.50:
                    self._conversation = prune_conversation(
                        self._conversation,
                        max_chars=int(context_limit * 4 * 0.60),
                    )

            if iteration == 1:
                self._report_status("Analyzing request")
            else:
                self._report_status("Processing results")
            llm_kwargs: dict[str, Any] = {
                "model": self._config.model,
                "temperature": self._config.temperature,
                "max_tokens": self._config.max_tokens,
                "tools": tool_schemas if tool_schemas else None,
            }
            if not self._config.model:
                llm_kwargs["role"] = self._config.name

            try:
                if self._stream_callback is not None:
                    response = await self._stream_complete(llm_kwargs)
                else:
                    response = await self._llm.complete(
                        self._conversation,
                        **llm_kwargs,
                    )
            except Exception as _llm_exc:
                # Import here to avoid circular imports at module load time.
                from lidco.llm.exceptions import LLMRetryExhausted
                if isinstance(_llm_exc, LLMRetryExhausted) and self._error_callback is not None:
                    from lidco.core.errors import ErrorRecord
                    _record = ErrorRecord(
                        id=uuid.uuid4().hex,
                        timestamp=datetime.now(timezone.utc),
                        tool_name="llm",
                        agent_name=self._config.name,
                        error_type="llm_error",
                        message=str(_llm_exc),
                        traceback_str=None,
                        file_hint=None,
                    )
                    self._error_callback(_record)
                raise
            usage.add(response.usage, cost_usd=response.cost_usd)
            self._report_token_usage(usage)

            # No tool calls - we have a final answer
            if not response.tool_calls:
                return AgentResponse(
                    content=response.content,
                    tool_calls_made=all_tool_calls,
                    iterations=iteration,
                    model_used=response.model,
                    token_usage=usage,
                )

            # Process tool calls
            self._conversation.append(
                Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            # Parse all tool calls and check if all are read-only
            import json
            import asyncio

            parsed_calls: list[tuple[dict, str, dict]] = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}
                parsed_calls.append((tool_call, tool_name, tool_args))
                # all_tool_calls is populated after execution to capture result_preview

            read_only_tools = {"file_read", "glob", "grep"}
            all_read_only = (
                len(parsed_calls) > 1
                and all(name in read_only_tools for _, name, _ in parsed_calls)
            )

            if all_read_only:
                # Execute read-only tools in parallel
                async def _run_one(tc: dict, name: str, args: dict) -> tuple[dict, str, dict, ToolResult]:
                    if self._tool_event_callback is not None:
                        self._tool_event_callback("start", name, args, None)
                    result = await self._execute_tool(name, args)
                    if self._tool_event_callback is not None:
                        self._tool_event_callback("end", name, args, result)
                    return tc, name, args, result

                if all(name == "file_read" for _, name, _ in parsed_calls):
                    from pathlib import Path as _Path
                    file_names = ", ".join(
                        _Path(args.get("path", "file")).name
                        for _, _, args in parsed_calls
                    )
                    self._report_status(f"Reading {file_names}")
                else:
                    self._report_status(f"Exploring {len(parsed_calls)} locations")
                results = await asyncio.gather(
                    *(_run_one(tc, name, args) for tc, name, args in parsed_calls)
                )
                _read_tools = {"file_read", "glob", "grep"}
                for tc, name, args, result in results:
                    raw = self._format_tool_result(result)
                    preview = raw[:400] if result.success and name in _read_tools else ""
                    all_tool_calls.append({"tool": name, "args": args, "result_preview": preview})
                    self._conversation.append(
                        Message(
                            role="tool",
                            content=truncate_tool_result(name, raw),
                            tool_call_id=tc.get("id", ""),
                            name=name,
                        )
                    )
            else:
                # Execute sequentially (write tools or single tool)
                _read_tools = {"file_read", "glob", "grep"}
                for tool_call, tool_name, tool_args in parsed_calls:
                    self._report_status(self._describe_tool_call(tool_name, tool_args))

                    if self._tool_event_callback is not None:
                        self._tool_event_callback("start", tool_name, tool_args, None)

                    result = await self._execute_tool(tool_name, tool_args)

                    if self._tool_event_callback is not None:
                        self._tool_event_callback("end", tool_name, tool_args, result)

                    raw = self._format_tool_result(result)
                    preview = raw[:400] if result.success and tool_name in _read_tools else ""
                    all_tool_calls.append({"tool": tool_name, "args": tool_args, "result_preview": preview})
                    self._conversation.append(
                        Message(
                            role="tool",
                            content=truncate_tool_result(tool_name, raw),
                            tool_call_id=tool_call.get("id", ""),
                            name=tool_name,
                        )
                    )

        # Max iterations reached (user declined to continue)
        return AgentResponse(
            content="Reached maximum iterations. Here's what I have so far.",
            tool_calls_made=all_tool_calls,
            iterations=iteration,
            model_used=self._config.model or "",
            token_usage=usage,
        )

    async def _execute_tool(self, tool_name: str, tool_args: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with permission checks and status reporting."""
        tool = self._tool_registry.get(tool_name)
        if not tool:
            return ToolResult(output="", success=False, error=f"Unknown tool: {tool_name}")

        # Report descriptive thinking status
        desc = self._describe_tool_call(tool_name, tool_args)
        self._report_status(desc)

        # Check permission (run in executor to avoid blocking the event loop)
        if self._permission_handler is not None:
            import asyncio
            loop = asyncio.get_event_loop()
            allowed = await loop.run_in_executor(
                None, self._permission_handler, tool_name, tool_args,
            )
            if not allowed:
                return ToolResult(output="", success=False, error="Operation denied by user")

        # Forward the stream callback so streaming-capable tools (e.g.
        # RunTestsTool with stream_output=True) can push progress lines to
        # the same display as LLM text chunks.
        tool.set_progress_callback(self._stream_callback)

        try:
            result = await tool.execute(**tool_args)
        except ClarificationNeeded as clarification:
            if self._clarification_handler is not None:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    answer = await loop.run_in_executor(
                        None,
                        self._clarification_handler,
                        clarification.question,
                        clarification.options,
                        clarification.context,
                    )
                    return ToolResult(
                        output=f"User answered: {answer}",
                        success=True,
                        metadata={"clarification_answer": answer},
                    )
                except Exception as e:
                    return ToolResult(
                        output="",
                        success=False,
                        error=f"Clarification handler failed: {e}",
                    )
            return ToolResult(
                output="",
                success=False,
                error="No clarification handler available to ask the user.",
            )

        # Fire error callback so session can track tool failures
        if not result.success and self._error_callback is not None:
            from lidco.core.errors import ErrorRecord, extract_file_hint, _compact_args
            record = ErrorRecord(
                id=uuid.uuid4().hex,
                timestamp=datetime.now(timezone.utc),
                tool_name=tool_name,
                agent_name=self._config.name,
                error_type="exception" if result.traceback_str else "tool_error",
                message=result.error or "unknown error",
                traceback_str=result.traceback_str,
                file_hint=extract_file_hint(result.traceback_str),
                tool_args=_compact_args(tool_args) if tool_args else None,
            )
            self._error_callback(record)
        return result

    @staticmethod
    def _describe_tool_call(tool_name: str, args: dict[str, Any]) -> str:
        """Return a human-readable description of a tool call for status display."""
        from pathlib import Path
        if tool_name == "file_write":
            return f"Creating {Path(args.get('path', 'file')).name}"
        if tool_name == "file_edit":
            return f"Editing {Path(args.get('path', 'file')).name}"
        if tool_name == "file_read":
            return f"Reading {Path(args.get('path', 'file')).name}"
        if tool_name == "bash":
            cmd = str(args.get("command", ""))
            if len(cmd) > 50:
                cmd = cmd[:50] + "..."
            return f"$ {cmd}"
        if tool_name == "grep":
            pattern = str(args.get("pattern", ""))
            return f"Searching '{pattern}'"
        if tool_name == "glob":
            pattern = str(args.get("pattern", ""))
            return f"Finding '{pattern}'"
        if tool_name == "git":
            return f"Git: {args.get('subcommand', 'operation')}"
        if tool_name == "ask_user":
            q = str(args.get("question", ""))
            if len(q) > 60:
                q = q[:60] + "..."
            return f"Asking user: {q}"
        return f"Using {tool_name}"

    def build_system_prompt(self, context: str = "") -> str:
        """Assemble the complete system prompt for one agent invocation.

        Starts from ``self._config.system_prompt`` and appends conditional
        sections based on the agent's declared tools and active streaming mode:

        * ``_STREAMING_NARRATION_PROMPT`` — added when a stream callback is set
          so the model narrates its reasoning as it works.
        * ``_CLARIFICATION_HINT`` — added when the agent has the ``ask_user``
          tool (or no tool restriction), prompting it to ask before guessing.
        * The provided *context* block appended as ``## Current Context``.

        Subclasses may override this method to extend or replace these defaults.
        """
        prompt = self._config.system_prompt or self.get_system_prompt()

        if self._stream_callback is not None:
            prompt += _STREAMING_NARRATION_PROMPT

        if not self._config.tools or "ask_user" in self._config.tools:
            prompt += _CLARIFICATION_HINT

        # Consume pending context (injected by prepend_system_context) then reset.
        # Pending sections are placed at the top of the context block so they
        # receive higher attention from the model (e.g. failure-site snippets
        # injected before the debugger runs).
        pending = self._pending_context
        self._pending_context = []

        context_parts: list[str] = []
        if pending:
            context_parts.extend(pending)
        if context:
            context_parts.append(context)

        if context_parts:
            prompt += f"\n\n## Current Context\n" + "\n\n".join(context_parts)

        return prompt

    @staticmethod
    def _format_tool_result(result: ToolResult, *, traceback_cap: int = 3000) -> str:
        """Format a ToolResult for inclusion in the conversation.

        For successful results returns the plain output.  For failures,
        appends the captured traceback (capped at *traceback_cap* chars) so the
        LLM can see the failure site without needing another tool call.
        """
        if result.success:
            return result.output
        error_text = f"Error: {result.error}"
        if result.traceback_str:
            tb = result.traceback_str[:traceback_cap]
            if len(result.traceback_str) > traceback_cap:
                tb += "\n...[traceback truncated]"
            error_text += f"\n\nTraceback:\n{tb}"
        return error_text

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent. Override in subclasses."""
