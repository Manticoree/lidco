"""Python library API — synchronous wrappers for scripting — Q171."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LidcoResult:
    """Unified result from any API call."""

    success: bool
    output: str
    files_changed: list[str] = field(default_factory=list)
    tokens_used: int = 0
    duration: float = 0.0
    error: str = ""


# Default no-op execute function (replaced in production / tests).
def _default_execute(prompt: str, **kwargs: object) -> dict:
    return {"output": "", "files_changed": [], "tokens_used": 0, "error": "no executor configured"}


_execute_fn: Callable[..., dict] = _default_execute


def set_execute_fn(fn: Callable[..., dict]) -> None:
    """Inject the execution backend (for testability)."""
    global _execute_fn
    _execute_fn = fn


def _call(prompt: str, **kwargs: object) -> LidcoResult:
    start = time.monotonic()
    try:
        raw = _execute_fn(prompt, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return LidcoResult(
            success=False,
            output="",
            error=str(exc),
            duration=round(time.monotonic() - start, 4),
        )
    elapsed = round(time.monotonic() - start, 4)
    error = raw.get("error", "")
    return LidcoResult(
        success=not bool(error),
        output=str(raw.get("output", "")),
        files_changed=list(raw.get("files_changed", [])),
        tokens_used=int(raw.get("tokens_used", 0)),
        duration=elapsed,
        error=str(error) if error else "",
    )


def run(prompt: str, model: str = "", project_dir: str = ".") -> LidcoResult:
    """Run a prompt and return the result."""
    return _call(prompt, model=model, project_dir=project_dir)


def edit(file_path: str, instruction: str, dry_run: bool = False) -> LidcoResult:
    """Edit a file with an instruction."""
    prompt = f"Edit {file_path}: {instruction}"
    return _call(prompt, file_path=file_path, instruction=instruction, dry_run=dry_run)


def ask(question: str, context: str = "") -> LidcoResult:
    """Ask a question and return the answer."""
    prompt = question if not context else f"{question}\n\nContext:\n{context}"
    return _call(prompt, mode="ask")


def review(file_path: str) -> LidcoResult:
    """Review a file for issues."""
    prompt = f"Review {file_path} for issues"
    return _call(prompt, file_path=file_path, mode="review")
