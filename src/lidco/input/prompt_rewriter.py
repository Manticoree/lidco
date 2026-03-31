"""Prompt rewriting: expand vague prompts with context."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RewriteResult:
    """Result of prompt rewriting."""

    original: str
    rewritten: str
    was_rewritten: bool
    expansions: tuple[str, ...] = ()


# Vague prompt patterns and their context-aware expansions
_VAGUE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^fix\s+it\.?$", re.I), "fix_it"),
    (re.compile(r"^do\s+it\.?$", re.I), "do_it"),
    (re.compile(r"^make\s+it\s+work\.?$", re.I), "make_work"),
    (re.compile(r"^try\s+again\.?$", re.I), "try_again"),
    (re.compile(r"^same\s+thing\.?$", re.I), "same_thing"),
    (re.compile(r"^again\.?$", re.I), "again"),
    (re.compile(r"^yes\.?$", re.I), "yes"),
    (re.compile(r"^no\.?$", re.I), "no"),
    (re.compile(r"^ok\.?$", re.I), "ok"),
    (re.compile(r"^continue\.?$", re.I), "continue"),
    (re.compile(r"^go\s+ahead\.?$", re.I), "go_ahead"),
    (re.compile(r"^help\.?$", re.I), "help"),
    (re.compile(r"^what\s+now\??$", re.I), "what_now"),
    (re.compile(r"^now\s+what\??$", re.I), "what_now"),
]


class PromptRewriter:
    """Expands vague prompts using available context."""

    def rewrite(self, prompt: str, context: Optional[dict[str, str]] = None) -> RewriteResult:
        """Rewrite a prompt, expanding vague ones with context.

        Args:
            prompt: The user's input text.
            context: Optional dict with keys like 'last_error', 'recent_files',
                     'current_file' to enrich vague prompts.

        Returns:
            RewriteResult with original and potentially rewritten prompt.
        """
        if not prompt or not prompt.strip():
            return RewriteResult(
                original=prompt or "",
                rewritten=prompt or "",
                was_rewritten=False,
            )

        text = prompt.strip()
        ctx = context or {}

        # Check if prompt matches a vague pattern
        vague_type: Optional[str] = None
        for pattern, vtype in _VAGUE_PATTERNS:
            if pattern.match(text):
                vague_type = vtype
                break

        if vague_type is None:
            # Not vague — return as-is
            return RewriteResult(
                original=text,
                rewritten=text,
                was_rewritten=False,
            )

        # Expand the vague prompt using context
        parts: list[str] = []
        expansions: list[str] = []

        if vague_type in ("fix_it", "make_work", "try_again"):
            if "last_error" in ctx:
                parts.append(f"Fix the error: {ctx['last_error']}")
                expansions.append("added_last_error")
            elif "current_file" in ctx:
                parts.append(f"Fix the issue in {ctx['current_file']}")
                expansions.append("added_current_file")
            else:
                parts.append("Fix the most recent issue")
                expansions.append("generic_fix")

        elif vague_type in ("do_it", "go_ahead", "yes", "ok", "continue"):
            if "current_file" in ctx:
                parts.append(f"Continue working on {ctx['current_file']}")
                expansions.append("added_current_file")
            else:
                parts.append("Continue with the previous task")
                expansions.append("generic_continue")

        elif vague_type in ("same_thing", "again"):
            parts.append("Repeat the previous action")
            expansions.append("repeat_previous")

        elif vague_type == "no":
            parts.append("Cancel the current suggestion and try a different approach")
            expansions.append("cancel_suggestion")

        elif vague_type in ("help", "what_now"):
            if "last_error" in ctx:
                parts.append(f"Help me understand and fix: {ctx['last_error']}")
                expansions.append("added_last_error")
            elif "current_file" in ctx:
                parts.append(f"Suggest next steps for {ctx['current_file']}")
                expansions.append("added_current_file")
            else:
                parts.append("Show available commands and suggest next steps")
                expansions.append("generic_help")

        # Add recent files context if available and not already used
        if "recent_files" in ctx and "added_current_file" not in expansions:
            parts.append(f"(recently edited: {ctx['recent_files']})")
            expansions.append("added_recent_files")

        rewritten = " ".join(parts) if parts else text

        return RewriteResult(
            original=text,
            rewritten=rewritten,
            was_rewritten=True,
            expansions=tuple(expansions),
        )
