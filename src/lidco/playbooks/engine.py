"""
Playbook Engine — Devin-style reusable multi-step workflow scripts.

Discovers .lidco/playbooks/*.yaml (project) + ~/.lidco/playbooks/*.yaml (global).
Project playbooks override global by name.

YAML format:
  name: deploy
  description: Deploy to production
  steps:
    - type: run
      command: "npm run build"
    - type: prompt
      message: "Summarise the build output: {{output}}"
    - type: tool
      command: "/git commit -m 'deploy'"
    - type: condition
      if: "{{exit_code}} == 0"
      then:
        - type: run
          command: "echo success"
      else:
        - type: run
          command: "echo failed"
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


try:
    import yaml  # type: ignore[import]
except ImportError:
    yaml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlaybookStep:
    type: str  # run | prompt | tool | condition
    command: str = ""
    message: str = ""
    condition: str = ""
    then_steps: list["PlaybookStep"] = field(default_factory=list)
    else_steps: list["PlaybookStep"] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Playbook:
    name: str
    description: str
    steps: list[PlaybookStep]
    source_path: str = ""


@dataclass
class StepResult:
    step_index: int
    type: str
    success: bool
    output: str = ""
    error: str = ""


@dataclass
class PlaybookResult:
    name: str
    steps_completed: int
    steps_total: int
    success: bool
    step_results: list[StepResult] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)

    @property
    def output(self) -> str:
        return "\n".join(r.output for r in self.step_results if r.output)


# ---------------------------------------------------------------------------
# YAML parsing helpers
# ---------------------------------------------------------------------------

def _parse_step(raw: dict[str, Any]) -> PlaybookStep:
    step_type = raw.get("type", "run")
    step = PlaybookStep(
        type=step_type,
        command=raw.get("command", ""),
        message=raw.get("message", ""),
        condition=raw.get("if", ""),
        raw=raw,
    )
    if step_type == "condition":
        step.then_steps = [_parse_step(s) for s in raw.get("then", [])]
        step.else_steps = [_parse_step(s) for s in raw.get("else", [])]
    return step


def _parse_playbook(data: dict[str, Any], source_path: str = "") -> Playbook:
    steps = [_parse_step(s) for s in data.get("steps", [])]
    return Playbook(
        name=data.get("name", Path(source_path).stem),
        description=data.get("description", ""),
        steps=steps,
        source_path=source_path,
    )


# ---------------------------------------------------------------------------
# PlaybookEngine
# ---------------------------------------------------------------------------

class PlaybookEngine:
    """
    Discovers and executes YAML playbooks from:
      - .lidco/playbooks/*.yaml  (project)
      - ~/.lidco/playbooks/*.yaml (global)

    Project playbooks override global ones by name.
    """

    def __init__(
        self,
        project_root: str | None = None,
        global_root: str | None = None,
        llm_callback: Callable[[str], str] | None = None,
        tool_callback: Callable[[str], str] | None = None,
        timeout: int = 60,
    ) -> None:
        self._project_root = Path(project_root) if project_root else Path.cwd()
        self._global_root = Path(global_root) if global_root else Path.home()
        self._llm_callback = llm_callback
        self._tool_callback = tool_callback
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _project_dir(self) -> Path:
        return self._project_root / ".lidco" / "playbooks"

    def _global_dir(self) -> Path:
        return self._global_root / ".lidco" / "playbooks"

    def _discover_paths(self) -> dict[str, Path]:
        """Return name → path mapping; project overrides global."""
        paths: dict[str, Path] = {}
        for directory in (self._global_dir(), self._project_dir()):
            if directory.is_dir():
                for p in sorted(directory.glob("*.yaml")):
                    paths[p.stem] = p
                for p in sorted(directory.glob("*.yml")):
                    if p.stem not in paths:
                        paths[p.stem] = p
        return paths

    def list(self) -> list[Playbook]:
        """Return all available playbooks (project overrides global)."""
        result = []
        for name, path in self._discover_paths().items():
            try:
                pb = self._load_from_path(path)
                result.append(pb)
            except Exception:
                pass
        return result

    def _load_from_path(self, path: Path) -> Playbook:
        if yaml is None:
            raise ImportError("PyYAML is required for playbooks (pip install pyyaml)")
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"Playbook {path} must be a YAML mapping")
        return _parse_playbook(data, str(path))

    def load(self, name: str) -> Playbook:
        """Load a playbook by name. Raises KeyError if not found."""
        paths = self._discover_paths()
        if name not in paths:
            available = ", ".join(sorted(paths)) or "(none)"
            raise KeyError(f"Playbook '{name}' not found. Available: {available}")
        return self._load_from_path(paths[name])

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        name: str,
        variables: dict[str, str] | None = None,
    ) -> PlaybookResult:
        """Execute a playbook by name."""
        playbook = self.load(name)
        return self._run_playbook(playbook, variables or {})

    def execute_playbook(
        self,
        playbook: Playbook,
        variables: dict[str, str] | None = None,
    ) -> PlaybookResult:
        """Execute a pre-loaded Playbook object."""
        return self._run_playbook(playbook, variables or {})

    def _run_playbook(
        self,
        playbook: Playbook,
        variables: dict[str, str],
    ) -> PlaybookResult:
        ctx = dict(variables)
        step_results: list[StepResult] = []
        completed = 0

        for idx, step in enumerate(playbook.steps):
            result = self._run_step(idx, step, ctx)
            step_results.append(result)
            # propagate output as {{output}} for next step
            if result.output:
                ctx["output"] = result.output
            if result.success:
                completed += 1
            else:
                return PlaybookResult(
                    name=playbook.name,
                    steps_completed=completed,
                    steps_total=len(playbook.steps),
                    success=False,
                    step_results=step_results,
                    variables=ctx,
                )

        return PlaybookResult(
            name=playbook.name,
            steps_completed=completed,
            steps_total=len(playbook.steps),
            success=True,
            step_results=step_results,
            variables=ctx,
        )

    def _interpolate(self, text: str, ctx: dict[str, str]) -> str:
        """Replace {{var}} placeholders from context."""
        def replace(m: re.Match) -> str:
            key = m.group(1).strip()
            return ctx.get(key, m.group(0))
        return re.sub(r"\{\{(\w+)\}\}", replace, text)

    def _run_step(
        self,
        idx: int,
        step: PlaybookStep,
        ctx: dict[str, str],
    ) -> StepResult:
        try:
            if step.type == "run":
                return self._step_run(idx, step, ctx)
            elif step.type == "prompt":
                return self._step_prompt(idx, step, ctx)
            elif step.type == "tool":
                return self._step_tool(idx, step, ctx)
            elif step.type == "condition":
                return self._step_condition(idx, step, ctx)
            else:
                return StepResult(
                    step_index=idx,
                    type=step.type,
                    success=False,
                    error=f"Unknown step type: {step.type}",
                )
        except Exception as exc:
            return StepResult(
                step_index=idx,
                type=step.type,
                success=False,
                error=str(exc),
            )

    def _step_run(
        self,
        idx: int,
        step: PlaybookStep,
        ctx: dict[str, str],
    ) -> StepResult:
        cmd = self._interpolate(step.command, ctx)
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        ctx["exit_code"] = str(proc.returncode)
        output = (proc.stdout + proc.stderr).strip()
        if proc.returncode != 0:
            return StepResult(
                step_index=idx,
                type="run",
                success=False,
                output=output,
                error=f"Command exited with code {proc.returncode}",
            )
        return StepResult(step_index=idx, type="run", success=True, output=output)

    def _step_prompt(
        self,
        idx: int,
        step: PlaybookStep,
        ctx: dict[str, str],
    ) -> StepResult:
        message = self._interpolate(step.message, ctx)
        if self._llm_callback is None:
            return StepResult(
                step_index=idx,
                type="prompt",
                success=False,
                error="No LLM callback configured",
            )
        response = self._llm_callback(message)
        ctx["llm_response"] = response
        return StepResult(
            step_index=idx, type="prompt", success=True, output=response
        )

    def _step_tool(
        self,
        idx: int,
        step: PlaybookStep,
        ctx: dict[str, str],
    ) -> StepResult:
        command = self._interpolate(step.command, ctx)
        if self._tool_callback is None:
            return StepResult(
                step_index=idx,
                type="tool",
                success=False,
                error="No tool callback configured",
            )
        output = self._tool_callback(command)
        ctx["tool_output"] = output
        return StepResult(step_index=idx, type="tool", success=True, output=output)

    def _step_condition(
        self,
        idx: int,
        step: PlaybookStep,
        ctx: dict[str, str],
    ) -> StepResult:
        condition = self._interpolate(step.condition, ctx)
        # Simple equality/truthiness evaluation (no exec/eval for security)
        branch_taken = self._evaluate_condition(condition, ctx)
        branch_steps = step.then_steps if branch_taken else step.else_steps

        outputs = []
        for sub_idx, sub_step in enumerate(branch_steps):
            result = self._run_step(sub_idx, sub_step, ctx)
            if result.output:
                outputs.append(result.output)
            if not result.success:
                return StepResult(
                    step_index=idx,
                    type="condition",
                    success=False,
                    output="\n".join(outputs),
                    error=result.error,
                )

        return StepResult(
            step_index=idx,
            type="condition",
            success=True,
            output="\n".join(outputs),
        )

    def _evaluate_condition(self, condition: str, ctx: dict[str, str]) -> bool:
        """
        Evaluate simple conditions like:
          "{{exit_code}} == 0"
          "{{output}} != ''"
          "true" / "false"
        """
        condition = condition.strip()
        if condition.lower() in ("true", "yes", "1"):
            return True
        if condition.lower() in ("false", "no", "0", ""):
            return False

        # equality: lhs == rhs or lhs != rhs
        for op in ("==", "!="):
            if op in condition:
                lhs, rhs = condition.split(op, 1)
                lhs = lhs.strip().strip("'\"")
                rhs = rhs.strip().strip("'\"")
                if op == "==":
                    return lhs == rhs
                else:
                    return lhs != rhs

        # fallback: non-empty string is truthy
        return bool(condition)
