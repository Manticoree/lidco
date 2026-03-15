"""Skill chaining — Task 295.

Parses and executes ``skill1 | skill2 | skill3`` pipelines where
the output of each skill becomes the ``{args}`` input of the next.

Usage::

    chain = SkillChain(registry, session)
    result = await chain.run("review | summarize", initial_args="src/auth.py")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session
    from lidco.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


@dataclass
class ChainStep:
    """Result of one step in a skill chain."""

    skill_name: str
    prompt: str
    output: str = ""
    error: str = ""
    success: bool = True


@dataclass
class ChainResult:
    """Result of a full skill chain execution."""

    steps: list[ChainStep] = field(default_factory=list)
    final_output: str = ""
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and all(s.success for s in self.steps)

    def summary(self) -> str:
        lines: list[str] = []
        for i, step in enumerate(self.steps, 1):
            icon = "✅" if step.success else "❌"
            lines.append(f"{icon} Step {i}: `{step.skill_name}`")
            if not step.success and step.error:
                lines.append(f"   Error: {step.error[:100]}")
        if self.final_output:
            lines.append(f"\n**Output:**\n{self.final_output[:1000]}")
        return "\n".join(lines)


def parse_chain(expression: str) -> list[tuple[str, str]]:
    """Parse a pipe-separated skill expression.

    Returns list of (skill_name, initial_args) tuples.
    The initial_args only applies to the first skill; subsequent
    skills receive the previous output as args.

    Examples::

        parse_chain("review src/auth.py | summarize")
        → [("review", "src/auth.py"), ("summarize", "")]

        parse_chain("lint | fix | format")
        → [("lint", ""), ("fix", ""), ("format", "")]
    """
    parts = [p.strip() for p in expression.split("|")]
    result: list[tuple[str, str]] = []
    for part in parts:
        tokens = part.split(maxsplit=1)
        name = tokens[0].lstrip("/") if tokens else ""
        args = tokens[1] if len(tokens) > 1 else ""
        if name:
            result.append((name, args))
    return result


class SkillChain:
    """Executes a chain of skills, piping output through them.

    Args:
        registry: Loaded SkillRegistry.
        session: Active LIDCO session for LLM calls.
    """

    def __init__(self, registry: "SkillRegistry", session: "Session") -> None:
        self._registry = registry
        self._session = session

    async def run(self, expression: str, initial_args: str = "") -> ChainResult:
        """Execute a pipe-chained skill expression.

        Args:
            expression: e.g. ``"review | summarize"`` or ``"lint src/ | fix"``
            initial_args: Passed as args to the first skill if it has none.
        """
        steps_def = parse_chain(expression)
        if not steps_def:
            return ChainResult(error="Empty chain expression")

        result = ChainResult()
        current_input = initial_args

        for i, (skill_name, skill_args) in enumerate(steps_def):
            skill = self._registry.get(skill_name)
            if skill is None:
                step = ChainStep(
                    skill_name=skill_name,
                    prompt="",
                    error=f"Skill '{skill_name}' not found",
                    success=False,
                )
                result.steps.append(step)
                result.error = step.error
                return result

            # First step uses skill_args or initial_args; subsequent steps use previous output
            args = skill_args if i == 0 and skill_args else current_input

            # Check requirements
            missing = skill.check_requirements()
            if missing:
                step = ChainStep(
                    skill_name=skill_name,
                    prompt="",
                    error=f"Missing required tools: {', '.join(missing)}",
                    success=False,
                )
                result.steps.append(step)
                result.error = step.error
                return result

            # Run pre-script
            skill.run_script("pre")

            prompt = skill.render(args)
            step = ChainStep(skill_name=skill_name, prompt=prompt)

            try:
                # Inject context file if specified
                context = ""
                if skill.context:
                    try:
                        from pathlib import Path as _Path
                        ctx_path = _Path(skill.context)
                        if ctx_path.is_file():
                            context = ctx_path.read_text(encoding="utf-8", errors="replace")[:3000]
                        elif ctx_path.is_dir():
                            context = f"Working in directory: {skill.context}"
                    except OSError:
                        pass

                response = await self._session.orchestrator.handle(
                    prompt,
                    context=context or None,
                )
                step.output = response.content if hasattr(response, "content") else str(response)
                step.success = True
                current_input = step.output

            except Exception as exc:
                step.error = str(exc)
                step.success = False
                result.steps.append(step)
                result.error = f"Step '{skill_name}' failed: {exc}"
                return result

            # Run post-script
            skill.run_script("post")
            result.steps.append(step)

        result.final_output = current_input
        return result
