"""Role-specialized sub-agent factory (Devin 2.0 parity).

Each role gets a tailored system prompt and a restricted tool list so the agent
focuses on its responsibility without accidentally performing out-of-scope work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

ROLE_SYSTEM_PROMPTS: dict[str, str] = {
    "coder": (
        "You are a focused coding agent. Your ONLY job is to write correct, "
        "clean, minimal code that satisfies the given requirement. Do not write "
        "tests, do not plan, do not review — just implement."
    ),
    "reviewer": (
        "You are a strict code reviewer. Analyse the given code diff or source "
        "for bugs, security issues, style violations, and maintainability problems. "
        "Return structured findings with severity (CRITICAL/HIGH/MEDIUM/LOW). "
        "Do not write new code — only review."
    ),
    "tester": (
        "You are a test-writing specialist. Given a module or function, write "
        "comprehensive pytest unit tests that cover happy paths, edge cases, and "
        "error conditions. Aim for 80 %+ branch coverage. Do not implement "
        "production code — only tests."
    ),
    "planner": (
        "You are a planning agent. Break the given task into a numbered list of "
        "concrete, atomic steps. Each step must be independently verifiable. "
        "Output only the plan — do not implement anything."
    ),
    "debugger": (
        "You are a debugging specialist. Given a failing test output or traceback, "
        "identify the root cause and propose the minimal code change to fix it. "
        "Show only the relevant diff — no full rewrites."
    ),
    "documenter": (
        "You are a documentation agent. Write clear, concise docstrings and "
        "inline comments for the given code. Follow Google-style docstrings. "
        "Do not change logic — only add/improve documentation."
    ),
}

ROLE_TOOLS: dict[str, list[str]] = {
    "coder": ["read_file", "write_file", "run_command"],
    "reviewer": ["read_file", "run_command"],
    "tester": ["read_file", "write_file", "run_command"],
    "planner": ["read_file"],
    "debugger": ["read_file", "write_file", "run_command"],
    "documenter": ["read_file", "write_file"],
}

VALID_ROLES = list(ROLE_SYSTEM_PROMPTS.keys())


@dataclass
class RoleAgentConfig:
    role: str
    system_prompt: str
    allowed_tools: list[str]
    extra_context: str = ""

    def full_prompt(self) -> str:
        parts = [self.system_prompt]
        if self.extra_context:
            parts.append(f"\nAdditional context:\n{self.extra_context}")
        return "\n".join(parts)


@dataclass
class AgentTask:
    role: str
    instructions: str
    context: str = ""


@dataclass
class AgentResult:
    role: str
    instructions: str
    response: str
    success: bool
    error: str = ""


class RoleAgentFactory:
    """Create and dispatch role-specialized sub-agents.

    Parameters
    ----------
    llm_callback:
        Async callable that accepts (system_prompt: str, user_message: str)
        and returns a string response.  Supply None for testing / dry runs.
    custom_roles:
        Extend or override the built-in roles.
    """

    def __init__(
        self,
        llm_callback: Callable[[str, str], Awaitable[str]] | None = None,
        custom_roles: dict[str, str] | None = None,
    ) -> None:
        self._llm = llm_callback
        self._prompts: dict[str, str] = {**ROLE_SYSTEM_PROMPTS}
        self._tools: dict[str, list[str]] = {**ROLE_TOOLS}
        if custom_roles:
            for role, prompt in custom_roles.items():
                self._prompts[role] = prompt
                self._tools.setdefault(role, [])

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def available_roles(self) -> list[str]:
        return list(self._prompts.keys())

    def get_config(self, role: str, extra_context: str = "") -> RoleAgentConfig:
        if role not in self._prompts:
            raise ValueError(f"Unknown role '{role}'. Available: {self.available_roles()}")
        return RoleAgentConfig(
            role=role,
            system_prompt=self._prompts[role],
            allowed_tools=list(self._tools.get(role, [])),
            extra_context=extra_context,
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, task: AgentTask) -> AgentResult:
        """Run a role agent for *task* and return its response."""
        config = self.get_config(task.role, extra_context=task.context)
        system = config.full_prompt()

        if self._llm is None:
            # Dry-run / test mode
            response = f"[{task.role.upper()}] (no LLM configured) — task: {task.instructions[:80]}"
            return AgentResult(role=task.role, instructions=task.instructions, response=response, success=True)

        try:
            response = await self._llm(system, task.instructions)
            return AgentResult(role=task.role, instructions=task.instructions, response=response, success=True)
        except Exception as exc:
            return AgentResult(
                role=task.role,
                instructions=task.instructions,
                response="",
                success=False,
                error=str(exc),
            )

    async def dispatch_many(self, tasks: list[AgentTask]) -> list[AgentResult]:
        """Dispatch multiple tasks sequentially (use WorkerPool for parallel)."""
        return [await self.dispatch(t) for t in tasks]

    def add_role(self, role: str, system_prompt: str, tools: list[str] | None = None) -> None:
        """Register a custom role."""
        self._prompts[role] = system_prompt
        self._tools[role] = tools or []
